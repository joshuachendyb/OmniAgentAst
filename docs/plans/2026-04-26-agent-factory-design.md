# Agent工厂模式架构改进设计方案

**版本**: v1.1
**创建时间**: 2026-04-26 12:25:00
**更新时间**: 2026-04-26 15:30:00
**作者**: 小健
**分析**: 小沈
**目标**: 从单一file模式提升到支持多工具分类的架构模式

---

## 一、当前架构问题（已更新）

| # | 问题 | 影响 | 状态 |
|---|------|------|------|
| 1 | 各Agent独立初始化工具 | 代码重复，难以维护 | ⚠️ 进行中 |
| 2 | 无统一注册机制 | 难以扩展新Agent | ✅ 已部分解决 |
| 3 | Network/Desktop返回错误 | 功能缺失 | 🟡 规划中 |
| 4 | 工具分散在各处 | 难以管理和测试 | ✅ 已统一 |
| 5 | time工具未集成到Agent | 只注册到旧系统 | ✅ 已修复 |
| 6 | **新发现：time工具实际未注册到registry** | 0个工具可用 | ✅ 已修复 |
| 7 | **新发现：FileReactAgent不支持tool_category** | 无法使用新架构 | 🔴 待修复 |

---

## 二、缺陷分析（小沈分析）

### 发现的缺陷

| # | 缺陷 | 严重程度 | 影响 |
|---|------|----------|------|
| **1** | time工具未注册到tool_registry | **严重** | 0个工具可用 |
| **2** | FileReactAgent 不支持 tool_category 参数 | **严重** | 无法使用新架构 |
| **3** | 函数名冲突 | 中等 | 代码冲突 |
| **4** | 循环导入风险 | 中等 | 启动失败 |
| **5** | BaseAgent 签名变更破坏现有代码 | 严重 | 现有功能崩溃 |
| **6** | 缺失参数传递 | 中等 | Agent初始化失败 |
| **7** | 回退逻辑不完整 | 中等 | 未知意图处理 |

### 详细分析

#### 缺陷1：time工具未注册（已修复）

**问题**：设计说"9个time工具已注册"，但实际上 `time_register.py` 使用的是旧装饰器 `@register_tool` 是空装饰器，不会注册到 `tool_registry`！

**验证**：`当前 time 工具在 registry 中数量为 0`

**修复方案**：
```python
# time_register.py 修正
from app.services.tools.registry import tool_registry, ToolCategory

def _register_time_tools():
    """注册所有time工具到tool_registry"""
    from app.services.tools.time.time_tools import (
        time_now, time_format, time_diff,
        timer_set, timer_clear,
        time_utc_to_local, time_local_to_utc,
        time_is_weekend, time_is_holiday,
    )
    
    registry_map = {
        "time_now": time_now,
        "time_format": time_format,
        "time_diff": time_diff,
        "timer_set": timer_set,
        "timer_clear": timer_clear,
        "time_utc_to_local": time_utc_to_local,
        "time_local_to_utc": time_local_to_utc,
        "time_is_weekend": time_is_weekend,
        "time_is_holiday": time_is_holiday,
    }
    
    for name, impl in registry_map.items():
        tool_registry.register(
            name=name,
            description=f"{name} - 时间相关功能",
            category=ToolCategory.TIME,
            implementation=impl
        )

# 模块加载时自动执行
_register_time_tools()
```

#### 缺陷2：FileReactAgent 不兼容（待修复）

**当前代码参数**：
```python
# file_react.py
def __init__(self, llm_client, session_id, intent_type, 
             api_base=None, api_key=None, model=None, ...):
```

**设计要求参数**：
```python
def __init__(self, tool_category=None, config=None, ...):
```

**冲突**：参数签名完全不兼容！

**修复方案**：使用 Mixin 方案

