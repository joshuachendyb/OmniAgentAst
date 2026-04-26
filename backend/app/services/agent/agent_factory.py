# -*- coding: utf-8 -*-
"""
AgentFactory - Agent工厂类
统一创建Agent实例

位置: app/services/agent/agent_factory.py
小健 - 2026-04-26
修复 - 2026-04-26 小沈
"""
from typing import Dict, Any, Optional, Type
from app.services.agent.base_react import BaseAgent
from app.services.tools.registry import ToolCategory


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
    _TOOL_CATEGORIES: Dict[str, Optional[ToolCategory]] = {}
    
    @classmethod
    def create(
        cls,
        intent_type: str,
        llm_client: Any = None,
        session_id: str = "",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        tool_category: Optional[ToolCategory] = None,
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
            tool_category: 工具分类 【新增】
            **kwargs: 其他参数
            
        Returns:
            BaseAgent: 对应的Agent实例
        """
        # 获取Agent类
        AgentClass = cls._AGENTS.get(intent_type)
        
        # 如果没有注册的Agent，返回None
        if not AgentClass:
            return None
        
        # 获取tool_category（优先使用参数，其次使用预注册的）
        effective_tool_category = tool_category
        if not effective_tool_category:
            effective_tool_category = cls._TOOL_CATEGORIES.get(intent_type)
        
        # 创建Agent实例（传递所有参数，包括tool_category）
        return AgentClass(
            llm_client=llm_client,
            session_id=session_id,
            api_base=api_base,
            api_key=api_key,
            model=model,
            tool_category=effective_tool_category,
            **kwargs
        )
    
    @classmethod
    def register(
        cls,
        intent_type: str,
        agent_class: Type[BaseAgent],
        tool_category: Optional[ToolCategory] = None
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
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('file', FileReactAgent, ToolCategory.FILE)
except ImportError as e:
    print(f"[AgentFactory] 注册FileReactAgent失败: {e}")

# 注册TimeReactAgent（如果存在）
try:
    from app.services.agent.time_react import TimeReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('time', TimeReactAgent, ToolCategory.TIME)
except ImportError as e:
    print(f"[AgentFactory] TimeReactAgent未找到: {e}")