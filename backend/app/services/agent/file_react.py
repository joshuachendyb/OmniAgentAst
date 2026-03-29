# -*- coding: utf-8 -*-
"""
FileReactAgent - 文件操作 ReAct Agent

继承 BaseAgent，专用于文件操作场景的 ReAct 智能体。
从 agent.py 复制，删除 intent-type 分支后改造。

【重构 Phase 4 - 2026-03-26 小沈】：
- 从 agent.py 复制，采用"复制+删除法"改造
- 删除 intent-type 分支（network/desktop）
- 保留文件操作专用逻辑（session管理、prompts、rollback）

【2026-03-26 小沈完成】：
- ✅ 已删除 intent_registry 和 preprocessor 对象
- ✅ 已删除 run_stream 方法中的意图识别调用
- FileReactAgent 现在是纯文件操作专用 Agent，意图识别由路由层处理

Author: 小沈 - 2026-03-21
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, AsyncGenerator, Callable

from app.services.agent.base_react import BaseAgent
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.types import Step, AgentResult, AgentStatus
from app.services.tools.file.file_tools import FileTools
from app.services.prompts.file.file_prompts import FileOperationPrompts
from app.services.agent.session import get_session_service
from app.services.agent.llm_adapter import LLMAdapter
from app.services.agent.adapter import dict_list_to_messages
from app.services.agent.llm_strategies import TextStrategy, ToolsStrategy, ResponseFormatStrategy
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.chat_stream.sse_formatter import format_thought_sse, format_action_tool_sse, format_observation_sse
from app.chat_stream.chat_helpers import create_final_response, create_timestamp
from app.chat_stream.error_handler import create_error_response


class FileReactAgent(BaseAgent):
    """
    文件操作 ReAct Agent，继承 BaseAgent
    
    实现完整的 Thought-Action-Observation 循环，
    专用于文件操作场景，保留 session管理、prompts、rollback 功能
    """
    
    def __init__(
        self,
        llm_client: Any,
        session_id: str,
        intent_type: str = "file",  # 【新增】意图类型参数
        file_tools: Optional[FileTools] = None,
        max_steps: int = 20,
        use_function_calling: bool = False,
        tools: Optional[List[Dict[str, Any]]] = None,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        初始化 FileReactAgent
        
        Args:
            llm_client: LLM 客户端函数
            session_id: 会话 ID（必需）- 用于操作安全追踪和审计
            file_tools: 文件工具实例（可选，默认创建新实例）
            max_steps: 最大执行步数
            use_function_calling: 是否使用 Function Calling 模式
            tools: 工具定义列表
            api_base: LLM API 地址（可选，用于自适应探测）
            api_key: LLM API 密钥（可选，用于自适应探测）
            model: LLM 模型名称（可选，用于自适应探测）
        """
        # 【修复】强制要求 session_id，避免写操作失败
        if not session_id:
            raise ValueError("session_id is required for file operation tracking and safety")
        
        # 【新增】保存 intent_type 参数
        self.intent_type = intent_type
        
        # 【修复】调用父类初始化
        super().__init__(max_steps=max_steps)
        
        # 【扩展】保存 use_function_calling（父类不需要，但子类需要）
        self.use_function_calling = use_function_calling
        
        # 会话ID
        self.llm_client = llm_client
        self.session_id = session_id
        
        # 初始化 session 服务（用于统一管理会话生命周期）
        self.session_service = get_session_service()
        
        # 【修复】标记 session 是否由本 Agent 创建（用于正确关闭）
        self._session_created_by_agent = False
        
        # 根据 intent_type 加载对应工具/安全检查/Prompt
        if intent_type == "file":
            # 初始化文件工具，确保 session_id 正确传递
            self.file_tools = file_tools or FileTools(session_id=session_id)
            
            # ToolExecutor - 使用 tools dict
            self._tools_dict = {
                "read_file": self.file_tools.read_file,
                "write_file": self.file_tools.write_file,
                "list_directory": self.file_tools.list_directory,
                "delete_file": self.file_tools.delete_file,
                "move_file": self.file_tools.move_file,
                "search_files": self.file_tools.search_files,
                "search_file_content": self.file_tools.search_file_content,
                "generate_report": self.file_tools.generate_report,
            }
            self.executor = ToolExecutor(self._tools_dict)
            
            self.prompts = FileOperationPrompts()
            
            logger.info(f"FileReactAgent initialized (session: {session_id})")
        else:
            # FileReactAgent 只支持 file 意图
            raise ValueError(f"FileReactAgent only supports intent_type='file', got: {intent_type}")
        
        # 【新增】LLM调用策略
        self.text_strategy = TextStrategy()
        
        # 构建OpenAI格式的tools列表（如果未提供）
        # 【修复】当有 api 参数时（使用 adapter），默认启用 tools
        has_api_params = bool(api_base and api_key and model)
        should_use_function_calling = use_function_calling or has_api_params
        
        openai_tools = tools or []
        if not openai_tools and should_use_function_calling:
            # 从注册表获取工具定义并转换为OpenAI格式
            from app.services.tools.file import get_registered_tools
            from app.services.agent.types.react_schema import _process_description, _clean_properties
            
            mcp_tools = get_registered_tools(category="file")
            openai_tools = []
            for tool in mcp_tools:
                # 转换逻辑（参考react_schema.py）
                properties = tool.get("input_schema", {}).get("properties", {})
                required = tool.get("input_schema", {}).get("required", [])
                cleaned_properties = _clean_properties(properties)
                
                openai_tool = {
                    "type": "function",
                    "function": {
                        "name": tool.get("name", ""),
                        "description": _process_description(tool.get("description", "")),
                        "parameters": {
                            "type": "object",
                            "properties": cleaned_properties,
                            "required": required
                        }
                    }
                }
                openai_tools.append(openai_tool)
            
            # 记录工具Prompt日志
            prompt_logger = get_prompt_logger()
            for tool_def in openai_tools:
                prompt_logger.log_tool_prompt(
                    tool_name=tool_def["function"]["name"],
                    prompt_content=json.dumps(tool_def, ensure_ascii=False, indent=2),
                    source="file_tools.py:register_tool"
                )
        
        self.tools_strategy = ToolsStrategy(tools=openai_tools)
        self.response_format_strategy = ResponseFormatStrategy()
        
        # Function Calling 支持
        self.tools = openai_tools
        
        # LLMAdapter 自适应探测
        self.adapter = None  # 【小沈修复 2026-03-23】确保 adapter 属性存在
        logger.info(f"[FileReactAgent] init - api_base={api_base}, api_key={'***' if api_key else None}, model={model}")
        if api_base and api_key and model:
            self.adapter = LLMAdapter(
                api_base=api_base,
                api_key=api_key,
                model=model,
                auto_detect=True
            )
            logger.info(f"FileReactAgent initialized (session: {session_id}, adapter=LLMAdapter, model={model})")
        else:
            logger.warning(f"FileReactAgent initialized (session: {session_id}, adapter=None - 缺少api参数)")
            if use_function_calling and tools:
                logger.info(f"FileReactAgent initialized (session: {session_id}, function_calling=True, tools_count={len(self.tools)})")
            else:
                logger.info(f"FileReactAgent initialized (session: {session_id})")
    
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
        
        代理到 ToolExecutor.execute
        """
        return await self.executor.execute(action, params)
    
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
        session_id = self.session_id
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
        if self._session_created_by_agent and self.session_id and self.session_service:
            try:
                self.session_service.complete_session(self.session_id, success=True)
                logger.info(f"Session completed in run_stream: {self.session_id}")
                self._session_created_by_agent = False
            except Exception as e:
                logger.error(f"Failed to complete session {self.session_id}: {e}")
    
    # ========== 文件专用方法 ==========
    
    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None
    ) -> AgentResult:
        """
        运行 Agent 完成任务
        
        【修复】使用锁保护确保并发安全
        【修复】每次 run 独立管理状态和 session
        
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
        
        【说明】意图识别已移至路由层（chat_router.py），此处只做文件操作
        """
        # 重置状态
        self.steps = []
        self.conversation_history = []
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        logger.info(f"[LLM Counter] Agent run started, LLM counter reset to 0")
        
        # 获取 session_id 用于日志追踪
        session_id = self.session_id or ""
        
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
        
        # 构建初始 prompt
        sys_prompt = system_prompt or self.prompts.get_system_prompt()
        task_prompt = self.prompts.get_task_prompt(task, context)
        
        # 添加到对话历史
        self.conversation_history.append({"role": "system", "content": sys_prompt})
        self.conversation_history.append({"role": "user", "content": task_prompt})
        
        current_step = 0
        result = None
        
        try:
            while current_step < self.max_steps:
                current_step += 1
                
                # 1. Thought - 获取 LLM 响应
                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()
                
                # 2. Action - 解析响应
                try:
                    parsed = self.parser.parse_response(response)
                except ValueError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    self._add_observation_to_history(
                        f"Parse error: {e}. Please respond with valid JSON format."
                    )
                    continue
                
                # 使用新字段名（兼容旧字段）
                thought_content = parsed.get("content", parsed.get("thought", ""))
                action_tool = parsed.get("action_tool", parsed.get("action", "finish"))
                params = parsed.get("params", parsed.get("action_input", {}))
                
                # 创建步骤记录
                step = Step(
                    step_number=current_step,
                    thought=thought_content,
                    action=action_tool,
                    action_input=params
                )
                
                logger.info(
                    f"Step {current_step}: {action_tool} - {thought_content[:50]}..."
                )
                
                # 3. 检查是否完成
                if action_tool == "finish":
                    if isinstance(params, dict):
                        final_result = params
                    else:
                        final_result = {"result": str(params)}
                    
                    step.observation = {
                        "success": True,
                        "result": final_result
                    }
                    self.steps.append(step)
                    self.status = AgentStatus.COMPLETED
                    
                    result = AgentResult(
                        success=True,
                        message="Task completed successfully",
                        steps=self.steps,
                        total_steps=current_step,
                        session_id=session_id,
                        final_result=final_result
                    )
                    return result
                
                # 4. Observation - 执行动作
                # 【修复 2026-03-26】原错误调用 _execute_with_retry（不存在），改为 _execute_tool
                # 说明：_execute_tool 执行一次失败就失败，_execute_with_retry 会自动重试
                # 当前统一使用 _execute_tool，简单可靠
                self.status = AgentStatus.EXECUTING
                observation = await self._execute_tool(
                    action_tool,
                    params
                )
                
                step.observation = observation
                self.steps.append(step)
                
                # 5. 添加观察结果到对话历史
                obs_text = self._format_observation(observation)
                self._add_observation_to_history(obs_text)
                
                self.status = AgentStatus.OBSERVING
            
            # 超过最大步数
            self.status = AgentStatus.FAILED
            result = AgentResult(
                success=False,
                message=f"Exceeded maximum steps ({self.max_steps})",
                steps=self.steps,
                total_steps=current_step,
                session_id=session_id,
                error="Maximum steps exceeded"
            )
            return result
            
        except Exception as e:
            logger.error(f"Agent execution error: {e}", exc_info=True)
            self.status = AgentStatus.FAILED
            result = AgentResult(
                success=False,
                message=f"Execution failed: {str(e)}",
                steps=self.steps,
                total_steps=current_step,
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
                    self.session_id = None
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
            if not self.session_id:
                raise ValueError("Session ID is required for rollback")
            
            if step_number is None:
                # 回滚整个会话
                result = await asyncio.to_thread(
                    self.file_tools.safety.rollback_session, self.session_id
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