```python
# 方案A：Mixin混合类（推荐）
from app.services.tools.mixin import ToolLoaderMixin

class FileReactAgent(ToolLoaderMixin, BaseAgent):
    def __init__(
        self,
        llm_client,
        session_id,
        intent_type="file",
        tool_category=None,  # 新增参数
        api_base=None,
        api_key=None,
        model=None,
        config=None,        # 新增参数
        **kwargs
    ):
        # 提取tool_category优先
        effective_category = tool_category or (config or {}).get("tool_category")
        
        super().__init__(
            llm_client=llm_client,
            session_id=session_id,
            tool_category=effective_category,
            max_steps=kwargs.get("max_steps", 100),
            **kwargs
        )
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self.config = config
```

#### 缺陷3：函数名冲突

| 设计中 | 已存在 | 冲突 |
|--------|--------|------|
| get_tools_from_registry_by_category | get_tools_from_file_registry | ❌ 需别名 |
| get_tools_by_category | - | ❌ 需别名 |

**修复**：在 `registry.py` 添加别名

```python
# 别名映射确保外部调用兼容
get_tools_from_file_registry = get_tools_from_registry_by_category
```

#### 缺陷4：循环导入风险

**修复**：使用延迟导入

```python
def _load_tools(self):
    if not self.tool_category:
        return {}
    # 延迟导入，避免循环
    from app.services.tools.registry import get_tools_from_registry_by_category
    return get_tools_from_registry_by_category(self.tool_category)
```

#### 缺陷5：BaseAgent 签名变更（已缓解）

**状态**：通过 `**kwargs` 和 `ToolLoaderMixin` 兼容旧参数

**注意**：所有旧代码调用处必须更新为使用 AgentFactory

#### 缺陷6：缺失参数传递

**修复**：
```python
class FileReactAgent(ToolLoaderMixin, BaseAgent):
    def __init__(self, ..., tool_category=None, config=None, **kwargs):
        if tool_category is None and config and "tool_category" in config:
            tool_category = config.get("tool_category")
        # ...
```

#### 缺陷7：回退逻辑不完整

**修复**：
```python
@classmethod
def create(cls, intent_type, llm_client, session_id, config, **kwargs):
    AgentClass = cls._AGENTS.get(intent_type)
    if not AgentClass:
        from app.services.agent.base_react import BaseReact
        return BaseReact(llm_client, session_id, config=config, **kwargs)
    # ...
```

---

## 三、目标架构（完整版）

```
tool_registry (唯一注册中心)
    ├─ category="file"     → 17个工具
    ├─ category="time"     → 9个工具
    ├─ category="shell"    → 待实现
    ├─ category="network"  → 待实现
    ├─ category="env"      → 待实现
    ├─ category="desktop"  → 待实现
    └─ category="chat"     → Prompt模板

AgentFactory.create(intent_type)
    ├─ "file"    → FileReactAgent
    ├─ "time"    → TimeReactAgent ✅ 新增
    ├─ "shell"   → ShellReactAgent (待实现)
    ├─ "network" → NetworkReactAgent (待实现)
    ├─ "env"     → EnvReactAgent (待实现)
    ├─ "desktop" → DesktopReactAgent (待实现)
    └─ "chat"   → BaseReact
```

---

## 三、工具分类状态（修正版）

| 分类 | 工具数量 | 注册方式 | Agent | 状态 |
|------|----------|-----------|-------|------|
| file | 17 | tool_registry | FileReactAgent | ⚠️ 待集成tool_category |
| time | 9 | tool_registry ✅ | TimeReactAgent | ✅ 已完成 |
| shell | 0 | 待实现 | ShellReactAgent | 🟡 规划中 |
| network | 0 | 待实现 | NetworkReactAgent | 🟡 规划中 |
| env | 0 | 待实现 | EnvReactAgent | 🟡 规划中 |
| desktop | 0 | 待实现 | DesktopReactAgent | 🟡 规划中 |
| chat | - | Prompt | BaseReact | ✅ 完成 |

**验证命令**：
```bash
# 验证time工具注册
python -c "from app.services.tools.registry import tool_registry; print(tool_registry.list_tools('time'))"
# 应输出: 9个工具名称
```

