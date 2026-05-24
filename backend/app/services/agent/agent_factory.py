# -*- coding: utf-8 -*-
"""
AgentFactory - 智能体工厂

改造后：使用声明式配置注册表创建 Agent
- UniversalReactAgent 处理 file/system/network/document
- DesktopReactAgent 独立处理 desktop

Author: 小强 - 2026-05-23
"""
from typing import Any, Dict, List, Optional, Type

from app.services.agent.agent_config import resolve_agent_config, AgentConfig, AGENT_REGISTRY, get_all_intent_types
from app.services.agent.universal_react import UniversalReactAgent
from app.services.agent.desktop_react import DesktopReactAgent
from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
from app.services.tools.registry import ToolCategory
from app.utils.logger import logger


class AgentFactory:
    """智能体工厂 — 基于声明式配置"""
    
    _AGENTS: Dict[str, Type[BaseAgent]] = {}
    _TOOL_CATEGORIES: Dict[str, Optional[ToolCategory]] = {}
    
    @classmethod
    def create(
        cls,
        intent_type: str,
        llm_client: Any = None,
        task_id: str = "",
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = DEFAULT_MAX_STEPS,
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
        
        if config.intent_type == "desktop":
            return DesktopReactAgent(
                llm_client=llm_client,
                task_id=task_id,
                tool_category=tool_category,
                max_steps=max_steps,
                candidates=candidates,
                **kwargs
            )
        
        return UniversalReactAgent(
            llm_client=llm_client,
            task_id=task_id,
            config=config,
            tool_category=tool_category,
            max_steps=max_steps,
            candidates=candidates,
            **kwargs
        )
    
    @classmethod
    def register(
        cls,
        intent_type: str,
        agent_class: Type[BaseAgent],
        tool_category: Optional[ToolCategory] = None
    ):
        """注册新的Agent（向后兼容接口）"""
        cls._AGENTS[intent_type] = agent_class
        if tool_category:
            cls._TOOL_CATEGORIES[intent_type] = tool_category
    
    @classmethod
    def list_available_agents(cls) -> Dict[str, str]:
        """列出所有可用的Agent"""
        result = {}
        for config in AGENT_REGISTRY.values():
            result[config.intent_type] = "UniversalReactAgent" if config.intent_type != "desktop" else "DesktopReactAgent"
            for alias in config.aliases:
                result[alias] = result[config.intent_type]
        return result


for config in AGENT_REGISTRY.values():
    AgentClass = DesktopReactAgent if config.intent_type == "desktop" else UniversalReactAgent
    AgentFactory._AGENTS[config.intent_type] = AgentClass
    AgentFactory._TOOL_CATEGORIES[config.intent_type] = config.category
    for alias in config.aliases:
        AgentFactory._AGENTS[alias] = AgentClass
        AgentFactory._TOOL_CATEGORIES[alias] = config.category
