# Agent工厂模式架构改进设计方案

**版本**: v1.0
**创建时间**: 2026-04-26 12:25:00
**作者**: 小健
**目标**: 从单一file模式提升到支持多工具分类的架构模式

---

## 一、当前架构问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 各Agent独立初始化工具 | 代码重复，难以维护 |
| 2 | 无统一注册机制 | 难以扩展新Agent |
| 3 | Network/Desktop返回错误 | 功能缺失 |
| 4 | 工具分散在各处 | 难以管理和测试 |
| 5 | time工具未集成到Agent | 只注册到旧系统 |

---

## 二、目标架构

```
tool_registry (唯一注册中心)
    ├─ category="file"     → 17个工具
    ├─ category="time"     → 9个工具
    ├─ category="network"   → 待实现
    ├─ category="desktop"  → 待实现
    └─ category="chat"     → Prompt模板

AgentFactory.create(intent_type)
    ├─ "file"    → FileReactAgent
    ├─ "time"    → TimeReactAgent (新建)
    ├─ "network" → NetworkReactAgent
    ├─ "desktop" → DesktopReactAgent
    └─ "chat"   → BaseReact
```

---

## 三、工具分类状态（更新）

| 分类 | 工具数量 | 注册方式 | Agent |
|------|----------|-----------|-------|
| file | 17 | tool_registry | FileReactAgent |
| time | 9 | ~~旧系统~~ → tool_registry | TimeReactAgent (新建) |
| network | 0 | 待实现 | NetworkReactAgent (新建) |
| desktop | 0 | 待实现 | DesktopReactAgent (新建) |
| chat | - | Prompt | BaseReact |

---

## 四、核心组件设计

### 4.1 AgentFactory（新建）

```python
# 文件位置: app/services/agent/agent_factory.py
# ============================================================

from typing import Dict, Any, Optional, Type
from app.services.agent.base_react import BaseAgent
from app.services.agent.file_react import FileReactAgent
from app.services.tools.registry import tool_registry, ToolCategory


class AgentFactory:
    """
    Agent工厂 - 统一创建Agent实例
    
    根据intent_type创建对应的Agent，并自动加载该Agent需要的工具。
    """
    
    # Agent类映射
    _AGENTS: Dict[str, Type[BaseAgent]] = {
        "file": FileReactAgent,
        # "time": TimeReactAgent,      # Phase 2
        # "network": NetworkReactAgent, # Phase 3
        # "desktop": DesktopReactAgent,# Phase 3
    }
    
    # Agent需要的工具分类
    _TOOL_CATEGORIES: Dict[str, Optional[ToolCategory]] = {
        "file": ToolCategory.FILE,
        # "time": ToolCategory.TIME,    # Phase 2
        # "network": ToolCategory.NETWORK,  # Phase 3
        # "desktop": ToolCategory.DESKTOP, # Phase 3
    }
    
    @classmethod
    def create(
        cls,
        intent_type: str,
        llm_client: Any,
        session_id: str,
        config: Dict[str, Any],
        **kwargs
    ) -> BaseAgent:
        """
        根据intent_type创建Agent
        
        Args:
            intent_type: 意图类型 (file/time/network/desktop/chat)
            llm_client: LLM客户端
            session_id: 会话ID
            config: 配置字典
            **kwargs: 其他参数
        
        Returns:
            BaseAgent: 对应的Agent实例
        
        Raises:
            ValueError: 如果intent_type未知
        """
        # 获取Agent类
        AgentClass = cls._AGENTS.get(intent_type)
        if not AgentClass:
            # 未实现的Agent，回退到BaseReact
            from app.services.agent.base_react import BaseReact
            AgentClass = BaseReact
            intent_type = "chat"  # 改为chat
        
        # 获取工具分类
        tool_category = cls._TOOL_CATEGORIES.get(intent_type)
        
        # 创建Agent实例
        return AgentClass(
            llm_client=llm_client,
            session_id=session_id,
            tool_category=tool_category,
            config=config,
            **kwargs
        )
    
    @classmethod
    def register_agent(
        cls,
        intent_type: str,
        agent_class: Type[BaseAgent],
        tool_category: Optional[ToolCategory] = None
    ):
        """
        注册新的Agent
        
        Args:
            intent_type: 意图类型
            agent_class: Agent类
            tool_category: 需要的工具分类
        """
        cls._AGENTS[intent_type] = agent_class
        cls._TOOL_CATEGORIES[intent_type] = tool_category
    
    @classmethod
    def list_available_agents(cls) -> Dict[str, Any]:
        """列出所有可用的Agent"""
        return {
            name: {
                "class": cls._AGENTS[name].__name__,
                "category": cls._TOOL_CATEGORIES[name],
                "available": cls._AGENTS[name] is not None
            }
            for name in cls._AGENTS.keys()
        }
```

### 4.2 BaseAgent改进