---

## 四、核心组件设计

### 4.1 AgentFactory（新建）

**当前限制**:
- 仅支持已实现的Agent类型
- file支持待集成tool_category参数
- time支持（新实现）

```python
# 文件位置: app/services/agent/agent_factory.py
# ============================================================

from typing import Dict, Any, Optional, Type
from app.services.agent.base_react import BaseAgent
from app.services.agent.file_react import FileReactAgent
from app.services.agent.time_react import TimeReactAgent  # 新增导入
from app.services.tools.registry import tool_registry, ToolCategory


class AgentFactory:
    """
    Agent工厂 - 统一创建Agent实例
    
    根据intent_type创建对应的Agent，并自动加载该Agent需要的工具。
    
    使用方式:
        agent = AgentFactory.create(
            intent_type="file",  # 或 "time", "network", "desktop", "chat"
            llm_client=llm_client,
            session_id=session_id,
            config=config
        )
    """

    # Agent类映射（完整版）
    _AGENTS: Dict[str, Type[BaseAgent]] = {
        "file": FileReactAgent,
        "time": TimeReactAgent,       # ✅ 新增
        # "shell": ShellReactAgent,   # Phase 3
        # "network": NetworkReactAgent, # Phase 3
        # "env": EnvReactAgent,     # Phase 3
        # "desktop": DesktopReactAgent,# Phase 3
    }
    
    # Agent需要的工具分类（完整版）
    _TOOL_CATEGORIES: Dict[str, Optional[ToolCategory]] = {
        "file": ToolCategory.FILE,
        "time": ToolCategory.TIME,    # ✅ 新增
        # "shell": ToolCategory.SHELL, # Phase 3
        # "network": ToolCategory.NETWORK,  # Phase 3
        # "env": ToolCategory.ENV,      # Phase 3
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

### 4.2 ToolLoaderMixin（新增）

```python
# 文件位置: app/services/tools/mixin.py
# ============================================================

from typing import Dict, Callable, Optional, Any
from app.services.tools.registry import (
    tool_registry,
    get_tools_from_registry_by_category,
    ToolCategory
)


class ToolLoaderMixin:
    """
    工具加载混入类
    
    使用方式:
        class FileReactAgent(ToolLoaderMixin, BaseAgent):
            pass
    
    或:
        class FileReactAgent(BaseAgent):
            def _load_tools(self):
                return super()._load_tools()  # 使用混入的方法
    """
    
    def _load_tools(
        self, 
        category: Optional[ToolCategory] = None
    ) -> Dict[str, Callable]:
        """
        从registry按分类加载工具
        
        Args:
            category: 工具分类
        
        Returns:
            {工具名: 工具函数}
        """
        if not category:
            return {}
        
        return get_tools_from_registry_by_category(category)
    
    def _load_tools_by_names(
        self, 
        tool_names: list[str]
    ) -> Dict[str, Callable]:
        """
        按名称加载特定工具
        
        Args:
            tool_names: 工具名称列表
        
        Returns:
            {工具名: 工具函数}
        """
        result = {}
        for name in tool_names:
            impl = tool_registry.get_exact_implementation(name)
            if impl:
                result[name] = impl
        return result
    
    def _load_all_tools(self) -> Dict[str, Callable]:
        """加载所有已注册的工具"""
        return tool_registry.list_all_tools()
```

### 4.4 TimeReactAgent（新增）

```python
# 文件位置: app/services/agent/time_react.py
# ============================================================

from typing import Dict, Any, Optional
from app.services.agent.base_react import BaseAgent
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory


