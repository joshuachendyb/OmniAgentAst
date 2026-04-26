# -*- coding: utf-8 -*-
"""
AgentFactory - Agent工厂类
统一创建Agent实例

位置: app/services/agent/agent_factory.py
小健 - 2026-04-26
"""
from typing import Dict, Any, Optional, Type
from app.services.agent.base_react import BaseAgent


class AgentFactory:
    """
    Agent工厂 - 统一创建Agent实例
    
    使用方式:
        agent = AgentFactory.create(
            intent_type="file",
            llm_client=llm_client,
            session_id=session_id,
            api_base=api_base,
            api_key=api_key,
            model=model
        )
    """
    
    _AGENTS: Dict[str, Type[BaseAgent]] = {}
    _TOOL_CATEGORIES: Dict[str, str] = {}
    
    @classmethod
    def create(
        cls,
        intent_type: str,
        llm_client: Any = None,
        session_id: str = "",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> BaseAgent:
        """创建Agent实例
        
        Args:
            intent_type: 意图类型 (file/time/shell/network/desktop/chat)
            llm_client: LLM客户端
            session_id: 会话ID
            api_base: API地址
            api_key: API密钥
            model: 模型名称
            **kwargs: 其他参数
            
        Returns:
            BaseAgent: 对应的Agent实例
        """
        # 获取Agent类
        AgentClass = cls._AGENTS.get(intent_type)
        
        # 如果没有注册的Agent，返回None
        if not AgentClass:
            return None
        
        # 创建Agent实例（传递所有参数）
        return AgentClass(
            llm_client=llm_client,
            session_id=session_id,
            api_base=api_base,
            api_key=api_key,
            model=model,
            **kwargs
        )
    
    @classmethod
    def register(
        cls,
        intent_type: str,
        agent_class: Type[BaseAgent],
        tool_category: Optional[str] = None
    ):
        """注册新的Agent
        
        Args:
            intent_type: 意图类型
            agent_class: Agent类
            tool_category: 工具分类
        """
        cls._AGENTS[intent_type] = agent_class
        if tool_category:
            cls._TOOL_CATEGORIES[intent_type] = tool_category
    
    @classmethod
    def list_available_agents(cls) -> Dict[str, str]:
        """列出所有可用的Agent
        
        Returns:
            {intent_type: Agent类名}
        """
        return {
            name: cls._AGENTS[name].__name__
            for name in cls._AGENTS.keys()
        }

# 注册默认的FileReactAgent
try:
    from app.services.agent.file_react import FileReactAgent
    AgentFactory.register('file', FileReactAgent, 'file')
except ImportError:
    pass