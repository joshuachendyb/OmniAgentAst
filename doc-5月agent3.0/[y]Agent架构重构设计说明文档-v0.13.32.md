# Agent 架构重构设计说明文档 (v0.13.32)

**文档类型**: LLD (详细设计文档)
**版本**: v0.13.32
**作者**: 小强
**日期**: 2026-05-24
**状态**: 已实现
**更新**: 2026-05-24 小沈 修正INTENT_TO_CATEGORY映射不一致

---

## 1. 模块概述

### 1.1 重构目标

将 9 个 Agent 子类（FileReactAgent, ShellReactAgent, SystemReactAgent, NetworkReactAgent, DocumentReactAgent, DatabaseReactAgent, TimeReactAgent, CodeExecutionReactAgent, DesktopReactAgent）精简为 2 个类 + 声明式配置注册表。

### 1.2 重构依据

8 个子类代码完全相同，唯一差异是 **Prompt 模板 + ToolCategory**，这是配置差异而非类型差异。DesktopReactAgent 必须独立保留（交互范式不同、安全模型不同、扩展方向不同）。

### 1.3 核心成果

| 指标 | 改造前 | 改造后 | 变化 |
|------|--------|--------|------|
| Agent 类数 | 9 | 2 | -7 |
| 代码行数 | ~2900 | ~580 | -2320 |
| 配置变更方式 | 新建类+修改factory | 修改AGENT_REGISTRY字典 | 零代码新增 |

---

## 2. 详细设计目标

- **消除重复**: 8个相同子类合并为1个配置驱动通用类
- **声明式配置**: Agent差异项（Prompt/Category/回滚/步数/别名）用dataclass描述
- **向后兼容**: 旧类名(FileReactAgent等)通过`__init__.py`的`__getattr__`重定向
- **Desktop独立**: 保留DesktopReactAgent，不强制纳入通用模式

---

## 3. 数据模型 / 配置设计

### 3.1 AgentConfig (agent_config.py)

    @dataclass
    class AgentConfig:
        intent_type: str              # 主意图名 (如 "file")
        category: ToolCategory        # 工具分类枚举
        prompt_module: str            # Prompt模块路径 (延迟导入)
        prompt_class_name: str        # Prompt类名
        category_display_name: str    # 中文显示名
        rollback_enabled: bool = False  # 是否启用回滚
        max_steps: int = 100          # 最大步数
        aliases: List[str] = []       # 意图别名 (如 "time"→"system")
        _prompt_class: Optional[Type] = None  # 懒加载缓存

**设计要点**:
- `prompt_module` + `prompt_class_name` 实现延迟导入，避免循环依赖
- `prompt_class` property 首次访问时 `importlib.import_module` + `getattr`，后续走缓存
- `aliases` 支持 CRSS 返回的旧意图名（如 "time"/"shell"/"environment"）路由到正确的 AgentConfig

### 3.2 AGENT_REGISTRY (agent_config.py)

    AGENT_REGISTRY: Dict[str, AgentConfig] = {
        "file":     AgentConfig(intent_type="file",    category=FILE,    prompt=FileOperationPrompts, rollback=True,  aliases=[]),
        "system":   AgentConfig(intent_type="system",  category=SYSTEM,  prompt=SystemPrompts,        rollback=False, aliases=["shell","meta","time","environment","env","code_execution"]),
        "network":  AgentConfig(intent_type="network", category=NETWORK, prompt=NetworkPrompts,       rollback=False, aliases=[]),
        "document": AgentConfig(intent_type="document",category=DOCUMENT,prompt=DocumentPrompts,      rollback=False, aliases=["database"]),
        "desktop":  AgentConfig(intent_type="desktop", category=DESKTOP, prompt=DesktopPrompts,       rollback=False, aliases=[]),
    }

**意图合并映射**:
- SHELL + TIME + ENVIRONMENT + CODE_EXECUTION → `system` (ToolCategory.SYSTEM)
- META工具 → 注册到SYSTEM (meta_register.py中category=ToolCategory.SYSTEM)
- DATABASE → `document` (ToolCategory.DOCUMENT)
- 原因: shell/meta工具已注册为SYSTEM分类，CRSS的TYPE_CATEGORY_MAP已同步更新
- 注意: ToolCategory.SHELL和ToolCategory.META枚举值保留(兼容性)，但无工具直接注册到它们

