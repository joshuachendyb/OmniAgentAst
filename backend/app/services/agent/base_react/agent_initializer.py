# -*- coding: utf-8 -*-
"""
Agent初始化逻辑 — 从 base_react.py 拆出

复制来源: base_react.py 第97-131行 (_init_llm, _init_state, _init_messages)
Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import Any, Optional, List

from app.services.agent.types import AgentStatus
from app.services.agent.message_builder import MessageBuilder
from app.constants import MAX_CONTEXT_CHARS
from app.services.tools.tool_types import ToolCategory


class AgentInitializer:
    """Agent初始化逻辑（SRP）"""

    @staticmethod
    def initialize(
        agent,
        llm_client: Any,
        task_id: str,
        tool_category: Optional[ToolCategory],
        max_steps: int,
        rollback_enabled: bool,
        candidates: Optional[List[str]],
        **kwargs
    ) -> None:
        """一次性完成所有初始化"""
        agent._init_llm(llm_client, **kwargs)
        agent._init_state(task_id, tool_category, max_steps)
        agent._init_messages()
        agent._init_task_tracking(enable=rollback_enabled)
        agent._init_candidates(candidates)

    @staticmethod
    def _init_llm(agent, llm_client: Any, **kwargs):
        """复制自 base_react.py 第97-107行 — 初始化LLM客户端相关属性"""
        agent.llm_client = llm_client

        # 【修复 2026-04-30 小沈】将 **kwargs 中有用的参数 setattr 到 self
        # 之前 **kwargs 被静默忽略，导致 model/provider/api_base/api_key 丢失
        # 这些属性被 prompt_logger 和 llm_adapter 等使用
        _ALLOWED_KWARGS = {'model', 'provider', 'api_base', 'api_key'}
        for key, value in kwargs.items():
            if key in _ALLOWED_KWARGS:
                setattr(agent, key, value)

    @staticmethod
    def _init_state(agent, task_id: str, tool_category: Optional[ToolCategory], max_steps: int):
        """复制自 base_react.py 第109-124行 — 初始化状态管理相关属性"""
        agent.task_id = task_id  # 赋值task_id
        agent.tool_category = tool_category
        agent.max_steps = max_steps
        agent.status = AgentStatus.IDLE
        agent.llm_call_count = 0
        agent._lock = asyncio.Lock()

        # 【重构 2026-05-27 小健】2.22：parse/empty重试委托给RetryEngine
        from app.utils.retry import create_agent_retry_engine
        agent._parse_retry_engine, agent._empty_response_retry_engine = create_agent_retry_engine()

        # 【v2.3新增】chunk处理相关属性—所有Agent子类共享
        from app.constants import MAX_CONSECUTIVE_CHUNKS
        agent.max_consecutive_chunks = MAX_CONSECUTIVE_CHUNKS  # 连续chunk达此阈值时提升为implicit

    @staticmethod
    def _init_messages(agent):
        """复制自 base_react.py 第127-131行 — 初始化消息构建相关属性"""
        from app.services.agent.steps import ReasoningStep
        # 【步骤2.10】步骤历史管理：使用ReasoningStep类型
        agent.steps: List[ReasoningStep] = []
        agent.message_builder = MessageBuilder(max_context_chars=MAX_CONTEXT_CHARS)

    @staticmethod
    def _init_task_tracking(agent, enable: bool):
        """初始化Task追踪 — 从 _initialize_run_state 中提取"""
        agent._task_tracker = None
        agent._tracked_task_id = None
        if not enable:
            return
        try:
            from app.services.task import get_tracker
            intent = getattr(agent, '_intent', None) or agent.tool_category.value if agent.tool_category else "unknown"
            agent_id = getattr(agent, 'task_id', 'unknown')
            tracker = get_tracker()
            agent._tracked_task_id = tracker.create_task(
                intent=intent,
                agent_id=agent_id,
                description="",
            )
            agent._task_tracker = tracker
        except Exception as _e:
            from app.utils.logger import logger
            logger.debug(f"[TaskTracker] 创建任务失败: {_e}")

    @staticmethod
    def _init_candidates(agent, candidates: Optional[List[str]]):
        """初始化候选意图列表"""
        agent._candidates = candidates or []
