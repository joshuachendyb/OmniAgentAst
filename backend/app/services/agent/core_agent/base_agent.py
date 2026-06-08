# -*- coding: utf-8 -*-
"""
Agent 核心基类 — 类骨架

从 base_react.py 拆出,遵循 SRP:
 - run_react_cycle / _initialize_run_state → 独立文件
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

from app.services.agent.core_agent.agent_initializer import AgentInitializer
from app.services.agent.core_agent.tool_manager import ToolManager
from app.services.agent.core_agent.step_emitter import StepEmitter
from app.services.agent.core_agent.react_cycle import run_react_cycle
from app.services.agent.core_agent.initialize_run_state import initialize_run_state
from app.services.agent.tool_retry_engine import ToolRetryEngine


class BaseAgent(ABC):
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
        self._retry_engine = ToolRetryEngine(self._tools_dict)
        AgentInitializer._init_task_tracking(self, enable=rollback_enabled)
        AgentInitializer._init_candidates(self, candidates)
        self._step_emitter = StepEmitter(self)

    def record_operation(self, operation_type: str, **kwargs):
        self._step_emitter.record_operation(operation_type, **kwargs)

    def _create_cancelled_chunk(self):
        """创建取消chunk — 委托给llm_client
         小健 - 2026-06-08 修复P0: run_react_cycle需要此方法
        """
        if hasattr(self, 'llm_client') and self.llm_client:
            return self.llm_client._create_cancelled_chunk()
        from app.services.llm.stream_parser import create_cancelled_chunk
        return create_cancelled_chunk(getattr(self, 'model', 'unknown'))

    # P2-16: 猴子补丁 → 正常方法 — 小欧 2026-06-08
    run_react_cycle = run_react_cycle
