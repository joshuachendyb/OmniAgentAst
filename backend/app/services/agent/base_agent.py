
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 小欧 统一TaskID: 删除_tracked_task_id, create_task传入self.task_id
# 2026-07-17 小欧 新增_consecutive_reasoning_only字段(空转检测防御: reasoning-only分支累加, 调工具/正常answer/真空/error/未知/action空名归零)
# 2026-07-22 小欧 max_context_chars→max_context_tokens 构造传参同步
# 2026-07-22 小欧 新增 accumulated_usage 字段(累积消耗统计: 逐次LLM调用累加, FinalStep终态输出)
# 2026-08-05 小欧 修复BUG1/2(三堂会审通过): init_tools按实际加载结果重建_loaded_categories(消除initial_categories=None失配); load_category改为单一权威(同时写_tools_dict与_loaded_categories,空实现返回False), _loaded_categories仅含真正加载实现的分类
# 2026-08-12 小欧 A6: ToolLoader 独立为 tool_loader.py; 删除 tool_registry/ToolCategory 导入与 ToolLoader 类定义; __init__ 不再初始化工具状态(改由 UniversalAgent.__init__ 驱动)
"""
Agent 核心基类 — 类骨架

遵循 SRP: 只保留 BaseAgent 类定义、__init__、抽象方法、Hook、委托方法
run_react_cycle / initialize_run_state → 独立文件

Author: 小沈 - 2026-03-25
P3-12: 删除run_react_cycle纯委托，改为混合类方式 — 小沈 2026-06-09
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.services.agent.status_table import AgentStatus
from app.services.agent.steps import ReasoningStep

from app.config import get_config
from app.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.message_builder import MessageBuilder

from app.services.agent.step_emitter import StepEmitter
from app.services.agent.react_cycle import run_react_cycle as _run


class BaseAgent(ABC):
    """Agent 核心基类 — 小沈 2026-03-25"""
    _ALLOWED_KWARGS = {'model', 'provider', 'api_base', 'api_key'}

    def __init__(
        self,
        llm_client: Any,
        task_id: str,
        max_steps: Optional[int] = None,
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
        self._consecutive_reasoning_only = 0  # 2026-07-17 - 小欧 - 连续reasoning-only计数(空转检测): reasoning-only分支累加, 调工具/正常answer/真空归零, 达上限终止
        self.accumulated_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}  # 2026-07-22 - 小欧 - 累积消耗统计: 逐次LLM调用累加, FinalStep终态输出

        # 原 AgentInitializer._init_messages
        self.steps: List[ReasoningStep] = []
        self.message_builder = MessageBuilder(max_context_tokens=get_config().get_max_context_tokens())

        # 工具相关状态(_tools_dict/_tool_loader/_retry_engine/_loaded_categories)
        # A6(2026-08-12): 由子类 UniversalAgent.__init__ 驱动 tool_loader 初始化, 抽象基类不依赖工具注册表

        # 原 AgentInitializer._init_task_tracking
        self._task_tracker = None
        try:
            from app.services.task import get_tracker
            tracker = get_tracker()
            # 统一任务ID: SSE task_id 为全场唯一标识, tracker 不再自编号 — 北京老陈/小欧 2026-07-16
            tracker.create_task(
                task_id=self.task_id,
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

