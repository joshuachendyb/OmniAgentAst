# -*- coding: utf-8 -*-
"""
FileReactAgent - 文件操作 ReAct Agent

参考: 文档5.5节+7.4节完整代码

继承 BaseAgent，专用于文件操作场景的 ReAct 智能体。

【Phase 2修复 2026-04-26 小沈】：
- 添加 tool_category 参数替换旧的 intent_type
- 使用 ToolLoaderMixin 加载工具
- 移除旧参数兼容

Author: 小沈 - 2026-03-21
Updated: 小沈 - 2026-04-26
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable

from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.types import Step, AgentResult, AgentStatus
from app.services.agent.llm_strategies import TextStrategy, ToolsStrategy, ResponseFormatStrategy
from app.services.agent.llm_adapter import LLMAdapter
from app.services.tools.file.file_tools import FileTools
from app.services.prompts.file.file_prompts import FileOperationPrompts
from app.services.agent.session import get_session_service
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.chat_stream.sse_formatter import format_thought_sse, format_action_tool_sse, format_observation_sse
from app.chat_stream.chat_helpers import create_final_response, create_timestamp
from app.chat_stream.error_handler import create_error_response


class FileReactAgent(ToolLoaderMixin, BaseAgent):
    """
    文件操作 ReAct Agent - 使用tool_category参数
    参考: 7.4节行956-1051
    
    实现完整的 Thought-Action-Observation 循环，
    专用于文件操作场景，保留 session管理、prompts、rollback 功能
    """
    
    def __init__(
        self,
        llm_client: Any,
        # 【重要】task_id 用于操作追踪和回退，【禁止】使用 session_id
        # session_id 专用于会话场景，操作追踪必须用 task_id
        task_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        **kwargs
    ):
        """
        初始化 FileReactAgent
        参考: 7.4节行961-1039
        
        Args:
            llm_client: LLM 客户端函数
            task_id: 任务ID（必需）- 用于操作安全追踪和审计
            # 【禁止】不要使用 session_id，会话和操作追踪是不同概念
            tool_category: 工具分类（可选，默认FILE）
            max_steps: 最大步数
        """
        # 【修复】强制要求 task_id，避免写操作失败
        if not task_id:
            raise ValueError("task_id is required for file operation tracking and safety")
        
        # 提取有效的tool_category
        effective_category = tool_category or ToolCategory.FILE
        
        # 调用父类初始化
        super().__init__(
            llm_client=llm_client,
            task_id=task_id,  # 【修改】2026-04-26 小沈
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        # 初始化 session 服务（用于统一管理会话生命周期）
        self.session_service = get_session_service()
        
        # 【修复】标记 session 是否由本 Agent 创建（用于正确关闭）
        self._session_created_by_agent = False
        
        # 初始化文件工具确保 task_id 正确传递
        self.file_tools = FileTools(task_id=task_id)  # 【修改】session_id → task_id，2026-04-26 小沈
        
        # 使用Mixin的工具加载方法
        if self.tool_category:
            self._tools_dict = ToolLoaderMixin._load_tools(self, self.tool_category)
        
        self.executor = ToolExecutor(self._tools_dict)
        
        self.prompts = FileOperationPrompts()
        
        logger.info(f"FileReactAgent initialized (task_id: {task_id}, tool_category: {effective_category})")
        
        # 【新增】LLM调用策略
        self.text_strategy = TextStrategy()
        
        # 简化：暂时为空，需要时由调用方传入
        self.use_function_calling = False
        self.openai_tools = []
        self.tools_strategy = None
        self.response_format_strategy = None
        self.adapter = None
        
        # Simple initialization - continue
        logger.info(f"FileReactAgent initialized (task_id: {task_id}, tool_category: {effective_category})")
    
    # ========== 抽象方法实现 ==========
    
    # ========== 重写 _get_llm_response ==========
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应的统一入口（重写，添加 adapter 策略选择）"""
        self.llm_call_count += 1
        logger.info(f"[LLM Counter] >>> LLM called, count: {self.llm_call_count}")
        
        # ========== LLM 调用日志记录 ==========
        from datetime import datetime
        prompt_logger = get_prompt_logger()
        prompt_logger.log_llm_call(
            round_number=self.llm_call_count,
            messages=self.conversation_history.copy(),
            model=getattr(self, 'model', 'unknown'),
            provider=getattr(self, 'provider', 'unknown'),
            call_type="text",
            extra_params={
                "max_steps": self.max_steps,
                "use_function_calling": self.use_function_calling
            }
        )
        # 保存日志到文件，确保JSON文件生成
        try:
            prompt_logger.save()
        except Exception as e:
            logger.warning(f"Failed to save prompt log: {e}")
        
        try:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]
            
            # 【调试】记录发送给LLM的messages
            logger.info(f"[Debug] _get_llm_response - conversation_history长度: {len(self.conversation_history)}")
            logger.info(f"[Debug] _get_llm_response - history_dicts长度: {len(history_dicts)}")
            for i, h in enumerate(history_dicts):
                logger.info(f"[Debug] history[{i}] role={h.get('role')}, content长度={len(h.get('content', ''))}")
            logger.info(f"[Debug] _get_llm_response - last_message长度: {len(last_message)}")
            logger.info(f"[Debug] _get_llm_response - last_message内容: {last_message[:200]}")
            
            # 【修改】使用 LLMAdapter 自适应策略
            if self.adapter:
                strategy = await self.adapter.ensure_capability()
                logger.info(f"[Agent] Using method: {strategy.method}")
                
                if strategy.method == "response_format":
                    response = await self.response_format_strategy.call(
                        llm_client=self.llm_client,
                        message=last_message,
                        history_dicts=history_dicts,
                        conversation_history=self.conversation_history
                    )
                elif strategy.method == "tools":
                    self.tools_strategy.tools = self.tools or []
                    response = await self.tools_strategy.call(
                        llm_client=self.llm_client,
                        message=last_message,
                        history_dicts=history_dicts,
                        conversation_history=self.conversation_history
                    )
                else:
                    response = await self.text_strategy.call(
                        llm_client=self.llm_client,
                        message=last_message,
                        history_dicts=history_dicts,
                        conversation_history=self.conversation_history
                    )
            elif self.use_function_calling and self.tools:
                # 使用 Function Calling 模式
                self.tools_strategy.tools = self.tools
                response = await self.tools_strategy.call(
                    llm_client=self.llm_client,
                    message=last_message,
                    history_dicts=history_dicts,
                    conversation_history=self.conversation_history
                )
            else:
                # 使用普通文本模式
                response = await self.text_strategy.call(
                    llm_client=self.llm_client,
                    message=last_message,
                    history_dicts=history_dicts,
                    conversation_history=self.conversation_history
                )
            
            # 记录 LLM 返回结果到 prompt_logger
            response_type = "text"
            if response:
                if "action_tool" in response:
                    response_type = "action_tool"
                elif "thought" in response:
                    response_type = "thought"
                elif "observation" in response:
                    response_type = "observation"
            
            prompt_logger.log_llm_response(
                round_number=self.llm_call_count,
                response_content=response,
                response_type=response_type,
                finish_reason="stop"
            )
            
            return response
            
        except Exception as e:
            logger.error(f"LLM client error: {e}")
            raise
    
    async def _get_llm_response_text(
        self,
        message: str,
        history_dicts: List[Dict[str, str]]
    ) -> str:
        """获取 LLM 响应（文本模式）- 使用策略类"""
        return await self.text_strategy.call(
            llm_client=self.llm_client,
            message=message,
            history_dicts=history_dicts,
            conversation_history=self.conversation_history
        )
    
    async def _get_llm_response_with_tools(
        self,
        message: str,
        history_dicts: List[Dict[str, str]]
    ) -> str:
        """获取 LLM 响应（Function Calling 模式）- 使用策略类"""
        self.tools_strategy.tools = self.tools or []
        return await self.tools_strategy.call(
            llm_client=self.llm_client,
            message=message,
            history_dicts=history_dicts,
            conversation_history=self.conversation_history
        )
    
    async def _execute_tool(
        self,
        action: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具的抽象方法实现
        
        【关键】直接使用 self.file_tools（有正确 task_id），
        而不是通过 executor（executor 用的是 registry 里没有 task_id 的工具）
        
        【2026-04-27 小沈修复】：调用 _normalize_params 做参数别名映射
        【2026-04-28 小沈修复】：添加工具名映射，支持 create_dir → create_directory
        """
        # 【2026-04-28 小沈新增】工具名映射表（LLM返回名 → 实际方法名）
        TOOL_NAME_MAP = {
            "create_dir": "create_directory",
            "list_dir": "list_directory",
            "delete_dir": "delete_directory",
            "rename_dir": "rename_directory",
        }
        
        # 映射工具名
        original_action = action
        action = TOOL_NAME_MAP.get(action, action)
        if original_action != action:
            logger.info(f"[file_react._execute_tool] 工具名映射: {original_action} → {action}")
        
        # 【2026-04-27 小沈新增】标准化参数（别名映射）
        normalized_params = self.executor._normalize_params(action, params)
        logger.info(f"[file_react._execute_tool] action={action}, 原params={params}, 标准化后={normalized_params}")
        
        tool_method = getattr(self.file_tools, action, None)
        if not tool_method:
            return {"success": False, "error": f"Tool '{original_action}' not found", "result": None}
        return await tool_method(**normalized_params)
    
    # ===== 实现父类抽象方法 =====
    
    def _get_system_prompt(self) -> str:
        """获取系统 Prompt"""
        # 如果有自定义的 system_prompt，先使用它
        if hasattr(self, '_custom_system_prompt') and self._custom_system_prompt:
            return self._custom_system_prompt
        return self.prompts.get_system_prompt()
    
    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """获取任务 Prompt"""
        return self.prompts.get_task_prompt(task, context)
    
    # ===== 实现父类 Hook 方法 =====
    
    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]]):
        """Session 初始化 Hook"""
        # 确保 session 存在
        session_id = self.task_id
        if not session_id:
            session_id = self.session_service.create_session(
                agent_id="file-operation-agent",
                task_description=task
            )
            self._session_created_by_agent = True
            if hasattr(self.file_tools, 'set_session'):
                self.file_tools.set_session(session_id)
            logger.info(f"Session created in run_stream(): {session_id}")
    
    def _on_before_loop(self, sys_prompt: str, task_prompt: str, context: Optional[Dict[str, Any]] = None):
        """循环开始前 Hook - 无操作，日志记录已由上层处理"""
        pass
    
    def _on_after_loop(self):
        """循环结束后 Hook - 关闭 Session"""
        if self._session_created_by_agent and self.task_id and self.session_service:
            try:
                self.session_service.complete_session(self.task_id, success=True)
                logger.info(f"Session completed in run_stream: {self.task_id}")
                self._session_created_by_agent = False
            except Exception as e:
                logger.error(f"Failed to complete session {self.task_id}: {e}")
    
    # ========== 文件专用方法 ==========
    
    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """
        运行 Agent 完成任务
        
        【重构 2026-03-31 小沈】：
        - 删除重复的 ReAct 循环实现
        - 统一调用父类 run_stream() 方法
        - 消除 run() 和 run_stream() 的行为不一致问题
        - 保留 session 管理和锁保护逻辑
        
        Args:
            task: 任务描述
            context: 额外上下文
            system_prompt: 自定义系统 prompt（可选）
            
        Returns:
            Agent 执行结果
        """
        async with self._lock:
            return await self._run_with_session(task, context, system_prompt)
    
    async def _run_with_session(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """
        内部运行方法（带 session 管理）
        
        【重构 2026-03-31 小沈】：
        - 删除重复的 ReAct 循环实现（原第457-533行）
        - 统一调用父类 run_stream() 方法
        - 消除与 base_react.py run_stream() 的行为不一致
        - 保留 session 管理、锁保护、结果收集逻辑
        
        【说明】意图识别已移至路由层（chat_router.py），此处只做文件操作
        """
        # 获取 session_id 用于日志追踪
        session_id = self.task_id or ""
        
        # 使用局部变量管理 session（session_id 在预处理前已获取）
        session_created_by_this_run = False
        
        # 确保 session 已创建
        if not session_id:
            session_id = self.session_service.create_session(
                agent_id="file-operation-agent",
                task_description=task
            )
            session_created_by_this_run = True
            self._session_created_by_agent = True
            
            if hasattr(self.file_tools, 'set_session'):
                self.file_tools.set_session(session_id)
            logger.info(f"Session created in run(): {session_id}")
        
        # 【重构 2026-03-31】调用父类 run_stream() 统一执行 ReAct 循环
        # 消除与 base_react.py 的重复实现，确保行为一致
        result = None
        try:
            async for event in self.run_stream(task, context):
                event_type = event.get("type")
                
                if event_type == "final":
                    # 任务完成
                    result = AgentResult(
                        success=True,
                        message=event.get("content", "Task completed successfully"),
                        steps=self.steps,
                        total_steps=len(self.steps),
                        session_id=session_id,
                        final_result=event.get("content")
                    )
                elif event_type == "error":
                    # 任务出错
                    result = AgentResult(
                        success=False,
                        message=event.get("message", "Execution failed"),
                        steps=self.steps,
                        total_steps=len(self.steps),
                        session_id=session_id,
                        error=event.get("message")
                    )
            
            # 如果没有收到 final 或 error 事件（例如 max_steps 耗尽）
            if result is None:
                result = AgentResult(
                    success=False,
                    message=f"Exceeded maximum steps ({self.max_steps})",
                    steps=self.steps,
                    total_steps=len(self.steps),
                    session_id=session_id,
                    error="Maximum steps exceeded"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            result = AgentResult(
                success=False,
                message=f"Execution failed: {str(e)}",
                steps=self.steps,
                total_steps=len(self.steps),
                session_id=session_id,
                error=str(e)
            )
            return result
            
        finally:
            # 只关闭由本次 run 创建的 session
            if session_created_by_this_run and session_id and self.session_service:
                try:
                    success = result.success if result else False
                    self.session_service.complete_session(session_id, success=success)
                    logger.info(f"Session completed: {session_id} (success={success})")
                    self._session_created_by_agent = False
                    self.task_id = None
                except Exception as e:
                    logger.error(f"Failed to complete session {session_id}: {e}")
    
    async def rollback(self, step_number: Optional[int] = None) -> bool:
        """
        回滚操作
        
        Args:
            step_number: 要回滚到的步骤号（None 表示回滚所有）
            
        Returns:
            是否成功
        """
        try:
            if not self.task_id:
                raise ValueError("Session ID is required for rollback")
            
            if step_number is None:
                # 回滚整个会话
                result = await asyncio.to_thread(
                    self.file_tools.safety.rollback_session, self.task_id
                )
                success = result.get("success", 0) > 0
            else:
                # 回滚到指定步骤
                steps_to_rollback = [s for s in self.steps if s.step_number > step_number]
                
                if not steps_to_rollback:
                    return False
                
                success = True
                for step in sorted(steps_to_rollback, key=lambda s: s.step_number, reverse=True):
                    observation = step.observation or {}
                    result_data = observation.get("result", {}) if isinstance(observation, dict) else {}
                    operation_id = result_data.get("operation_id")
                    if operation_id:
                        step_success = await asyncio.to_thread(
                            self.file_tools.safety.rollback_operation, operation_id
                        )
                        success = success and step_success
                    else:
                        raise ValueError(f"No operation_id found for step {step.step_number}")
            
            self.status = AgentStatus.ROLLED_BACK
            return success
            
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    # 【阶段6删除 2026-03-27 小沈】
    # 删除 ver1_run_stream() 方法，SSE 格式化逻辑移到 react_sse_wrapper
    # FileReactAgent.run_stream() 返回 event dict，供 react_sse_wrapper 调用
    
    # 注意：保留的工具定义和 Prompt 模板仍然需要，
    # 它们是 FileReactAgent 特有的逻辑