# -*- coding: utf-8 -*-
"""
Agent 核心基类 - 支持多工具分类

参考: 文档5.6节+7.5节完整代码

定义 ReAct 循环的核心逻辑，供所有 Agent 实现类继承。

【重构 2026-03-25】：
- 从 agent.py 提取核心逻辑
- base.py 是核心基准
- 子类继承并实现抽象方法

【重构 2026-04-17】：
- 步骤2.9：所有yield改为StepFactory调用
- 步骤2.10：添加步骤历史管理self.steps
- 步骤2.11：清理废弃的create_*_result函数

【Phase 1修复 2026-04-26 小沈】：
- 添加 llm_client, session_id 参数
- 添加 _load_tools 方法从 registry 加载工具

Author: 小沈 - 2026-03-25
Updated: 小沈 - 2026-04-26
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator, Callable, Set, Tuple

from app.services.agent.types import AgentStatus
from app.services.agent.llm_response_parser import parse_react_response
from app.services.agent.message_builder import MessageBuilder
from app.services.agent.reasoning_steps import (
    StepFactory,
    ReasoningStep,
)
from app.services.tools.tool_types import ToolCategory
from app.services.tools.tool_queries import get_tools_from_registry_by_category

from app.constants import MAX_CONTEXT_CHARS
from app.services.preprocessing.intent_classifier import IntentClassifier
from app.utils.logger import logger
from app.chat_stream.incident_handler import create_incident_data
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.mixins.react_handler_mixin import ReActHandlerMixin



# ===== 全局默认值常量 =====
# 原则：config.yaml > 代码常量 > 硬编码默认值
# react_sse_wrapper.py 从 config.yaml 读取后传入
DEFAULT_MAX_STEPS = 100
# 连续chunk最大次数-达到此阈值且为工具Agent时提升为implicit退出循环
# chat Agent（无工具）首个chunk即退出，不受此限制
MAX_CONSECUTIVE_CHUNKS = 5


class BaseAgent(ReActHandlerMixin, ABC):
    """
    Agent 核心基类 - 支持多工具分类
    
    参考: 文档5.6节+7.5节完整代码
    
    定义 ReAct (Thought-Action-Observation) 循环的核心逻辑
    子类需要实现抽象方法
    """
    
    def __init__(
        self,
        llm_client: Any,
        task_id: str,  # 【修改】session_id → task_id，2026-04-26 小沈
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        **kwargs
    ):
        """
        初始化 BaseAgent
        参考: 5.1节行 503-534

        Args:
            llm_client: LLM 客户端函数
            task_id: 任务ID - 用于操作安全追踪和审计（必需，不可为空字符串）
            tool_category: 工具分类（可选，用于加载特定工具集）
            max_steps: 最大步数（默认 DEFAULT_MAX_STEPS=100，优先从 config.yaml 读取）
        """
        # 初始化编排 - 按职责分组调用私有方法
        self._init_llm(llm_client, **kwargs)
        self._init_state(task_id, tool_category, max_steps)
        self._init_messages()
        self._init_tools()
    
    def _init_llm(self, llm_client: Any, **kwargs):
        """初始化LLM客户端相关属性 - 提取自__init__的LLM职责部分"""
        self.llm_client = llm_client
        
        # 【修复 2026-04-30 小沈】将 **kwargs 中有用的参数 setattr 到 self
        # 之前 **kwargs 被静默忽略，导致 model/provider/api_base/api_key 丢失
        # 这些属性被 prompt_logger 和 llm_adapter 等使用
        _ALLOWED_KWARGS = {'model', 'provider', 'api_base', 'api_key'}
        for key, value in kwargs.items():
            if key in _ALLOWED_KWARGS:
                setattr(self, key, value)
    
    def _init_state(self, task_id: str, tool_category: Optional[ToolCategory], max_steps: int):
        """初始化状态管理相关属性 - 提取自__init__的状态管理职责部分"""
        self.task_id = task_id  # 赋值task_id
        self.tool_category = tool_category
        self.max_steps = max_steps
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0
        self._lock = asyncio.Lock()
        
        # 【重构 2026-05-27 小健】2.22：parse/empty重试委托给RetryEngine
        from app.utils.retry_engine import RetryEngine, BackoffStrategy
        self._parse_retry_engine = RetryEngine(
            max_retries=3, backoff_strategy=BackoffStrategy.EXPONENTIAL, backoff_factor=2.0)
        self._empty_response_retry_engine = RetryEngine(
            max_retries=2, backoff_strategy=BackoffStrategy.FIXED, backoff_factor=1.0)
        
        self.parse_retry_count = 0
        self.max_parse_retries = 3
        
        # 【v2.3新增】chunk处理相关属性—所有Agent子类共享
        self.max_consecutive_chunks = MAX_CONSECUTIVE_CHUNKS  # 连续chunk达此阈值时提升为implicit
    

    
    def _init_messages(self):
        """初始化消息构建相关属性 - 提取自__init__的消息构建职责部分"""
        # 【步骤2.10】步骤历史管理：使用ReasoningStep类型
        self.steps: List[ReasoningStep] = []
        self.message_builder = MessageBuilder(max_context_chars=self.MAX_CONTEXT_CHARS)
    
    def _init_tools(self):
        """初始化工具相关属性 - 提取自__init__的工具职责部分"""
        # 【修复 小健 2026-05-24】P2-8: _load_tools移到子类_init_tools_and_executor统一调用，避免重复初始化
        self._tools_dict = {}
        self._loaded_categories = set()
        if self.tool_category:
            self._loaded_categories.add(self.tool_category.value)
        self._intent_classifier = IntentClassifier()
        
        # 创建工具执行器
        self.executor = None  # 子类应初始化
        
    
    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        """@property透传至MessageBuilder — 小沈 2026-05-21"""
        return self.message_builder.conversation_history
    
    @conversation_history.setter
    def conversation_history(self, value: List[Dict[str, str]]) -> None:
        """@property setter — 小沈 2026-05-21"""
        self.message_builder.conversation_history = value
    
    # ===== 抽象方法（子类必须实现）=====
    
    @abstractmethod
    async def _get_llm_response(self) -> str:
        """
        获取 LLM 响应
        
        子类实现：调用具体的 LLM 客户端
        """
        pass
    
    @abstractmethod
    async def _execute_tool(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具
        
        子类实现：调用具体的工具执行器
        """
        pass
    
    @abstractmethod
    def _get_system_prompt(self) -> str:
        """
        获取系统 Prompt
        
        子类实现：返回具体的系统提示
        """
        pass
    
    @abstractmethod
    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        获取任务 Prompt
        
        子类实现：返回具体的任务提示
        """
        pass
    
    # ===== 可扩展 Hook 方法（子类可覆盖）=====
    
    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]]):
        """
        Session 初始化 Hook
        子类可覆盖：做 session 相关的初始化
        """
        pass
    
    def _on_before_loop(self, sys_prompt: str, task_prompt: str, context: Optional[Dict[str, Any]] = None):
        """
        循环开始前 Hook
        
        子类可覆盖：做 prompt 日志等
        
        【修复 2026-04-30 小沈】添加 context 参数，与子类 FileReactAgent 签名一致
        """
        pass
    
    def _on_after_loop(self):
        """
        循环结束后 Hook
        
        子类可覆盖：做 session 关闭等
        """
        pass
    
    # ===== 步骤9：动态加载工具相关方法（文档4.14节）=====
    
    def load_tools_by_intent(self, intent_type: str, reason: str = ""):
        """
        动态加载某个意图的工具
        
        参考：文档4.14节步骤9代码示例
        
        Args:
            intent_type: 意图类型（file/system/network/desktop/document）
            reason: 加载原因（用于日志）
        """
        if intent_type in self._loaded_categories:
            return  # 已加载
        
        logger.info(f"[动态加载] 原因: {reason}，加载意图: {intent_type}")
        
        # 1. 获取该意图的工具 - 【2026-05-18 小沈】
        from app.services.intents.intent_mapper import resolve_category
        category = resolve_category(intent_type)
        if not category:
            logger.warning(f"[动态加载] 意图'{intent_type}'无对应工具分类")
            return
        new_tools = get_tools_from_registry_by_category(category)
        
        # 2. 添加到_tools_dict
        self._tools_dict.update(new_tools)
        self._loaded_categories.add(category.value)

        # 【修复 N4 小沈 2026-05-15】不再注入load_hint，依赖下一轮detail自动包含新分类
        new_tool_names = sorted(new_tools.keys())
        logger.info(f"[动态加载] 已加载{intent_type}分类的{len(new_tool_names)}个工具，下一轮detail将自动包含")

        # 3. 刷新FC通道的tools定义（如果已启用）
        # 【修复 问题2+9 小沈 2026-05-15】增加openai_tools存在性检查
        if hasattr(self, 'tools_strategy') and self.tools_strategy is not None and hasattr(self, 'openai_tools') and self.openai_tools:
            from app.services.tools.registry import tool_registry
            new_openai_tools = tool_registry.to_openai_tools(category=category)
            self.openai_tools.extend([t for t in new_openai_tools if t not in self.openai_tools])
            self.tools_strategy.tools = self.openai_tools
            logger.info(f"[FC刷新] tools定义已更新，当前{len(self.openai_tools)}个")

        # 【修复 小健 2026-05-24】P2-9: 用try/except替代hasattr+delattr，消除TOCTOU风险
        for _attr in ('_cached_schema_text', '_cached_tools_content', '_last_injected_categories'):
            try:
                delattr(self, _attr)
            except AttributeError:
                pass

        logger.info(f"[动态加载] 完成，新增{len(new_tools)}个工具，总计{len(self._tools_dict)}个")
    
    # ===== 核心方法（子类调用）=====
    
    async def run_stream(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
        task_id: Optional[str] = None,
        running_tasks: Optional[Dict[str, Any]] = None,
        step_counter: Optional[Callable[[], int]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """ReAct 核心循环 — 重构为骨架+私有方法分发 — 小沈 2026-05-25"""
        chunk_buffer, valid_tool_names = self._initialize_run_state(task, task_id, context)
        step_count = 0

        try:
            while True:
                if step_count >= max_steps:
                    yield self._exit_with_error(step_count, "max_steps_exceeded", f"已达到最大迭代次数 {max_steps}")
                    self._on_after_loop()
                    return

                step_count = step_counter() if step_counter else (step_count + 1)

                _int = self._check_interrupt(step_count, running_tasks)
                if _int:
                    if task_id and running_tasks:
                        _crt = running_tasks.get(task_id, {}).get("cancel_request_time")
                        if _crt:
                            logger.info(f"[InterruptCheck] 任务 {task_id} 延迟: {(time.time() - _crt) * 1000:.0f}ms")
                    yield _int
                    self._on_after_loop()
                    return

                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()

                _int = self._check_interrupt(step_count, running_tasks)
                if _int:
                    yield _int
                    self._on_after_loop()
                    return

                if not response:
                    self._empty_response_retry_engine.record_attempt()
                    self.parse_retry_count = 0
                    async for step in self._handle_empty_response(step_count):
                        yield step
                    continue

                self._empty_response_retry_engine.reset_attempts()
                parsed = parse_react_response(response)
                parsed_type = parsed["type"]

                if parsed_type == "chunk":
                    async for step in self._handle_chunk_type(parsed, step_count, chunk_buffer, step_counter):
                        yield step
                    continue

                if parsed_type in ("answer", "implicit"):
                    async for step in self._handle_completion_type(parsed, step_count, chunk_buffer):
                        yield step
                    self._on_after_loop()
                    return

                if parsed_type == "thought_only":
                    async for step in self._handle_thought_only(parsed, step_count, chunk_buffer):
                        yield step
                    continue

                thought_content = parsed.get("content", "")
                tool_name = parsed.get("tool_name") or parsed.get("action_tool")
                tool_params = parsed.get("tool_params", parsed.get("params", {}))

                if parsed_type != "parse_error":
                    if not tool_name or tool_name not in valid_tool_names:
                        parsed = {"type": "parse_error", "error": f"LLM返回无效工具名: {tool_name!r}"}
                        parsed_type = "parse_error"

                if parsed_type == "parse_error":
                    async for step in self._handle_parse_error(parsed, step_count, chunk_buffer):
                        yield step
                    continue

                async for step in self._handle_action_type(
                    parsed, step_count, chunk_buffer, valid_tool_names,
                    running_tasks, task_id, step_counter, response
                ):
                    yield step

        except Exception as e:
            yield self._handle_run_exception(e, step_count)
            self._on_after_loop()
            return

    def _initialize_run_state(
        self, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
    ) -> Tuple[ChunkBuffer, Set[str]]:
        """初始化运行状态，返回(chunk_buffer, valid_tool_names) — 小沈 2026-05-25"""
        self.steps = []
        self.message_builder.reset_per_run()
        self.conversation_history = self.message_builder.conversation_history
        self.status = AgentStatus.THINKING
        self.llm_call_count = 0
        if task_id:
            self.task_id = task_id

        self._on_session_init(task, context)
        sys_prompt = self._get_system_prompt()
        task_prompt = self._get_task_prompt(task, context)
        self._on_before_loop(sys_prompt, task_prompt, context)
        self.message_builder.init_history(sys_prompt, task_prompt)
        self.conversation_history = self.message_builder.conversation_history

        chunk_buffer = ChunkBuffer(self.max_consecutive_chunks)
        valid_tool_names: Set[str] = {"finish"}
        try:
            from app.services.tools.registry import tool_registry
            valid_tool_names = {t["name"] for t in tool_registry.list_tools()} | {"finish"}
        except Exception as _e:
            logger.debug(f"[工具名验证] 获取工具列表失败: {_e}, 仅允许finish")

        return chunk_buffer, valid_tool_names

    
    # ===== 对话历史管理 =====

    MAX_CONTEXT_CHARS = MAX_CONTEXT_CHARS  # from app.constants — 小健 2026-05-24

    # ===== 通用方法 =====

    def _emit_step(self, step) -> dict:
        """记录步骤并返回yield用的dict — 小健 2026-05-24
        
        统一 self.steps.append(step) + step.to_dict() 两步操作。
        调用方: step_dict = self._emit_step(step); yield step_dict
        """
        self.steps.append(step)
        return step.to_dict()

    def _exit_with_error(self, step_count: int, error_type: str, error_message: str, recoverable: bool = False) -> dict:
        """创建error_step并返回yield用的dict，同时设置FAILED状态 — 小健 2026-05-24
        
        统一 error_step创建 + append + status设置。
        调用方: yield self._exit_with_error(...); self._on_after_loop(); return
        """
        self.status = AgentStatus.FAILED
        error_step = StepFactory.create_error_step(
            step=step_count,
            error_type=error_type,
            error_message=error_message,
            recoverable=recoverable
        )
        return self._emit_step(error_step)

    def _check_interrupt(self, step_count: int, running_tasks: Optional[Dict[str, Any]] = None) -> Optional[dict]:
        """检查任务是否被中断，若中断返回interrupted_data的dict — 小健 2026-05-24
        
        统一4处中断检查逻辑。直接读取cancelled标志（非线程安全但可接受，
        因为只是检查布尔值，与loop中现有模式一致）。
        调用方: _int = self._check_interrupt(step_count, running_tasks); 
               if _int: yield _int; self._on_after_loop(); return
        """
        task_id = getattr(self, '_task_id', None) or getattr(self, 'task_id', None)
        if not task_id or not running_tasks:
            return None
        task_data = running_tasks.get(task_id, {})
        if task_data.get("cancelled", False):
            return create_incident_data(
                incident_value='interrupted',
                message='用户取消了任务',
                step=step_count
            )
        return None


