# -*- coding: utf-8 -*-
"""
Agent初始化逻辑 — 从 base_react.py 拆出

复制来源: base_react.py 第97-131行 (_init_llm, _init_state, _init_messages)
Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import Any

from app.services.agent.types import AgentStatus
from app.services.agent.message_builder import MessageBuilder


class AgentInitializer:
    """Agent初始化逻辑(SRP)"""

    @staticmethod
    def _init_llm(agent, llm_client: Any, **kwargs):
        """复制自 base_react.py 第97-107行 — 初始化LLM客户端相关属性"""
        agent.llm_client = llm_client

        # 【修复 2026-04-30 小沈】将 **kwargs 中有用的参数 setattr 到 self
        # 之前 **kwargs 被静默忽略,导致 model/provider/api_base/api_key 丢失
        # 这些属性被 prompt_logger 和 llm_adapter 等使用
        _ALLOWED_KWARGS = {'model', 'provider', 'api_base', 'api_key'}
        for key, value in kwargs.items():
            if key in _ALLOWED_KWARGS:
                setattr(agent, key, value)

    @staticmethod
    def _init_state(agent, task_id: str, max_steps: int):
        agent.task_id = task_id
        agent.max_steps = max_steps
        agent.status = AgentStatus.IDLE
        agent.llm_call_count = 0

        # 【重构 2026-05-27 小健】2.22:parse/empty重试委托给RetryEngine
        from app.utils.retry import create_agent_retry_engine
        agent._parse_retry_engine, agent._empty_response_retry_engine = create_agent_retry_engine()

        # 【v2.3新增】chunk处理相关属性—所有Agent子类共享
        from app.constants import MAX_CONSECUTIVE_CHUNKS
        agent.max_consecutive_chunks = MAX_CONSECUTIVE_CHUNKS  # 连续chunk达此阈值时提升为implicit

    @staticmethod
    def _init_messages(agent):
        """初始化消息构建 — 从配置读取max_context_chars"""
        from app.services.agent.steps import ReasoningStep
        from app.config import get_config
        agent.steps: List[ReasoningStep] = []
        max_context_chars = get_config().get_max_context_chars()
        agent.message_builder = MessageBuilder(max_context_chars=max_context_chars)

    @staticmethod
    def _init_task_tracking(agent, enable: bool, description: str = ""):
        """初始化Task追踪"""
        agent._task_tracker = None
        agent._tracked_task_id = None
        if not enable:
            return
        try:
            from app.services.task import get_tracker
            agent_id = getattr(agent, 'task_id', 'unknown')
            tracker = get_tracker()
            agent._tracked_task_id = tracker.create_task(
                intent="",
                agent_id=agent_id,
                description=description[:200] if description else "",
            )
            agent._task_tracker = tracker
        except Exception as _e:
            from app.utils.logger import logger
            logger.debug(f"[TaskTracker] 创建任务失败: {_e}")


