# -*- coding: utf-8 -*-
"""
Agent 核心基类 — 类骨架

从 base_react.py 拆出，遵循 SRP：
- run_stream / _initialize_run_state → 独立文件
- 本文件只保留 BaseAgent 类定义、__init__、抽象方法、Hook、委托方法

Author: 小沈 - 2026-03-25
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator, Set, Tuple

from app.services.agent.types import AgentStatus
from app.services.agent.steps import ReasoningStep, IncidentStep
from app.services.tools.tool_types import ToolCategory
from app.constants import MAX_CONTEXT_CHARS
from app.utils.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.mixins.react_handler_mixin import ReActHandlerMixin

from app.services.agent.base_react.agent_initializer import AgentInitializer
from app.services.agent.base_react.tool_manager import ToolManager
from app.services.agent.base_react.step_emitter import StepEmitter
from app.services.agent.base_react.run_stream import run_stream
from app.services.agent.base_react.initialize_run_state import initialize_run_state


class BaseAgent(ReActHandlerMixin, ABC):
    """Agent 核心基类 — 只保留骨架"""

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
        AgentInitializer._init_llm(self, llm_client, **kwargs)
        if max_steps is None:
            from app.config import get_config
            max_steps = get_config().get_max_steps()
        AgentInitializer._init_state(self, task_id, tool_category, max_steps)
        AgentInitializer._init_messages(self)
        self._tool_manager = ToolManager(self)
        self._tool_manager.init_tools()
        self._init_llm_strategies()
        AgentInitializer._init_task_tracking(self, enable=rollback_enabled)
        AgentInitializer._init_candidates(self, candidates)
        self._step_emitter = StepEmitter(self)

    def _init_llm_strategies(self):
        pass

    def _init_tools(self):
        self._tool_manager = ToolManager(self)
        self._tool_manager.init_tools()

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
        self._tool_manager.load_by_intent(intent_type, reason)

    run_stream = run_stream
    _initialize_run_state = initialize_run_state

    MAX_CONTEXT_CHARS = MAX_CONTEXT_CHARS

    def _emit_step(self, step) -> ReasoningStep:
        return self._step_emitter.emit(step)

    def _exit_with_error(self, step_count: int, error_type: str, error_message: str, recoverable: bool = False) -> ReasoningStep:
        return self._step_emitter.exit_with_error(step_count, error_type, error_message, recoverable)

    def _check_interrupt(self, step_count: int, running_tasks: Optional[Dict[str, Any]] = None) -> Optional[IncidentStep]:
        return self._step_emitter.check_interrupt(step_count, running_tasks)

    def _complete_tracked_task(self, success: bool):
        self._step_emitter.complete_task(success)

    def record_operation(self, operation_type: str, **kwargs):
        self._step_emitter.record_operation(operation_type, **kwargs)
