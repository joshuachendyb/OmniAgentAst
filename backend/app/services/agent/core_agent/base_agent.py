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

from app.services.agent.core_agent.status_table import AgentStatus
from app.services.agent.steps import ReasoningStep

from app.config import get_config
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.message_builder import MessageBuilder

from app.services.agent.core_agent.step_emitter import StepEmitter
from app.services.agent.tool_retry_engine import ToolRetryEngine
from app.services.agent.core_agent.react_cycle import run_react_cycle as _run


class BaseAgent(ABC):
    """Agent 核心基类 — 小沈 2026-03-25"""
    _ALLOWED_KWARGS = {'model', 'provider', 'api_base', 'api_key'}

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        max_steps: Optional[int] = None,
        initial_categories=None,
        **kwargs
    ):
        # 原 AgentInitializer._init_llm
        self.llm_client = llm_client
        for key, value in kwargs.items():
            if key in self._ALLOWED_KWARGS:
                setattr(self, key, value)

        if max_steps is None:
            max_steps = get_config().get_max_steps()

        # 原 AgentInitializer._init_state
        self.task_id = task_id
        self.max_steps = max_steps
        self.status = AgentStatus.IDLE
        self.llm_call_count = 0

        # 原 AgentInitializer._init_messages
        self.steps: List[ReasoningStep] = []
        self.message_builder = MessageBuilder(max_context_chars=get_config().get_max_context_chars())

        self._loaded_categories: Set = set(initial_categories or [])
        self._tool_loader = ToolLoader(self)
        self._tool_loader.init_tools(initial_categories=initial_categories)
        self._retry_engine = ToolRetryEngine(self._tools_dict)

        # 原 AgentInitializer._init_task_tracking
        self._task_tracker = None
        self._tracked_task_id = None
        try:
            from app.services.task import get_tracker
            tracker = get_tracker()
            self._tracked_task_id = tracker.create_task(
                agent_id=self.__class__.__name__,
                description="",
            )
            self._task_tracker = tracker
        except Exception as _e:
            logger.debug(f"[TaskTracker] 创建任务失败: {_e}")

        self._step_emitter = StepEmitter(self)

    def record_operation(self, operation_type: str, *, status: Optional[str] = None, **kwargs):
        self._step_emitter.record_operation(operation_type, status=status, **kwargs)

    def _on_session_init(self, task: str, context: Optional[Dict[str, Any]] = None):
        """生命周期Hook: ReAct循环开始前 — 子类可override"""
        pass

    def _on_before_loop(self, sys_prompt: str, task: str, context: Optional[Dict[str, Any]] = None):
        """生命周期Hook: 构建sys_prompt后,循环开始前 — 子类可override"""
        pass

    def _on_after_loop(self):
        """生命周期Hook: ReAct循环结束后 — 子类可override"""
        pass

    # set_failed/set_completed/set_cancelled 方法已删除，统一使用 status_table.py 中的函数
    # chendyg 2026-07-01: 删除这三个方法，强制使用 status_table.set_failed/set_completed/set_cancelled

    def _create_cancelled_chunk(self):
        """创建取消chunk — 直接使用stream_parser函数
         【修复P2-6】移除对llm_client私有方法的依赖 — 北京老陈 2026-06-13
        """
        from app.services.llm.core import create_cancelled_chunk
        return create_cancelled_chunk(getattr(self, 'model', 'unknown'))

    async def run_react_cycle(self, task, context=None, max_steps=None, task_id=None):
        """直接从模块导入 — 小沈 2026-06-09 替代纯委托"""
        async for event in _run(self, task, context, max_steps, task_id):
            yield event


class ToolLoader:
    """工具加载和管理 — 小沈 2026-06-17 改名ToolManager→ToolLoader"""

    def __init__(self, agent):
        self.agent = agent

    def init_tools(self, initial_categories=None):
        """初始化工具,按分类注入工具给LLM"""
        self.agent._tools_dict = {}
        categories_to_load = initial_categories or list(ToolCategory)
        for cat in categories_to_load:
            cat_tools = tool_registry.get_implementations_by_category(cat)
            self.agent._tools_dict.update(cat_tools)
        logger.info(f"[ToolLoader] 初始化完成,共{len(self.agent._tools_dict)}个工具")

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict

    def load_category(self, category: ToolCategory) -> None:
        """动态加载单个分类的工具到_tools_dict"""
        cat_tools = tool_registry.get_implementations_by_category(category)
        if cat_tools:
            self.agent._tools_dict.update(cat_tools)
            self.agent._loaded_categories.add(category)
            logger.info(f"[ToolLoader] 动态加载分类{category.value}, {len(cat_tools)}个工具")
