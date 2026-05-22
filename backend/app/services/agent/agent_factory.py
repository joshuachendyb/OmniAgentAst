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
from app.services.tools.registry import ToolCategory, INTENT_TO_CATEGORY


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
        
        # 【步骤7】不再回退到FileReactAgent，未注册intent直接报错
        if not AgentClass:
            available = list(cls._AGENTS.keys())
            raise ValueError(f"AgentFactory: intent_type='{intent_type}' 未注册。可用Agent: {available}")
        
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

# TimeReactAgent → 兼容旧意图名time - 【2026-05-18 小沈】time→meta
try:
    from app.services.agent.time_react import TimeReactAgent
    if 'meta' not in AgentFactory._AGENTS:
        AgentFactory.register('meta', TimeReactAgent, ToolCategory.META)
    AgentFactory.register('time', TimeReactAgent, ToolCategory.META)
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

# DatabaseReactAgent → 兼容旧意图名database - 【2026-05-18 小沈】database→document
try:
    from app.services.agent.database_react import DatabaseReactAgent
    if 'document' not in AgentFactory._AGENTS:
        AgentFactory.register('document', DatabaseReactAgent, ToolCategory.DOCUMENT)
    AgentFactory.register('database', DatabaseReactAgent, ToolCategory.DOCUMENT)
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
# 【注意】行164-166已将'document'注册为DatabaseReactAgent作为兼容别名
# 此处覆盖为DocumentReactAgent（新规范名），是设计意图，不是bug - 小沈 2026-05-22
try:
    from app.services.agent.document_react import DocumentReactAgent
    from app.services.tools.registry import ToolCategory
    if 'document' not in AgentFactory._AGENTS:
        AgentFactory.register('document', DocumentReactAgent, ToolCategory.DOCUMENT)
    else:
        # 覆盖旧兼容别名，确保新规范名的Agent正确 - 小沈 2026-05-22
        AgentFactory._AGENTS['document'] = DocumentReactAgent
        from app.services.tools.registry import ToolCategory
        AgentFactory._TOOL_CATEGORIES['document'] = ToolCategory.DOCUMENT
except ImportError as e:
    print(f"[AgentFactory] DocumentReactAgent: {e}")

# CodeExecutionReactAgent → 兼容旧意图名code_execution - 【2026-05-18 小沈】code_execution→shell
try:
    from app.services.agent.code_execution_react import CodeExecutionReactAgent
    if 'shell' not in AgentFactory._AGENTS:
        AgentFactory.register('shell', CodeExecutionReactAgent, ToolCategory.SHELL)
    AgentFactory.register('code_execution', CodeExecutionReactAgent, ToolCategory.SHELL)
except ImportError as e:
    print(f"[AgentFactory] CodeExecutionReactAgent: {e}")
