# -*- coding: utf-8 -*-
"""
AgentFactory - Agent工厂类
统一创建Agent实例

参考: 文档5.1节+7.1节完整代码

位置: app/services/agent/agent_factory.py
修复 - 2026-04-26 小沈
"""
from typing import Dict, Any, Optional, Type
from app.services.agent.base_react import BaseAgent
from app.services.tools.registry import ToolCategory


class AgentFactory:
    """
    Agent工厂 - 统一创建Agent实例
    参考: 7.1节行857-912
    
    使用方式:
        agent = AgentFactory.create(
            intent_type="file",
            llm_client=llm_client,
            session_id=session_id,
            tool_category=ToolCategory.FILE
        )
    """
    
    _AGENTS: Dict[str, Type[BaseAgent]] = {}
    _TOOL_CATEGORIES: Dict[str, Optional[ToolCategory]] = {}
    
    @classmethod
    def create(
        cls,
        intent_type: str,
        llm_client: Any = None,
        task_id: str = "",  # 【修改】session_id → task_id，2026-04-26 小沈
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = 100,
        **kwargs
    ) -> BaseAgent:
        """创建Agent实例
        参考: 7.1节行881-901
        
        Args:
            intent_type: 意图类型 (file/time/shell/network/desktop/chat)
            llm_client: LLM客户端
            task_id: 任务ID（操作追踪和回退用）
            tool_category: 工具分类
            max_steps: 最大步数
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
        
        # 创建Agent实例（传递所有参数，按新结构）
        # 【修改】task_id参数传递，2026-04-26 小沈
        return AgentClass(
            llm_client=llm_client,
            task_id=task_id,  # 修正：使用已重命名的task_id参数
            tool_category=effective_tool_category,
            max_steps=max_steps,
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
        参考: 7.1节行902-912
        
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

# 注册默认的Agent
# FileReactAgent
try:
    from app.services.agent.file_react import FileReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('file', FileReactAgent, ToolCategory.FILE)
except ImportError as e:
    print(f"[AgentFactory] FileReactAgent: {e}")

# TimeReactAgent
try:
    from app.services.agent.time_react import TimeReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('time', TimeReactAgent, ToolCategory.TIME)
except ImportError as e:
    print(f"[AgentFactory] TimeReactAgent: {e}")