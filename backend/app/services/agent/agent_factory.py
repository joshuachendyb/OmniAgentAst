# -*- coding: utf-8 -*-
"""
create_agent - 创建 UniversalAgent

Author: 小沈 - 2026-06-13
"""
from app.services.agent.universal_agent import UniversalAgent
from app.utils.logger import logger


def create_agent(
    llm_client=None,
    task_id: str = "",
    **kwargs
) -> UniversalAgent:
    """创建 UniversalAgent"""
    logger.info(f"[create_agent] task_id={task_id}")
    return UniversalAgent(
        llm_client=llm_client,
        task_id=task_id,
        **kwargs
    )