```python
# 文件位置: app/services/agent/base_react.py
# ============================================================

class BaseAgent(ABC):
    """Agent基类 - 支持多工具分类"""
    
    def __init__(
        self,
        max_steps: int = 100,
        tool_category: Optional[ToolCategory] = None,
        **kwargs
    ):
        super().__init__(max_steps)
        
        self.tool_category = tool_category
        
        # 加载工具
        self._tools_dict = self._load_tools()
        
        # 创建工具执行器
        self.executor = ToolExecutor(self._tools_dict)
    
    def _load_tools(self) -> Dict[str, Callable]:
        """从registry加载工具"""
        if not self.tool_category:
            return {}
        
        from app.services.tools.registry import (
            get_tools_from_registry_by_category
        )
        
        return get_tools_from_registry_by_category(self.tool_category)
```

### 4.3 新注册函数

```python
# 文件位置: app/services/tools/registry.py
# ============================================================

def get_tools_from_registry_by_category(category: ToolCategory) -> Dict[str, Callable]:
    """
    按分类从registry获取工具
    
    Args:
        category: 工具分类
    
    Returns:
        {工具名: 工具函数} 格式
    """
    result = {}
    for name in tool_registry.list_tools(category=category):
        impl = tool_registry.get_exact_implementation(name)
        if impl:
            result[name] = impl
    return result
```

---

## 五、实施计划

### Phase 1: 创建AgentFactory（高优先级）

| 任务 | 文件 | 内容 |
|------|------|------|
| T1.1 | agent_factory.py | 创建AgentFactory类 |
| T1.2 | registry.py | 添加get_tools_by_category |
| T1.3 | base_react.py | 改造BaseAgent支持tool_category |
| T1.4 | react_sse_wrapper.py | 使用AgentFactory |

### Phase 2: 集成time工具（高优先级）

| 任务 | 文件 | 内容 |
|------|------|------|
| T2.1 | time_register.py | 改为注册到tool_registry |
| T2.2 | agent/time_react.py | 新建TimeReactAgent |
| T2.3 | time/__init__.py | 更新导出 |

### Phase 3: 创建Network/DesktopAgent（中优先级）

| 任务 | 文件 | 内容 |
|------|------|------|
| T3.1 | network/ | 新建目录结构 |
| T3.2 | network_tools.py | 实现网络工具 |
| T3.3 | network_register.py | 注册到registry |
| T3.4 | agent/network_react.py | 新建NetworkReactAgent |
| T3.5 | desktop/ | 同上 |

### Phase 4: 混合工具支持（扩展）

| 任务 | 文件 | 内容 |
|------|------|------|
| T4.1 | BaseAgent | 支持多分类 |
| T4.2 | ToolExecutor | 跨分类执行 |

---

## 六、代码实现

### 6.1 AgentFactory实现

```python
# ============================================================
# app/services/agent/agent_factory.py
# ============================================================

from typing import Dict, Any, Optional, Type
from app.services.agent.base_react import BaseAgent
from app.services.agent.file_react import FileReactAgent
from app.services.tools.registry import tool_registry, ToolCategory


class AgentFactory:
    """
    Agent工厂 - 统一创建Agent实例
    
    使用方式:
        agent = AgentFactory.create(
            intent_type="file",
            llm_client=llm_client,
            session_id=session_id,
            config=config
        )
    """
    
    _AGENTS: Dict[str, Type[BaseAgent]] = {
        "file": FileReactAgent,
    }
    
    _TOOL_CATEGORIES: Dict[str, Optional[ToolCategory]] = {
        "file": ToolCategory.FILE,
    }
    
    @classmethod
    def create(
        cls,
        intent_type: str,
        llm_client: Any,
        session_id: str,
        config: Dict[str, Any],
        **kwargs
    ) -> BaseAgent:
        """创建Agent实例"""
        AgentClass = cls._AGENTS.get(intent_type, BaseReact)
        
        tool_category = cls._TOOL_CATEGORIES.get(intent_type)
        
        return AgentClass(
            llm_client=llm_client,
            session_id=session_id,
            tool_category=tool_category,
            config=config,
            **kwargs
        )
    
    @classmethod
    def register(
        cls,
        intent_type: str,
        agent_class: Type[BaseAgent],
        tool_category: Optional[ToolCategory] = None
    ):
        """注册新的Agent"""
        cls._AGENTS[intent_type] = agent_class
        cls._TOOL_CATEGORIES[intent_type] = tool_category
```

### 6.2 registry.py新函数

```python
# ============================================================
# 添加到 registry.py
# ============================================================

def get_tools_by_category(category: ToolCategory) -> Dict[str, Callable]:
    """按分类获取工具"""
    result = {}
    for name in tool_registry.list_tools(category=category):
        impl = tool_registry.get_exact_implementation(name)
        if impl:
            result[name] = impl
    return result
```

---

## 七、验证标准

| 验证项 | 预期结果 |
|--------|----------|
| AgentFactory.create("file") | 返回FileReactAgent |
| file工具 registry数量 | 17 |
| time工具注册到registry | 9 |
| react_sse_wrapper使用工厂 | 正常工作 |

---

**更新时间**: 2026-04-26 12:25:00
**版本**: v1.0