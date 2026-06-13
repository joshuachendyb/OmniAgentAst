# -*- coding: utf-8 -*-
"""
Agent 核心基类 — 类骨架

遵循 SRP: 只保留 BaseAgent 类定义、__init__、抽象方法、Hook、委托方法
run_react_cycle / initialize_run_state → 独立文件

Author: 小沈 - 2026-03-25
P3-12: 删除run_react_cycle纯委托，改为混合类方式 — 小沈 2026-06-09
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, AsyncGenerator, Set, Tuple

from app.services.agent.types import AgentStatus
from app.services.agent.steps import ReasoningStep

from app.constants import MAX_CONTEXT_CHARS
from app.utils.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer

from app.services.agent.core_agent.agent_initializer import AgentInitializer
from app.services.agent.core_agent.tool_manager import ToolManager
from app.services.agent.core_agent.step_emitter import StepEmitter
from app.services.agent.tool_retry_engine import ToolRetryEngine


class BaseAgent(ABC):
    """Agent 核心基类 — 只保留骨架"""

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        max_steps: Optional[int] = None,
        initial_categories=None,
        **kwargs
    ):
        AgentInitializer._init_llm(self, llm_client, **kwargs)
        if max_steps is None:
            from app.config import get_config
            max_steps = get_config().get_max_steps()
        AgentInitializer._init_state(self, task_id, max_steps)
        AgentInitializer._init_messages(self)
        self._tool_manager = ToolManager(self)
        self._tool_manager.init_tools(initial_categories=initial_categories)
        self._retry_engine = ToolRetryEngine(self._tools_dict)
        AgentInitializer._init_task_tracking(self, enable=True)
        self._step_emitter = StepEmitter(self)

    def record_operation(self, operation_type: str, **kwargs):
        self._step_emitter.record_operation(operation_type, **kwargs)

    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]] = None):
        """生命周期Hook: ReAct循环开始前 — 子类可override"""
        pass

    def _on_before_loop(self, sys_prompt: str, task: str, context: Optional[Dict[str, Any]] = None):
        """生命周期Hook: 构建sys_prompt后,循环开始前 — 子类可override"""
        pass

    def _on_after_loop(self):
        """生命周期Hook: ReAct循环结束后 — 子类可override"""
        pass

    def _create_cancelled_chunk(self):
        """创建取消chunk — 直接使用stream_parser函数
         【修复P2-6】移除对llm_client私有方法的依赖 — 北京老陈 2026-06-13
        """
        from app.services.llm.stream_parser import create_cancelled_chunk
        return create_cancelled_chunk(getattr(self, 'model', 'unknown'))

    async def run_react_cycle(self, task, context=None, max_steps=None, task_id=None):
        """直接从模块导入 — 小沈 2026-06-09 替代纯委托"""
        from app.services.agent.core_agent.react_cycle import run_react_cycle as _run
        async for event in _run(self, task, context, max_steps, task_id):
            yield event
