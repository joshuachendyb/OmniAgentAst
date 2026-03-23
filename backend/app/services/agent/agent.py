# -*- coding: utf-8 -*-
"""
IntentAgent - 通用意图 Agent

继承 BaseAgent，实现 ReAct 循环的通用意图智能体，
通过 intent_type 参数决定加载哪套工具/安全检查/Prompt，
各意图共用同一套 ReAct 循环逻辑

【重构 Phase 3】：
- 删除重复的 ToolParser、ToolExecutor、AgentStatus、Step、AgentResult 定义
- 继承 BaseAgent，实现抽象方法
- 保留文件专用逻辑（session管理、prompts、rollback）

【重命名】2026-03-21 小沈 - FileOperationAgent → IntentAgent

Author: 小沈 - 2026-03-21
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, AsyncGenerator

from app.services.agent.base import BaseAgent
from app.services.agent.tool_executor import ToolExecutor
from app.services.agent.types import Step, AgentResult, AgentStatus
from app.services.tools.file.file_tools import FileTools
from app.services.prompts.file.file_prompts import FileOperationPrompts
from app.services.agent.session import get_session_service
from app.services.agent.llm_adapter import LLMAdapter
from app.services.agent.adapter import dict_list_to_messages
from app.services.intent import IntentRegistry, Intent
from app.services.preprocessing import PreprocessingPipeline
from app.services.agent.llm_strategies import TextStrategy, ToolsStrategy, ResponseFormatStrategy
from app.utils.logger import logger
from app.chat_stream.sse_formatter import format_thought_sse, format_action_tool_sse, format_observation_sse
from app.chat_stream.chat_helpers import create_final_response
from app.chat_stream.error_handler import create_error_response


class IntentAgent(BaseAgent):
    """
    通用意图 Agent，继承 BaseAgent
    
    实现完整的 Thought-Action-Observation 循环，
    通过 intent_type 参数决定加载哪套工具/安全检查/Prompt，
    各意图共用同一套 ReAct 循环逻辑
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
        初始化 IntentAgent
        
        Args:
            llm_client: LLM 客户端函数，接收 message 和 history，返回 response
            session_id: 会话 ID（必需）- 用于操作安全追踪和审计
            intent_type: 意图类型，决定加载哪套工具/安全检查/Prompt（默认"file"）
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
        super().__init__(max_steps=max_steps, use_function_calling=use_function_calling)
        
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
                "generate_report": self.file_tools.generate_report,
            }
            self.executor = ToolExecutor(self._tools_dict)
            
            self.prompts = FileOperationPrompts()
            
            logger.info(f"IntentAgent initialized (intent_type=file, session: {session_id})")
        elif intent_type == "desktop":
            # 预留：桌面操作意图
            self.file_tools = None
            self._tools_dict = {}
            self.executor = ToolExecutor(self._tools_dict)
            self.prompts = None
            logger.warning(f"IntentAgent initialized (intent_type=desktop, session: {session_id}) - not implemented")
        elif intent_type == "network":
            # 预留：网络操作意图
            self.file_tools = None
            self._tools_dict = {}
            self.executor = ToolExecutor(self._tools_dict)
            self.prompts = None
            logger.warning(f"IntentAgent initialized (intent_type=network, session: {session_id}) - not implemented")
        else:
            raise ValueError(f"Unsupported intent_type: {intent_type}. Supported: file, desktop, network")
        
        # 【新增】意图注册表（多意图支持）
        self.intent_registry = IntentRegistry()
        self._register_default_intents()
        
        # 【新增】预处理流水线（多意图支持）
        self.preprocessor = PreprocessingPipeline()
        
        # 【新增】LLM调用策略
        self.text_strategy = TextStrategy()
        self.tools_strategy = ToolsStrategy(tools=tools or [])
        self.response_format_strategy = ResponseFormatStrategy()
        
        # Function Calling 支持
        self.tools = tools or []
        
        # LLMAdapter 自适应探测
        if api_base and api_key and model:
            self.adapter = LLMAdapter(
                api_base=api_base,
                api_key=api_key,
                model=model,
                auto_detect=True
            )
            logger.info(f"IntentAgent initialized (session: {session_id}, adapter=LLMAdapter, model={model})")
        else:
            if use_function_calling and tools:
                logger.info(f"IntentAgent initialized (session: {session_id}, function_calling=True, tools_count={len(self.tools)})")
            else:
                logger.info(f"IntentAgent initialized (session: {session_id})")
    
    def _register_default_intents(self):
        """注册默认意图类型"""
        # file 意图
        file_intent = Intent(
            name="file",
            description="文件读写、目录管理、文件搜索",
            keywords=["文件", "读取", "写入", "删除", "移动", "目录", "搜索", "创建"],
            tools=["read_file", "write_file", "list_directory", "delete_file", "move_file", "search_files", "generate_report"],
            safety_checker="file_safety"
        )
        self.intent_registry.register(file_intent)
        
        # network 意图（预留）
        network_intent = Intent(
            name="network",
            description="网络搜索、网页访问、API调用",
            keywords=["搜索", "网络", "网页", "API", "http", "https"],
            tools=[],  # 待实现
            safety_checker=None
        )
        self.intent_registry.register(network_intent)
        
        logger.info(f"Registered {len(self.intent_registry.list_all())} intents")
    
    # ========== 抽象方法实现 ==========
    
    # ========== 重写 _get_llm_response ==========
    
    async def _get_llm_response(self) -> str:
        """获取 LLM 响应的统一入口（重写，添加 adapter 策略选择）"""
        self.llm_call_count += 1
        logger.info(f"[LLM Counter] >>> LLM called, count: {self.llm_call_count}")
        
        try:
            last_message = self.conversation_history[-1]["content"]
            history_dicts = self.conversation_history[:-1]
            
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
        action_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        执行工具的抽象方法实现
        
        代理到 ToolExecutor.execute
        """
        return await self.executor.execute(action, action_input)
    
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
        
        【设计要求】使用预处理流水线和意图注册表
        """
        # 重置状态
        self.steps = []
        self.conversation_history = []
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        logger.info(f"[LLM Counter] Agent run started, LLM counter reset to 0")
        
        # 获取 session_id 用于日志追踪
        session_id = self.session_id or ""
        
        # 【设计要求】使用预处理流水线预处理用户输入
        try:
            preprocessed = self.preprocessor.process(
                task,
                list(self.intent_registry.get_all_names()),
                session_id=session_id
            )
            logger.info(f"[Agent] Preprocessed: intent={preprocessed.get('intent')}, confidence={preprocessed.get('confidence')}")
        except Exception as e:
            logger.warning(f"[Agent] Preprocessing failed: {e}, using original input")
            preprocessed = {"corrected": task, "intent": "unknown", "confidence": 0.0}
        
        # 【设计要求】使用意图注册表获取意图定义
        intent_def = self.intent_registry.get(self.intent_type)
        if intent_def:
            logger.info(f"[Agent] Using intent: {intent_def.name} ({intent_def.description})")
        else:
            logger.warning(f"[Agent] Intent definition not found for: {self.intent_type}")
        
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
                
                # 4. Observation - 执行动作（使用重试机制）
                self.status = AgentStatus.EXECUTING
                observation = await self._execute_with_retry(
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
    
    async def run_stream(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        【Phase2新增】异步流式执行 Agent，每轮循环完成后立即 yield 输出
        
        Args:
            task: 任务描述
            context: 额外上下文
            system_prompt: 自定义系统 prompt（可选）
            max_steps: 最大迭代次数
        
        Yields:
            各个阶段的输出字典
        """
        # 重置状态
        self.steps = []
        self.conversation_history = []
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        
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
        
        # 构建初始 prompt
        sys_prompt = system_prompt or self.prompts.get_system_prompt()
        task_prompt = self.prompts.get_task_prompt(task, context)
        
        # 添加到对话历史
        self.conversation_history.append({"role": "system", "content": sys_prompt})
        self.conversation_history.append({"role": "user", "content": task_prompt})
        
        step_count = 0
        
        try:
            while step_count < max_steps:
                step_count += 1
                
                # ========== Thought 阶段 ==========
                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()
                
                # 解析响应
                try:
                    parsed = self.parser.parse_response(response)
                except ValueError as e:
                    logger.error(f"Failed to parse LLM response: {e}")
                    self._add_observation_to_history(f"Parse error: {e}. Please respond with valid JSON format.")
                    continue
                
                thought_content = parsed.get("content", "")
                reasoning = parsed.get("reasoning")
                action_tool = parsed.get("action_tool", "finish")
                params = parsed.get("params", {})
                
                # 立即 yield thought
                yield {
                    "type": "thought",
                    "step": step_count,
                    "content": thought_content,
                    "reasoning": reasoning,
                    "action_tool": action_tool,
                    "params": params
                }
                
                # 判断是否结束
                if action_tool == "finish":
                    yield {
                        "type": "final",
                        "content": params.get("result", thought_content)
                    }
                    break
                
                # ========== Action 阶段 ==========
                self.status = AgentStatus.EXECUTING
                execution_result = await self.executor.execute(action_tool, params)
                
                # 立即 yield action_tool 结果
                yield {
                    "type": "action_tool",
                    "step": step_count,
                    "tool_name": action_tool,
                    "tool_params": params,
                    "execution_status": execution_result.get("status", "success"),
                    "summary": execution_result.get("summary", ""),
                    "raw_data": execution_result.get("data"),
                    "action_retry_count": execution_result.get("retry_count", 0)
                }
                
                # ========== Observation 阶段 ==========
                observation_text = f"Observation: {execution_result.get('status', 'unknown')} - {execution_result.get('summary', '')}"
                self._add_observation_to_history(observation_text)
                
                # 调用 LLM 获取下一个决策
                self.status = AgentStatus.OBSERVING
                llm_response = await self._get_llm_response()
                
                try:
                    parsed_obs = self.parser.parse_response(llm_response)
                except ValueError as e:
                    logger.error(f"Failed to parse observation LLM response: {e}")
                    parsed_obs = {"content": "无法解析LLM响应", "action_tool": "finish", "params": {}}
                
                is_finished = parsed_obs.get("action_tool") == "finish"
                
                # 立即 yield observation
                yield {
                    "type": "observation",
                    "step": step_count,
                    "obs_execution_status": execution_result.get("status", "success"),
                    "obs_summary": execution_result.get("summary", ""),
                    "obs_raw_data": execution_result.get("data"),
                    "content": parsed_obs.get("content", ""),
                    "obs_reasoning": parsed_obs.get("reasoning"),
                    "obs_action_tool": parsed_obs.get("action_tool", "finish"),
                    "obs_params": parsed_obs.get("params", {}),
                    "is_finished": is_finished
                }
                
                # 更新消息历史
                self.conversation_history.append({"role": "assistant", "content": thought_content})
                
                # 判断是否结束
                if is_finished:
                    yield {
                        "type": "final",
                        "content": parsed_obs.get("content", "任务已完成")
                    }
                    break
            
            # 超过最大步数
            if step_count >= max_steps:
                yield {
                    "type": "error",
                    "code": "MAX_STEPS_EXCEEDED",
                    "message": f"已达到最大迭代次数 {max_steps}"
                }
                
        except Exception as e:
            logger.error(f"Agent run_stream error: {e}", exc_info=True)
            yield {
                "type": "error",
                "code": "INTERNAL_ERROR",
                "message": str(e)
            }
        finally:
            # 关闭 session
            if self._session_created_by_agent and session_id and self.session_service:
                try:
                    self.session_service.complete_session(session_id, success=True)
                    logger.info(f"Session completed in run_stream: {session_id}")
                    self._session_created_by_agent = False
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

    async def ver1_run_stream(
        self,
        task: str,
        model: str,
        provider: str,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        max_steps: int = 100,
        step_start: int = 1  # 【小沈修复 2026-03-23】添加 step_start 参数，让调用方控制起始编号
    ) -> AsyncGenerator[str, None]:
        """
        【Phase4新增】异步流式执行 Agent，直接返回 SSE 格式字符串
        
        封装 run_stream()，将每个事件转换为 SSE 字符串，
        减少调用方（chat2.py）的重复代码。
        
        Args:
            task: 任务描述
            model: 模型名称（用于 final/error 响应）
            provider: 提供商（用于 final/error 响应）
            context: 额外上下文
            system_prompt: 自定义系统 prompt（可选）
            max_steps: 最大迭代次数
            step_start: 步骤起始编号（默认1），用于与调用方的 next_step() 统一编号
        
        Yields:
            SSE 格式的字符串
        """
        step_count = step_start - 1  # 【小沈修复 2026-03-23】使用 step_start 作为起始值
        
        async for event in self.run_stream(
            task=task,
            context=context,
            system_prompt=system_prompt,
            max_steps=max_steps
        ):
            event_type = event.get('type')
            step_count += 1
            
            if event_type == 'thought':
                yield format_thought_sse(
                    step=step_count,
                    content=event.get('content', ''),
                    reasoning=event.get('reasoning', ''),
                    action_tool=event.get('action_tool', ''),
                    params=event.get('params', {})
                )
            
            elif event_type == 'action_tool':
                yield format_action_tool_sse(
                    step=step_count,
                    tool_name=event.get('tool_name', ''),
                    tool_params=event.get('tool_params', {}),
                    execution_status=event.get('execution_status', 'success'),
                    summary=event.get('summary', ''),
                    raw_data=event.get('raw_data'),
                    action_retry_count=event.get('action_retry_count', 0)
                )
            
            elif event_type == 'observation':
                yield format_observation_sse(
                    step=step_count,
                    execution_status=event.get('execution_status', 'success'),
                    summary=event.get('summary', ''),
                    content=event.get('content', ''),
                    reasoning=event.get('reasoning', ''),
                    action_tool=event.get('action_tool', ''),
                    params=event.get('params', {}),
                    is_finished=event.get('is_finished', False),
                    raw_data=event.get('raw_data')
                )
            
            elif event_type == 'final':
                # 【小沈修复 2026-03-23】添加 step 参数，确保 final 也有 step 编号
                yield create_final_response(
                    content=event.get('content', ''),
                    model=model,
                    provider=provider,
                    display_name=f"{provider} ({model})",
                    step=step_count  # 【小沈修复 2026-03-23】添加 step 参数
                )
            
            elif event_type == 'error':
                # 【小沈修复 2026-03-23】添加 step 参数，确保 error 也有 step 编号
                yield create_error_response(
                    error_type="agent",
                    message=event.get('message', '未知错误'),
                    code=event.get('code', 'AGENT_ERROR'),
                    model=model,
                    provider=provider,
                    retryable=event.get('retryable', False),
                    step=step_count  # 【小沈修复 2026-03-23】添加 step 参数
                )