# -*- coding: utf-8 -*-
"""
Agent 核心基类

Author: 小沈 - 2026-03-25
Updated: 小欧 - 2026-06-07 (合并 agent_initializer / tool_manager / step_emitter / run_stream / initialize_run_state)
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator, Set, Tuple

from app.services.agent.types import AgentStatus
from app.services.agent.steps import ReasoningStep, StepFactory
from app.services.agent.llm_response_parser import parse_react_response
from app.services.tools.tool_types import ToolCategory
from app.services.tools.tool_queries import get_tools_from_registry_by_category
from app.constants import MAX_CONTEXT_CHARS, META_TOOL_NAMES
from app.utils.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.mixins.react_handler_mixin import ReActHandlerMixin
from app.services.agent.message_builder import MessageBuilder


class BaseAgent(ReActHandlerMixin, ABC):
    """Agent 核心基类"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: Optional[int] = None,
        rollback_enabled: bool = True,
        candidates: Optional[List[str]] = None,
        **kwargs
    ):
        self.llm_client = llm_client

        if max_steps is None:
            from app.config import get_config
            max_steps = get_config().get_max_steps()
        self.task_id = task_id
        self.tool_category = tool_category
        self.max_steps = max_steps
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0
        self._lock = asyncio.Lock()

        from app.utils.retry import create_agent_retry_engine
        self._parse_retry_engine, self._empty_response_retry_engine = create_agent_retry_engine()

        from app.constants import MAX_CONSECUTIVE_CHUNKS
        self.max_consecutive_chunks = MAX_CONSECUTIVE_CHUNKS

        self.steps: List[ReasoningStep] = []
        self.message_builder = MessageBuilder(max_context_chars=MAX_CONTEXT_CHARS)

        self._init_tools()
        self._init_llm_strategies()

        self._task_tracker = None
        self._tracked_task_id = None
        if rollback_enabled:
            try:
                from app.services.task import get_tracker
                intent = getattr(self, '_intent', None) or self.tool_category.value if self.tool_category else "unknown"
                tracker = get_tracker()
                self._tracked_task_id = tracker.create_task(
                    intent=intent,
                    agent_id=task_id,
                    description="",
                )
                self._task_tracker = tracker
            except (ImportError, AttributeError) as e:
                logger.debug(f"[TaskTracker] 创建任务失败: {e}")

        self._candidates = candidates or []

    def _init_llm_strategies(self):
        pass

    def _init_tools(self):
        self._tools_dict = {}
        self._loaded_categories: Set[str] = set()
        if self.tool_category:
            self._loaded_categories.add(self.tool_category.value)
        meta_tools = self._load_tools_by_names(META_TOOL_NAMES)
        self._tools_dict.update(meta_tools)
        self._init_tools_and_executor(self.tool_category)

    async def _execute_tool(self, action: str, action_input: Dict[str, Any]) -> Dict[str, Any]:
        from app.services.agent.tool_executor import execute_tool_with_unified_retry
        return await execute_tool_with_unified_retry(action, action_input, self._tools_dict)

    @property
    def conversation_history(self) -> List[Dict[str, str]]:
        return self.message_builder.conversation_history

    @conversation_history.setter
    def conversation_history(self, value: List[Dict[str, str]]) -> None:
        self.message_builder.conversation_history = value

    async def _get_llm_response(self) -> str:
        return await self._call_llm()

    @abstractmethod
    def _get_system_prompt(self) -> str:
        pass

    @abstractmethod
    def _get_task_prompt(self, task: str, context: Optional[Dict[str, Any]] = None) -> str:
        pass

    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]]):
        pass

    def _on_before_loop(self, sys_prompt: str, task_prompt: str, context: Optional[Dict[str, Any]] = None):
        pass

    def _on_after_loop(self):
        pass

    def load_tools_by_intent(self, intent_type: str, reason: str = ""):
        if intent_type in self._loaded_categories:
            return
        logger.info(f"[动态加载] 原因: {reason}，加载意图: {intent_type}")
        from app.services.intents.intent_mapper import resolve_category
        category = resolve_category(intent_type)
        if not category:
            logger.warning(f"[动态加载] 意图'{intent_type}'无对应工具分类")
            return
        new_tools = get_tools_from_registry_by_category(category)
        self._tools_dict.update(new_tools)
        self._loaded_categories.add(category.value)
        new_tool_names = sorted(new_tools.keys())
        logger.info(f"[动态加载] 已加载{intent_type}分类的{len(new_tool_names)}个工具，下一轮detail将自动包含")
        if hasattr(self, 'tools_strategy') and self.tools_strategy is not None and hasattr(self, 'openai_tools') and self.openai_tools:
            from app.services.tools.registry import tool_registry
            new_openai_tools = tool_registry.to_openai_tools(category=category)
            self.openai_tools.extend([t for t in new_openai_tools if t not in self.openai_tools])
            self.tools_strategy.tools = self.openai_tools
            logger.info(f"[FC刷新] tools定义已更新，当前{len(self.openai_tools)}个")
        for _attr in ('_cached_schema_text', '_cached_tools_content', '_last_injected_categories'):
            try:
                delattr(self, _attr)
            except AttributeError:
                pass
        logger.info(f"[动态加载] 完成，新增{len(new_tools)}个工具，总计{len(self._tools_dict)}个")

    def _emit_step(self, step) -> ReasoningStep:
        self.steps.append(step)
        return step

    def _exit_with_error(self, step_count: int, error_type: str, error_message: str, recoverable: bool = False) -> ReasoningStep:
        self.status = AgentStatus.FAILED
        error_step = StepFactory.create_error_step(
            step=step_count, error_type=error_type,
            error_message=error_message, recoverable=recoverable,
        )
        return self._emit_step(error_step)

    def _complete_tracked_task(self, success: bool):
        if self._task_tracker and self._tracked_task_id:
            try:
                self._task_tracker.complete_task(self._tracked_task_id, success=success)
            except (AttributeError, TypeError) as e:
                logger.debug(f"[TaskTracker] 完成任务失败: {e}")

    def record_operation(self, operation_type: str, **kwargs):
        if self._task_tracker and self._tracked_task_id:
            try:
                self._task_tracker.add_operation(self._tracked_task_id, operation_type, **kwargs)
            except (AttributeError, TypeError) as e:
                logger.debug(f"[TaskTracker] 记录操作失败: {e}")

    def _initialize_run_state(
        self, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
    ) -> Tuple[ChunkBuffer, Set[str]]:
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
        except (ImportError, AttributeError) as e:
            logger.debug(f"[工具名验证] 获取工具列表失败: {e}, 仅允许finish")

        self._task_tracker = None
        self._tracked_task_id = None
        try:
            from app.services.task import get_tracker
            intent = getattr(self, '_intent', None) or (self.tool_category.value if self.tool_category else "unknown")
            tracker = get_tracker()
            self._tracked_task_id = tracker.create_task(
                intent=intent, agent_id=self.task_id, description=task[:200],
            )
            self._task_tracker = tracker
        except (ImportError, AttributeError) as e:
            logger.debug(f"[TaskTracker] 创建任务失败: {e}")

        return chunk_buffer, valid_tool_names

    async def run_stream(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
        max_steps: Optional[int] = None,
        task_id: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if max_steps is None:
            from app.config import get_config
            max_steps = get_config().get_max_steps()
        chunk_buffer, valid_tool_names = self._initialize_run_state(task, task_id, context)
        step_count = 0

        try:
            while True:
                if step_count >= max_steps:
                    yield self._exit_with_error(step_count, "max_steps_exceeded", f"已达到最大迭代次数 {max_steps}")
                    self._complete_tracked_task(success=False)
                    self._on_after_loop()
                    return

                step_count += 1
                self.status = AgentStatus.THINKING
                response = await self._get_llm_response()

                if not response:
                    self._empty_response_retry_engine.record_attempt()
                    self._parse_retry_engine.reset_attempts()
                    async for step in self._handle_empty_response(step_count):
                        yield step
                    continue

                self._empty_response_retry_engine.reset_attempts()
                parsed = parse_react_response(response)
                parsed_type = parsed["type"]

                if parsed_type == "chunk":
                    async for step in self._handle_chunk_type(parsed, step_count, chunk_buffer):
                        yield step
                    if self.status == AgentStatus.COMPLETED:
                        self._complete_tracked_task(success=True)
                        return
                    continue

                if parsed_type in ("answer", "implicit"):
                    async for step in self._handle_completion_type(parsed, step_count, chunk_buffer):
                        yield step
                    self._complete_tracked_task(success=True)
                    self._on_after_loop()
                    return

                if parsed_type == "thought_only":
                    async for step in self._handle_thought_only(parsed, step_count, chunk_buffer):
                        yield step
                    continue

                thought_content = parsed.get("content", "")
                tool_name = parsed.get("tool_name")
                tool_params = parsed.get("tool_params", {})

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
                    task_id, response
                ):
                    yield step

        except Exception as e:
            yield self._handle_run_exception(e, step_count)
            self._complete_tracked_task(success=False)
            self._on_after_loop()
            return

    MAX_CONTEXT_CHARS = MAX_CONTEXT_CHARS