### 3.3 resolve_agent_config(intent_type)

遍历 AGENT_REGISTRY，先匹配 intent_type，再匹配 aliases。无匹配则 raise ValueError。

---

## 4. 核心类设计

### 4.1 UniversalReactAgent (universal_react.py)

**继承链**: `UniversalReactAgent(ReactAgentMixin, RollbackMixin, BaseAgent)`

**职责**: 配置驱动的通用 ReAct Agent，替代 8 个冗余子类。

#### __init__ 流程

    def __init__(self, llm_client, task_id, config, tool_category=None, max_steps=None, candidates=None):
        1. 校验 task_id 非空
        2. 确定 effective_category = tool_category or config.category
        3. 确定 effective_max_steps = max_steps or config.max_steps
        4. super().__init__(llm_client, task_id, effective_category, effective_max_steps)
        5. _init_tools_and_executor(effective_category)    # Mixin: 加载工具+创建执行器
        6. _init_llm_strategies()                          # Mixin: 创建LLM策略+适配器
        7. _init_task_tracking(enable=config.rollback_enabled)  # Mixin: 任务追踪
        8. _init_candidates(candidates)                    # Mixin: 候选意图
        9. self.prompts = config.prompt_class()             # 延迟加载Prompt实例

#### 抽象方法实现

| 方法 | 实现 | 说明 |
|------|------|------|
| `_get_llm_response()` | `await self._call_llm()` | 委托Mixin的LLM调用 |
| `_execute_tool(action, params)` | 别名解析→参数归一化→executor.execute | 含tool_aliases解析 |
| `_get_system_prompt()` | `self._build_system_prompt(config.category_display_name)` | Mixin构建含工具描述的Prompt |
| `_get_task_prompt(task)` | `self.prompts.get_task_prompt(task)` | 委托Prompt模板类 |

#### Hook 方法

| Hook | 逻辑 |
|------|------|
| `_on_session_init` | 若 rollback_enabled 且无 task_id，创建追踪任务 |
| `_on_before_loop` | 空实现 |
| `_on_after_loop` | 若 rollback_enabled 且任务由Agent创建，complete_task |

#### run() 方法（非流式入口）

带 session 管理的完整运行：创建任务→run_stream→收集final/error事件→返回AgentResult→finally中complete_task。

### 4.2 DesktopReactAgent (desktop_react.py)

**继承链**: `DesktopReactAgent(ReactAgentMixin, BaseAgent)`

**与UniversalReactAgent的关键差异**:

| 差异点 | UniversalReactAgent | DesktopReactAgent |
|--------|---------------------|-------------------|
| 交互范式 | 文本ReAct循环 | 视觉循环(screenshot→click/type→screenshot) |
| RollbackMixin | 继承，可回滚 | 不继承，rollback()→False |
| Prompt | 配置驱动(config.prompt_class) | 硬编码DesktopPrompts |
| _execute_tool | 含alias解析 | 直接归一化+execute |
| 扩展方向 | 声明式配置 | 可能增加视觉理解能力 |

### 4.3 AgentFactory (agent_factory.py)

改造为配置驱动的工厂：

    def create(cls, intent_type, ...):
        config = resolve_agent_config(intent_type)
        if config.intent_type == "desktop":
            return DesktopReactAgent(...)
        return UniversalReactAgent(config=config, ...)

**向后兼容注册**: 模块加载时遍历AGENT_REGISTRY，填充`_AGENTS`和`_TOOL_CATEGORIES`字典（含别名）。

### 4.4 RollbackMixin (mixins/rollback_mixin.py)

可插拔回滚能力，从 FileReactAgent 提取：

- `rollback(step_number=None)`: step_number=None→全量回滚(rollback_session)，否则按步骤回滚(rollback_operation)
- 依赖 executor.execute('rollback_session'/'rollback_operation', {...})
- 回滚后设置 `self.status = AgentStatus.ROLLED_BACK`

---

## 5. 消息构建模块 (message_builder.py)

### 5.1 核心职责

统一管理 conversation_history 的写操作、observation 构建、消息注入。

### 5.2 关键方法

