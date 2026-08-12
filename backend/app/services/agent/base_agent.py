
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 小欧 统一TaskID: 删除_tracked_task_id, create_task传入self.task_id
# 2026-07-17 小欧 新增_consecutive_reasoning_only字段(空转检测防御: reasoning-only分支累加, 调工具/正常answer/真空/error/未知/action空名归零)
# 2026-07-22 小欧 max_context_chars→max_context_tokens 构造传参同步
# 2026-07-22 小欧 新增 accumulated_usage 字段(累积消耗统计: 逐次LLM调用累加, FinalStep终态输出)
# 2026-08-05 小欧 修复BUG1/2(三堂会审通过): init_tools按实际加载结果重建_loaded_categories(消除initial_categories=None失配); load_category改为单一权威(同时写_tools_dict与_loaded_categories,空实现返回False), _loaded_categories仅含真正加载实现的分类
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

from app.services.agent.status_table import AgentStatus
from app.services.agent.steps import ReasoningStep

from app.config import get_config
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer
from app.services.agent.message_builder import MessageBuilder

from app.services.agent.step_emitter import StepEmitter
from app.tools.toolhelper.tool_retry_engine import ToolRetryEngine
from app.services.agent.react_cycle import run_react_cycle as _run


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
        self._consecutive_reasoning_only = 0  # 2026-07-17 - 小欧 - 连续reasoning-only计数(空转检测): reasoning-only分支累加, 调工具/正常answer/真空归零, 达上限终止
        self.accumulated_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}  # 2026-07-22 - 小欧 - 累积消耗统计: 逐次LLM调用累加, FinalStep终态输出

        # 原 AgentInitializer._init_messages
        self.steps: List[ReasoningStep] = []
        self.message_builder = MessageBuilder(max_context_tokens=get_config().get_max_context_tokens())

        self._loaded_categories: Set = set()
        self._tool_loader = ToolLoader(self)
        self._tool_loader.init_tools(initial_categories=initial_categories)
        self._retry_engine = ToolRetryEngine(self._tools_dict)

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


class ToolLoader:
    """工具加载和管理 — 小沈 2026-06-17 改名ToolManager→ToolLoader"""

    def __init__(self, agent):
        self.agent = agent

    def init_tools(self, initial_categories=None):
        """初始化工具,按分类注入工具给LLM"""
        self.agent._tools_dict = {}
        # _loaded_categories 由实际加载结果重建, 保证与_tools_dict一致(单一权威: 只含真正加载了实现的分类)
        # 2026-08-05 小欧: 修复BUG1/2 - 空实现分类不再被标记为已加载; 消除initial_categories=None时标记与实现失配
        self.agent._loaded_categories = set()
        categories_to_load = initial_categories or list(ToolCategory)
        for cat in categories_to_load:
            cat_tools = tool_registry.get_implementations_by_category(cat)
            if cat_tools:
                self.agent._tools_dict.update(cat_tools)
                self.agent._loaded_categories.add(cat)
        logger.info(f"[ToolLoader] 初始化完成,共{len(self.agent._tools_dict)}个工具")

    def get_tools(self) -> dict:
        """获取工具字典"""
        return self.agent._tools_dict

    def load_category(self, category: ToolCategory) -> bool:
        """动态加载单个分类的工具到_tools_dict

        单一权威(2026-08-05 小欧 修复BUG1/2):
        - _tools_dict 与 _loaded_categories 同时写入, 保证标记=已实现
        - 返回是否真正加载成功(空实现分类返回False), 供调用方跳过标记
        """
        cat_tools = tool_registry.get_implementations_by_category(category)
        if not cat_tools:
            logger.info(f"[ToolLoader] 分类{category.value}无可用实现, 不标记为已加载")
            return False
        self.agent._tools_dict.update(cat_tools)
        self.agent._loaded_categories.add(category)
        logger.info(f"[ToolLoader] 动态加载分类{category.value}, {len(cat_tools)}个工具")
        return True

