# -*- coding: utf-8 -*-
"""
FileReactAgent - 文件操作 ReAct Agent

继承 BaseAgent，专用于文件操作场景的 ReAct 智能体。
从 agent.py 复制，删除 intent-type 分支后改造。

【重构 Phase 4 - 2026-03-26 小沈】：
- 从 agent.py 复制，采用"复制+删除法"改造
- 删除 intent-type 分支（network/desktop）
- 保留文件操作专用逻辑（session管理、prompts、rollback）

【TODO 待清理 - 2026-03-26 小健检查发现】：
- intent_registry 和 preprocessor 对象仍保留在代码中（第121-125行）
- run_stream 方法中仍有意图识别调用（第389-404行）
- FileReactAgent 是专用 Agent，这些逻辑应该在路由层处理
- 后续应删除这些冗余代码（待实现）

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
from app.services.intent import IntentRegistry, Intent
from app.services.preprocessing import PreprocessingPipeline
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
                "generate_report": self.file_tools.generate_report,
            }
            self.executor = ToolExecutor(self._tools_dict)
            
            self.prompts = FileOperationPrompts()
            
            logger.info(f"FileReactAgent initialized (session: {session_id})")
        else:
            # FileReactAgent 只支持 file 意图
            raise ValueError(f"FileReactAgent only supports intent_type='file', got: {intent_type}")
        
        # 意图注册表（用于意图识别）
        self.intent_registry = IntentRegistry()
        self._register_default_intents()
        
        # 预处理流水线（用于意图识别）
        self.preprocessor = PreprocessingPipeline()
        
        # 【新增】LLM调用策略
        self.text_strategy = TextStrategy()
        self.tools_strategy = ToolsStrategy(tools=tools or [])
        self.response_format_strategy = ResponseFormatStrategy()
        
        # Function Calling 支持
        self.tools = tools or []
        
        # LLMAdapter 自适应探测
        self.adapter = None  # 【小沈修复 2026-03-23】确保 adapter 属性存在
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
        # file 意图（FileReactAgent 只支持 file 意图）
        file_intent = Intent(
            name="file",
            description="文件读写、目录管理、文件搜索",
            keywords=["文件", "读取", "写入", "删除", "移动", "目录", "搜索", "创建"],
            tools=["read_file", "write_file", "list_directory", "delete_file", "move_file", "search_files", "generate_report"],
            safety_checker="file_safety"
        )
        self.intent_registry.register(file_intent)
        
        logger.info(f"Registered {len(self.intent_registry.list_all())} intents")
    
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
        """循环开始前 Hook - 记录 Prompt 日志"""
        from datetime import datetime
        prompt_logger = get_prompt_logger()
        prompt_logger.start_request(
            user_message=task_prompt,
            user_message_id=f"msg_{self.session_id}_{datetime.now().strftime('%H%M%S')}",
            session_id=self.session_id
        )
        prompt_logger.log_system_prompt(
            step_name="系统Prompt生成",
            prompt_content=sys_prompt,
            source="file_prompts.py:get_system_prompt()"
        )
        prompt_logger.log_task_prompt(
            task_content=task_prompt,
            context=context
        )
    
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
        get_next_step: Optional[Callable[[], int]] = None  # 【小沈修复 2026-03-23】传入统一的 step 计数函数
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
            get_next_step: 统一的 step 计数函数（与调用方共用）
        
        Yields:
            SSE 格式的字符串
        """
        # 【小沈修复 2026-03-23】使用调用方传入的 get_next_step 函数
        if get_next_step is None:
            raise ValueError("get_next_step function is required")
        
        # 将 system_prompt 存入 self，供父类 hook 使用
        self._custom_system_prompt = system_prompt
        
        async for event in self.run_stream(
            task=task,
            context=context,
            max_steps=max_steps
        ):
            event_type = event.get('type')
            step = get_next_step()  # 【小沈修复 2026-03-23】使用统一计数器
            
            if event_type == 'thought':
                yield format_thought_sse(
                    step=step,
                    content=event.get('content', ''),
                    reasoning=event.get('reasoning', ''),
                    action_tool=event.get('action_tool', ''),
                    params=event.get('params', {})
                )
            
            elif event_type == 'action_tool':
                yield format_action_tool_sse(
                    step=step,
                    tool_name=event.get('tool_name', ''),
                    tool_params=event.get('tool_params', {}),
                    execution_status=event.get('execution_status', 'success'),
                    summary=event.get('summary', ''),
                    raw_data=event.get('raw_data'),
                    action_retry_count=event.get('action_retry_count', 0)
                )
            
            elif event_type == 'observation':
                yield format_observation_sse(
                    step=step,
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
                yield create_final_response(
                    content=event.get('content', ''),
                    model=model,
                    provider=provider,
                    display_name=f"{provider} ({model})",
                    step=step
                )
            
            elif event_type == 'error':
                yield create_error_response(
                    error_type="agent",
                    message=event.get('message', '未知错误'),
                    code=event.get('code', 'AGENT_ERROR'),
                    model=model,
                    provider=provider,
                    retryable=event.get('retryable', False),
                    step=step
                )