class TimeReactAgent(ToolLoaderMixin, BaseAgent):
    """
    时间工具Agent
    
    使用time工具执行时间相关任务，如获取当前时间、格式化时间、计算时间差等。
    
    使用方式:
        agent = TimeReactAgent(
            llm_client=llm_client,
            session_id=session_id,
            tool_category=ToolCategory.TIME
        )
    """
    
    def __init__(
        self,
        llm_client: Any,
        session_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = 50,
        **kwargs
    ):
        # 默认使用TIME分类
        effective_category = tool_category or ToolCategory.TIME
        
        super().__init__(
            llm_client=llm_client,
            session_id=session_id,
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        # 时间工具Agent使用简化的prompt模板
        self.system_prompt = """你是一个时间助手，可以使用时间工具来：
- 获取当前时间 (time_now)
- 格式化时间戳 (time_format)
- 计算时间差 (time_diff)
- 设置定时器 (timer_set, timer_clear)
- 时区转换 (time_utc_to_local, time_local_to_utc)
- 判断日期 (time_is_weekend, time_is_holiday)

请直接回答用户的时间相关问题。"""

### 4.5 BaseAgent改进

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

## 五、实施计划（修正版）

### Phase 1: 创建AgentFactory（高优先级）

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|------|
| T1.1 | agent_factory.py | 创建AgentFactory类 | ✅ 已完成 |
| T1.2 | registry.py | 添加get_tools_by_category | ✅ 已完成 |
| T1.3 | base_react.py | 改造BaseAgent支持tool_category | ⚠️ 已Mixin缓解 |
| T1.4 | react_sse_wrapper.py | 使用AgentFactory | ✅ 已完成 |
| **T1.5** | **file_react.py** | **支持tool_category参数** | 🔴 **待修复** |

### Phase 2: 集成time工具（高优先级）

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|------|
| T2.1 | time_register.py | 改为注册到tool_registry | ✅ 已完成 |
| T2.2 | agent/time_react.py | 新建TimeReactAgent | 🟡 规划中 |
| T2.3 | time/__init__.py | 更新导出 | ✅ 已完成 |

### Phase 3: 创建Network/DesktopAgent（中优先级）

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|------|
| T3.1 | network/ | 新建目录结构 | 🟡 规划中 |
| T3.2 | network_tools.py | 实现网络工具 | 🟡 规划中 |
| T3.3 | network_register.py | 注册到registry | 🟡 规划中 |
| T3.4 | agent/network_react.py | 新建NetworkReactAgent | 🟡 规划中 |
| T3.5 | desktop/ | 同上 | 🟡 规划中 |

### Phase 4: 混合工具支持（扩展）

| 任务 | 文件 | 内容 | 状态 |
|------|------|------|------|
| T4.1 | BaseAgent | 支持多分类 | 🟡 规划中 |
| T4.2 | ToolExecutor | 跨分类执行 | 🟡 规划中 |

---

## 六、代码实现（完整版）

### 6.1 AgentFactory实现

```python
# ============================================================
# app/services/agent/agent_factory.py
# ============================================================

from typing import Dict, Any, Optional, Type
from app.services.agent.base_react import BaseAgent
from app.services.agent.file_react import FileReactAgent
from app.services.agent.time_react import TimeReactAgent  # ✅ 新增
from app.services.tools.registry import tool_registry, ToolCategory


class AgentFactory:
    """
    Agent工厂 - 统一创建Agent实例
    
    使用方式:
        agent = AgentFactory.create(
            intent_type="file",  # 或 "time", "shell", "network", "env", "desktop", "chat"
            llm_client=llm_client,
            session_id=session_id,
            config=config
        )
    """
    
    _AGENTS: Dict[str, Type[BaseAgent]] = {
        "file": FileReactAgent,
        "time": TimeReactAgent,       # ✅ 新增
    }
    
    _TOOL_CATEGORIES: Dict[str, Optional[ToolCategory]] = {
        "file": ToolCategory.FILE,
        "time": ToolCategory.TIME,    # ✅ 新增
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


### 6.2 ToolLoaderMixin实现

```python
# ============================================================
# app/services/tools/mixin.py
# ============================================================

from typing import Dict, Callable, Optional
from app.services.tools.registry import (
    tool_registry,
    get_tools_from_registry_by_category,
    ToolCategory
)


class ToolLoaderMixin:
    """
    工具加载混入类
    
    使用方式:
        class FileReactAgent(ToolLoaderMixin, BaseAgent):
            pass
    """
    
    def _load_tools(
        self, 
        category: Optional[ToolCategory] = None
    ) -> Dict[str, Callable]:
        """从registry按分类加载工具"""
        if not category:
            return {}
        return get_tools_from_registry_by_category(category)
    
    def _load_tools_by_names(
        self, 
        tool_names: list[str]
    ) -> Dict[str, Callable]:
        """按名称加载特定工具"""
        result = {}
        for name in tool_names:
            impl = tool_registry.get_exact_implementation(name)
            if impl:
                result[name] = impl
        return result
    
    def _load_all_tools(self) -> Dict[str, Callable]:
        """加载所有已注册的工具"""
        return tool_registry.list_all_tools()


### 6.3 TimeReactAgent实现

```python
# ============================================================
# app/services/agent/time_react.py
# ============================================================

from typing import Any, Optional
from app.services.agent.base_react import BaseAgent
from app.services.tools.mixin import ToolLoaderMixin
from app.services.tools.registry import ToolCategory


class TimeReactAgent(ToolLoaderMixin, BaseAgent):
    """
    时间工具Agent
    """
    
    def __init__(
        self,
        llm_client: Any,
        session_id: str,
        tool_category: Optional[ToolCategory] = None,
        max_steps: int = 50,
        **kwargs
    ):
        effective_category = tool_category or ToolCategory.TIME
        
        super().__init__(
            llm_client=llm_client,
            session_id=session_id,
            tool_category=effective_category,
            max_steps=max_steps,
            **kwargs
        )
        
        self.system_prompt = """你是一个时间助手，可以回答时间相关问题。"""
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

## 七、验证标准（修正版）

| 验证项 | 预期结果 | 状态 |
|--------|----------|------|
| AgentFactory.create("file") | 返回FileReactAgent | ⚠️ 待修复tool_category |
| file工具 registry数量 | 17 | ✅ 已验证 |
| time工具注册到registry | 9 | ✅ 已修复 |
| react_sse_wrapper使用工厂 | 正常工作 | ✅ 已完成 |
| **FileReactAgent支持tool_category** | 待实现 | 🔴 **待修复** |

### 验证检查清单

在继续下一步前，请确认：

- [x] ✅ time工具已注册到registry（9个工具）
- [x] ✅ 文档声称与事实一致
- [x] ✅ 移除旧注册系统引用
- [ ] ⚠️ FileReactAgent支持tool_category（进行中）
- [ ] ⚠️ BaseAgent兼容性测试通过

---

## 八、修正后的实施重点

### 🔴 高优先级（在下一步必须完成）

1. **T1.5: FileReactAgent 支持 tool_category**
   - 创建 `ToolLoaderMixin`
   - 修改 `FileReactAgent.__init__` 支持 `tool_category` 和 `config` 参数
   - 使用 Mixin 方案

2. **更新所有 Agent 工厂调用**
   - 将 `react_sse_wrapper.py` 中所有直接实例化改为使用 `AgentFactory.create()`

### 🟡 规划中

3. 创建 Shell/Network/Env/Desktop Agent
4. 完整混合工具支持

---

## 九、已做工作和待做工作

### ✅ 已完成
1. ✅ time工具注册到tool_registry（9个函数）
2. ✅ 移除 `_TOOL_REGISTRY`/`register_tool` 旧代码
3. ✅ 更新 registry.py 移除旧兼容代码
4. ✅ 添加时间工具注册函数
5. ✅ 创建 test_registry.py 测试文件

### ⚠️ 进行中
1. FileReactAgent集成tool_category
2. 更新所有Agent工厂调用

### 🟡 规划中
1. Shell/Network/Env/Desktop Agent创建
2. 完整混合工具支持

---

**更新时间**: 2026-04-26 17:00:00
**版本**: v1.2
**更新说明**: 补充ToolLoaderMixin、TimeReactAgent完整实现，更新目标架构