| 方法 | 职责 |
|------|------|
| `init_history(sys_prompt, task_prompt)` | 初始化 system+user 消息 |
| `add_assistant(content)` | 追加 assistant 消息 |
| `add_observation(observation_text, fc_context)` | 追加 observation（含FC协议处理） |
| `prepare_messages_for_llm()` | 合并 history+temp_history 发给 LLM |
| `inject_tools_info(history, tools_content)` | 在第一个非system消息前注入工具描述 |
| `trim_history()` | 容量感知的对话历史裁剪 |

### 5.3 FC 协议处理

`add_observation` 在 FC 模式下注入两条消息：

    {"role": "assistant", "content": None, "tool_calls": [...]}
    {"role": "tool", "content": observation_text, "tool_call_id": "..."}

**P0修复**: `_total_chars()` 必须显式处理 `content: None`：
- `msg.get("content", "")` 在 key 存在但值为 None 时返回 None（**不使用默认值**）
- `len(None)` → TypeError
- 修复: `len(content) if content is not None else 0`

### 5.4 裁剪算法 (trim_history)

1. 估算总字符 → 低于80%阈值直接跳过
2. 分类消息: system_msgs / obs_list / assistant_msgs
3. observation去重(_dedup_by_fingerprint, FC消息跳过去重)
4. 保留最新10条assistant, 30条observation
5. 从最旧observation开始移除，直到满足预算
6. FC配对裁剪(_trim_fc_pairs): 确保tool_call与tool_response严格配对
7. 确保至少system+user两条消息

---

## 6. LLM 策略模块

### 6.1 ReactAgentMixin._init_llm_strategies()

    1. 创建 TextStrategy (纯文本模式)
    2. 若 llm_client + api_base 可用:
       - 创建 LLMAdapter(api_base, api_key, model)
       - 生成 openai_tools = tool_registry.to_openai_tools(category)
       - 创建 ToolsStrategy(tools=openai_tools)
       - use_function_calling = True
    3. 否则: 降级到 text 模式

### 6.2 LLMAdapter.detect_strategy()

首次调用时探测 LLM 是否支持 FC：发一个带 tools 参数的请求，若返回 tool_calls → "tools"，否则 → "text"。探测结果缓存，瞬态失败(429/timeout)指数退避重试3次。

### 6.3 策略选择流程

    _call_llm():
        if _strategy is None:  # 首次调用
            strategy = await adapter.detect_strategy()
            _strategy = tools_strategy if strategy=="tools" else text_strategy
        return await _strategy.execute(messages, ...)

---

## 7. 意图路由链路

### 7.1 完整调用链

    chat_router.py → react_sse_wrapper.py → AgentFactory.create(intent_type)
        → resolve_agent_config(intent_type)
        → UniversalReactAgent(config=config) / DesktopReactAgent()

### 7.2 CRSS → Agent 映射

CRSS 评分器使用 `TYPE_CATEGORY_MAP` 将 CRSS 类型映射到 ToolCategory：

    TYPE_CATEGORY_MAP = {
        "FILE": FILE, "SHELL": SYSTEM, "TIME": SYSTEM,
        "NETWORK": NETWORK, "DESKTOP": DESKTOP,
        "ENV": SYSTEM, "SYSTEM": SYSTEM,
        "DATABASE": DOCUMENT, "DOCUMENT": DOCUMENT,
        "CODE_EXECUTION": SYSTEM,
    }

> **修正说明**: TIME映射为SYSTEM(非META)，与meta_register.py实际注册到SYSTEM一致。INTENT_TO_CATEGORY已同步修正。

CRSS 返回的 intent_type（如 "time"/"shell"/"environment"）通过 AGENT_REGISTRY 的 aliases 路由到正确的 AgentConfig。

### 7.3 Prompt Logger 集成

react_sse_wrapper.py 中 prompt logger 改用 `resolve_agent_config(intent_type)` 解析 intent→prompt 映射，替代硬编码的 if/elif 链。解析失败时降级到 FileOperationPrompts。

---

## 8. 工具注册变更

### 8.1 分类合并

| 原分类 | 目标分类 | 变更文件 |
|--------|----------|----------|
| SHELL | SYSTEM | shell_register.py: category=ToolCategory.SYSTEM |
| META | SYSTEM | meta_register.py: category=ToolCategory.SYSTEM |

