# -*- coding: utf-8 -*-
"""
create_agent - 创建 UniversalAgent

CRSS/意图移除后，所有请求走同一个 UniversalAgent，不再按意图分类

Author: 小沈 - 2026-06-13
"""
from typing import Any, Optional

from app.services.agent.agent_config import DEFAULT_AGENT_CONFIG
from app.services.agent.universal_agent import UniversalAgent
from app.utils.logger import logger


def create_agent(
    llm_client: Any = None,
    task_id: str = "",
    **kwargs
) -> UniversalAgent:
    """创建 UniversalAgent — 单一配置,无意图分支"""
    config = DEFAULT_AGENT_CONFIG
    
    logger.info(
        f"[create_agent] task_id={task_id}, config={config.prompt_class_name}"
    )
    
    return UniversalAgent(
        llm_client=llm_client,
        task_id=task_id,
        config=config,
        **kwargs
    )

