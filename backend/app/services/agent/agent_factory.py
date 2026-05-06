# -*- coding: utf-8 -*-
"""
AgentFactory - Agent工厂类
统一创建Agent实例

参考: 文档5.1节+7.1节完整代码

位置: app/services/agent/agent_factory.py
修复 - 2026-04-26 小沈
新增 - 2026-04-30 小沈（candidates参数）
"""
from typing import Dict, Any, Optional, Type, List
from app.services.agent.base_react import BaseAgent, DEFAULT_MAX_STEPS
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
        max_steps: int = DEFAULT_MAX_STEPS,
        candidates: Optional[List[str]] = None,  # 【新增 2026-04-30 小沈】候选意图列表
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
            candidates: 候选意图列表（如 ["file", "chat"]），用于跨分类工具访问
            **kwargs: 其他参数
            
        Returns:
            BaseAgent: 对应的Agent实例
        """
        # 获取Agent类
        AgentClass = cls._AGENTS.get(intent_type)
        
        # 【修复 2026-04-30 小沈】未注册的intent_type回退到FileReactAgent，而非返回None
        # 返回None会导致调用方 None.run_stream() → AttributeError
        if not AgentClass:
            from app.utils.logger import logger
            logger.warning(f"[AgentFactory] intent_type='{intent_type}' 未注册，回退到 FileReactAgent")
            fallback_class = cls._AGENTS.get('file')
            if not fallback_class:
                raise ValueError(f"AgentFactory: intent_type='{intent_type}' 未注册且无回退Agent可用")
            AgentClass = fallback_class
            # 回退时也使用file的tool_category
            if not tool_category:
                tool_category = cls._TOOL_CATEGORIES.get('file')
        
        # 获取tool_category（优先使用参数，其次使用预注册的）
        effective_tool_category = tool_category
        if not effective_tool_category:
            effective_tool_category = cls._TOOL_CATEGORIES.get(intent_type)
        
        # 创建Agent实例（传递所有参数，按新结构）
        # 【修改】task_id参数传递，2026-04-26 小沈
        # 【新增】candidates参数传递，2026-04-30 小沈
        return AgentClass(
            llm_client=llm_client,
            task_id=task_id,  # 修正：使用已重命名的task_id参数
            tool_category=effective_tool_category,
            max_steps=max_steps,
            candidates=candidates,  # 传递候选意图列表
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

# ===== 步骤4：注册7个新Agent ===== 
# 参考文档4.14节，步骤4实施要求使用fallback机制

# ShellReactAgent
try:
    from app.services.agent.shell_react import ShellReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('shell', ShellReactAgent, ToolCategory.SHELL)
except ImportError as e:
    print(f"[AgentFactory] ShellReactAgent: {e}")

# NetworkReactAgent
try:
    from app.services.agent.network_react import NetworkReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('network', NetworkReactAgent, ToolCategory.NETWORK)
except ImportError as e:
    print(f"[AgentFactory] NetworkReactAgent: {e}")

# DesktopReactAgent
try:
    from app.services.agent.desktop_react import DesktopReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('desktop', DesktopReactAgent, ToolCategory.DESKTOP)
except ImportError as e:
    print(f"[AgentFactory] DesktopReactAgent: {e}")

# DatabaseReactAgent
try:
    from app.services.agent.database_react import DatabaseReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('database', DatabaseReactAgent, ToolCategory.DATABASE)
except ImportError as e:
    print(f"[AgentFactory] DatabaseReactAgent: {e}")

# SystemReactAgent
try:
    from app.services.agent.system_react import SystemReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('system', SystemReactAgent, ToolCategory.SYSTEM)
except ImportError as e:
    print(f"[AgentFactory] SystemReactAgent: {e}")

# DocumentReactAgent
try:
    from app.services.agent.document_react import DocumentReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('document', DocumentReactAgent, ToolCategory.DOCUMENT)
except ImportError as e:
    print(f"[AgentFactory] DocumentReactAgent: {e}")

# CodeExecutionReactAgent
try:
    from app.services.agent.code_execution_react import CodeExecutionReactAgent
    from app.services.tools.registry import ToolCategory
    AgentFactory.register('code_execution', CodeExecutionReactAgent, ToolCategory.CODE_EXECUTION)
except ImportError as e:
    print(f"[AgentFactory] CodeExecutionReactAgent: {e}")