### 8.2 System Agent 工具清单 (24个)

- System 原生工具 (10): get_system_info, net_connections, event_log, list_processes, kill_process, service_control, task_control, get_env, set_env, registry_control
- Shell 工具 (4): execute_shell_command, find_command, execute_code, shell_session
- Meta 工具 (10): tool_help, tool_search, pipeline, get_time, time_add, time_diff, query_calendar, timezone_convert, batch_process, timer

### 8.3 SystemPrompts 扩充

`get_system_prompt()` 从仅描述10个system工具扩充为描述全部24个工具，确保 LLM 能发现 execute_shell_command、get_time 等工具。

---

## 9. 向后兼容设计[X杜绝向后兼容的设计,下面的设计是错误]

### 9.1 __init__.py 懒加载

    def __getattr__(name):
        if name == "IntentAgent":     return UniversalReactAgent
        if name == "IntentReactAgent": return UniversalReactAgent
        if name == "FileReactAgent":   return UniversalReactAgent
        ...

旧代码 `from app.services.agent import FileReactAgent` 仍可工作，返回 UniversalReactAgent。

### 9.2 AgentFactory._AGENTS 兼容

模块加载时自动填充 `_AGENTS` 和 `_TOOL_CATEGORIES`（含别名），确保依赖 `_AGENTS` 的代码仍可工作。

---

## 10. 错误处理与边界情况

### 10.1 已修复的 P0 问题

| 问题 | 根因 | 修复 |
|------|------|------|
| `_total_chars()` FC模式崩溃 | `content:None` → `msg.get("content","")` 返回 None → `len(None)` TypeError | 显式判断 `content is not None` |
| test_adapter.py 引用已删除类 | adapter.py 在架构改造中被删除 | 删除 test_adapter.py |

### 10.2 已知的低优先级遗留

| 问题 | 影响 | 评估 |
|------|------|------|
| `ToolCategory.SHELL/META` 枚举值无工具注册 | shell_register.py和meta_register.py均注册到SYSTEM，SHELL/META枚举值无实际工具 | 兼容性需要，暂保留 |
| `INTENT_TO_CATEGORY` 已修正 | shell→SYSTEM, meta→SYSTEM, time→SYSTEM, code_execution→SYSTEM (2026-05-24修正) | 已修复 |

---

## 11. 测试关键点

| 测试场景 | 验证内容 |
|----------|----------|
| resolve_agent_config("file") | 返回 file AgentConfig, rollback=True |
| resolve_agent_config("time") | 通过 alias 路由到 system AgentConfig |
| resolve_agent_config("unknown") | raise ValueError |
| UniversalReactAgent(file config) | prompts 实例为 FileOperationPrompts |
| _total_chars(content=None) | 返回0，不崩溃 |
| AgentFactory.create("shell") | 返回 UniversalReactAgent, category=SYSTEM |
| trim_history FC配对 | tool_call 与 tool_response 严格配对 |

---

## 12. 模块文件清单

| 文件 | 行数 | 职责 |
|------|------|------|
| `agent/agent_config.py` | 101 | AgentConfig dataclass + AGENT_REGISTRY + resolve_agent_config |
| `agent/universal_react.py` | 196 | UniversalReactAgent (配置驱动通用Agent) |
| `agent/desktop_react.py` | 75 | DesktopReactAgent (独立桌面Agent) |
| `agent/agent_factory.py` | 107 | AgentFactory (配置驱动工厂) |
| `agent/mixins/rollback_mixin.py` | 57 | RollbackMixin (可插拔回滚) |
| `agent/mixins/react_agent_mixin.py` | ~280 | ReactAgentMixin (工具加载/策略/追踪) |
| `agent/base_react.py` | ~1300 | BaseAgent (ReAct循环核心) |
| `agent/message_builder.py` | ~385 | MessageBuilder (消息组装+裁剪) |
| `agent/llm_adapter.py` | ~120 | LLMAdapter (FC探测+策略决定) |

**已删除**: file_react.py, shell_react.py, system_react.py, network_react.py, document_react.py, database_react.py, time_react.py, code_execution_react.py, adapter.py, _deprecated_adapter.py, _deprecated_adapter_full.py, test_adapter.py
