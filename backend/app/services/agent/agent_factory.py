# -*- coding: utf-8 -*-
"""
AgentFactory - 智能体工厂

小健 - 2026-06-08 修复P2: 消除desktop硬编码分支,统一走config.agent_class创建

Author: 小强 - 2026-05-23
"""
from typing import Any, Dict, List, Optional

from app.services.agent.agent_config import resolve_agent_config, AGENT_REGISTRY
from app.services.agent.core_agent import BaseAgent
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class AgentFactory:
    """智能体工厂 — 基于声明式配置,无硬编码分支"""
    
    @classmethod
    def create(
        cls,
        intent_type: str,
        llm_client: Any = None,
        task_id: str = "",
        tool_category: Optional[ToolCategory] = None,
        candidates: Optional[List[str]] = None,
        **kwargs
    ) -> BaseAgent:
        """创建 Agent 实例 — 统一入口,config决定一切"""
        config = resolve_agent_config(intent_type)
        
        logger.info(
            f"[AgentFactory] intent_type={intent_type} → "
            f"config.intent={config.intent_type}, category={config.category}"
        )
        
        agent_class = config.agent_class
        if agent_class is None:
            raise ValueError(f"Agent class not configured for intent_type: {intent_type}")
        
        # 统一传入config,不再分desktop特殊路径
        return agent_class(
            llm_client=llm_client,
            task_id=task_id,
            config=config,
            tool_category=tool_category,
            candidates=candidates,
            **kwargs
        )

