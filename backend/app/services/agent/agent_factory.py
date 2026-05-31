# -*- coding: utf-8 -*-
"""
AgentFactory - 智能体工厂

改造后：使用声明式配置注册表创建 Agent
- UniversalReactAgent 处理 file/system/network/document
- DesktopReactAgent 独立处理 desktop

Author: 小强 - 2026-05-23
"""
from typing import Any, Dict, List, Optional

from app.services.agent.agent_config import resolve_agent_config, AgentConfig, AGENT_REGISTRY, get_all_intent_types
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
        """
        创建 Agent 实例
        
        Args:
            intent_type: 意图类型（含别名，如 "time" → "system"）
            llm_client: LLM 客户端
            task_id: 任务ID
            tool_category: 工具分类（可选，由配置自动决定）
            max_steps: 最大步数
            candidates: 候选意图列表
            **kwargs: 其他参数
        """
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
        result = {}
        for config in AGENT_REGISTRY.values():
            name = config.agent_class_name or "UnknownAgent"
            result[config.intent_type] = name
            for alias in config.aliases:
                result[alias] = name
        return result



