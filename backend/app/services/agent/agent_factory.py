# -*- coding: utf-8 -*-
"""
AgentFactory - 智能体工厂

Author: 小强 - 2026-05-23
"""
from typing import Any, Dict, List, Optional

from app.services.agent.agent_config import resolve_agent_config, AGENT_REGISTRY
from app.services.agent.base_react import BaseAgent
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


class AgentFactory:
    """智能体工厂 — 基于声明式配置"""
    
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
        """创建 Agent 实例"""
        config = resolve_agent_config(intent_type)
        
        logger.info(
            f"[AgentFactory] intent_type={intent_type} → "
            f"config.intent={config.intent_type}, category={config.category}, "
            f"rollback={config.rollback_enabled}"
        )
        
        agent_class = config.agent_class
        if agent_class is None:
            raise ValueError(f"Agent class not configured for intent_type: {intent_type}")
        
        if config.intent_type == "desktop":
            return agent_class(
                llm_client=llm_client,
                task_id=task_id,
                tool_category=tool_category,
                candidates=candidates,
                **kwargs
            )
        
        return agent_class(
            llm_client=llm_client,
            task_id=task_id,
            config=config,
            tool_category=tool_category,
            candidates=candidates,
            **kwargs
        )
    
    @classmethod
    def list_available_agents(cls) -> Dict[str, str]:
        """列出所有可用的Agent"""
        return {
            config.intent_type: config.agent_class_name or "UnknownAgent"
            for config in AGENT_REGISTRY.values()
        }
