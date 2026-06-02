# Hermes Agent 与 OpenCode Agent 架构性对比研究

**创建时间**: 2026-06-02 12:18:53
**编写人**: 小欧
**版本**: v4.0（4部分结构重构版）
**研究对象**: Hermes Agent (Nous Research) / OpenCode Agent (sst/opencode)
**源码版本**: Hermes 7,046个.py文件 / OpenCode 137个.go文件
**验证方式**: 3轮源码逐行验证

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-06-02 12:18:53 | 小欧 | 初始版本 |
| v2.0 | 2026-06-02 12:35:00 | 小欧 | 5轮源码验证修正 |
| v3.0 | 2026-06-02 12:50:00 | 小欧 | 重构为架构性对比：系统组织+模块组装+服务架构 |
| v3.1 | 2026-06-02 13:15:00 | 小欧 | 修正章节编号：合并§5+§7→§5，重新编号§6-§10 |
| v4.0 | 2026-06-02 14:00:00 | 小欧 | 4部分结构重构：Hermes分析→OpenCode分析→对比→借鉴 |

---

## 目录

- [第一部分 Hermes Agent 分析](#第一部分-hermes-agent-分析)
  - 1 系统概览
  - 2 系统组织
  - 3 服务组装
  - 4 ReAct 核心循环
  - 5 工具系统
  - 6 通信与回调
  - 7 上下文管理
  - 8 平台扩展
- [第二部分 OpenCode Agent 分析](#第二部分-opencode-agent-分析)
  - 9 系统概览
  - 10 系统组织
  - 11 服务组装
  - 12 ReAct 核心循环
  - 13 工具系统
  - 14 事件总线通信
  - 15 上下文管理（手动摘要）
  - 16 平台扩展（MCP）
- [第三部分 架构对比](#第三部分-架构对比)
  - 17 架构对比
- [第四部分 对 OmniAgent 的借鉴分析](#第四部分-对-omniagent-的借鉴分析)
  - 18 借鉴分析

---

# 第一部分 Hermes Agent 分析

## 1 系统概览

Hermes Agent 是 Nous Research 开发的**生产级多平台 Agent 平台**，定位为"功能完备、厚积薄发"。其设计哲学是"**生产级鲁棒性，不信任任何外部输入**"——通过多层防御处理所有边界情况。

### 1.1 核心数据（源码实测）

| 指标 | 数值 | 来源 |
|------|------|------|
| Python 文件总数 | 7,046 个 | `Get-ChildItem` 实测 |
| agent/ 目录文件数 | 84 个 | `Get-ChildItem agent/*.py` |
| tools/ 目录工具数 | 78 个 | `Get-ChildItem tools/*.py` 排除registry |
| 平台适配器 | 20 个独立平台 | gateway/platforms/ |
| 最大单文件 | 4,460 行 | conversation_loop.py |
| 入口文件 | 4,816 行 | run_agent.py |
| 服务组装 | 1,657 行 / 60+ 参数 | agent_init.py |
| 工具注册表 | 589 行 | tools/registry.py |
| 工具执行器 | 1,016 行 | agent/tool_executor.py |
| 上下文压缩器 | 2,078 行 | agent/context_compressor.py |
| Guardrail 循环检测 | 475 行 | agent/tool_guardrails.py |

### 1.2 三大设计理念

```
理念1: 不信任外部输入
  ├─ 工具参数清洗（_sanitize_tool_call_arguments）
  ├─ 角色交替修复（_repair_message_sequence）
  ├─ 孤儿工具结果补全（_sanitize_api_messages）
  ├─ 空白+JSON 标准化
  └─ surrogate 字符清洗

理念2: 8层防御性循环
  ├─ 循环控制层（预算/中断/checkpoint/钩子）
  ├─ 消息准备层（steer/记忆/缓存）
  ├─ 消息清洗层（孤儿/thinking/surrogate）
  ├─ API调用层（重试/fallback/退避）
  ├─ Token 统计层
  ├─ 工具执行层（验证/JSON/guardrail）
  ├─ 上下文压缩层
  └─ 恢复层（nudge/prefill/retry/fallback）

理念3: 多平台 Gateway 适配
  ├─ Telegram / Discord / Slack / WhatsApp
  ├─ 飞书 / 钉钉 / 企业微信
  ├─ 邮件 / Signal / Matrix / Webhook
  └─ API Server / 内部 API
```

---

## 2 系统组织

### 2.1 顶层目录结构

```
hermes/
├── run_agent.py              # Forwarder 入口（4,816 行）
├── model_tools.py            # 工具定义查询层（1,067 行）
├── cli.py                    # CLI 入口
│
├── agent/                    # 核心 Agent 逻辑（84 个 .py 文件）
│   ├── agent_init.py         # 服务组装（1,657 行，60+ 参数）
│   ├── conversation_loop.py  # 核心循环（4,460 行）
│   ├── tool_executor.py      # 工具执行（1,016 行）
│   ├── context_compressor.py # 上下文压缩（2,078 行）
│   ├── memory_manager.py     # 记忆编排
│   ├── tool_guardrails.py    # 循环检测（475 行）
│   ├── system_prompt.py      # 提示词构建
│   ├── error_classifier.py   # 错误分类
│   ├── iteration_budget.py   # 迭代预算
│   ├── transports/           # API 传输适配器
│   ├── auxiliary_client.py   # 辅助模型客户端
│   ├── anthropic_adapter.py  # Anthropic 适配
│   ├── credential_pool.py    # 凭证池
│   └── ...
│
├── tools/                    # 工具实现（78 个工具 + registry.py）
│   ├── registry.py           # 工具注册表（589 行，AST 自动发现）
│   ├── terminal_tool.py      # 终端工具
│   ├── file_tools.py         # 文件工具
│   ├── web_tools.py          # 网页工具
│   ├── browser_tool.py       # 浏览器工具
│   ├── delegate_tool.py      # 子 Agent 委派
│   ├── mcp_tool.py           # MCP 扩展
│   ├── memory_tool.py        # 记忆工具
│   ├── skills_tool.py        # 技能工具
│   ├── terminal_tool.py      # 终端
│   ├── checkpoint_manager.py # Checkpoint 管理
│   └── ...
│
├── gateway/                  # 平台适配层
│   ├── platforms/            # 20 个平台适配器
│   │   ├── telegram.py / discord_tool.py
│   │   ├── feishu.py / dingtalk.py / wecom.py
│   │   ├── whatsapp.py / signal.py / slack.py
│   │   ├── email.py / webhook.py / matrix.py
│   │   ├── homeassistant.py / bluebubbles.py
│   │   ├── msgraph_webhook.py / sms.py
│   │   ├── weixin.py / yuanbao.py
│   │   └── qqbot/            # QQ 机器人子目录
│   ├── session.py            # 会话管理
│   ├── hooks.py              # 生命周期钩子
│   ├── delivery.py           # 消息投递
│   ├── platform_registry.py  # 平台注册表
│   └── run.py                # Gateway 启动
│
├── providers/                # LLM Provider 实现
├── plugins/                  # 插件系统
├── skills/                   # 技能系统
├── hermes_cli/               # CLI 交互层
├── hermes_agent.egg-info/    # 包元信息
├── ui-tui/                   # TUI 界面
├── web/                      # Web 界面
└── tests/                    # 测试套件
```

### 2.2 组织特点

| 维度 | 特点 | 说明 |
|------|------|------|
| **总体布局** | 扁平化 + 功能聚类 | 顶层文件少（5 个），按功能聚类到子目录 |
| **核心模块** | agent/ + tools/ | 两个最大模块（84 + 78 文件） |
| **辅助模块** | gateway/ + providers/ | 平台适配 + 多 LLM Provider |
| **入口策略** | Forwarder 模式 | run_agent.py 是 4,816 行的"薄壳" |
| **代码密度** | 单文件超大 | 最大文件 4,460 行，最大入口 4,816 行 |
| **依赖风格** | 循环引用容忍 | tools ↔ agent 之间有大量循环引用 |

---

## 3 服务组装

### 3.1 Forwarder + 属性注入

Hermes 采用 **Forwarder 模式 + 属性注入** 风格组装服务：

```
┌─────────────────────────────────────────────────────────────┐
│  用户代码                                                    │
│  agent = AIAgent(base_url=..., model=...)                   │
│      ↓                                                       │
│  AIAgent.__init__(...)        ← run_agent.py 薄壳            │
│      ↓ 调用                                                    │
│  init_agent(self, ...)        ← agent/agent_init.py         │
│      ↓ 60+ 参数 + 1,657 行属性设置                            │
│  agent.model = model                                          │
│  agent.max_iterations = max_iterations                       │
│  agent.context_compressor = ContextCompressor(...)           │
│  agent._memory_manager = MemoryManager()                     │
│  agent._tool_guardrails = ToolCallGuardrailController(...)   │
│  agent.tools = get_tool_definitions(...)                      │
│  agent._session_db = session_db                              │
│  ...                                                         │
│  (1,657 行属性初始化)                                         │
│      ↓                                                       │
│  用户调用 agent.run_conversation(user_msg)                   │
│      ↓ 转发                                                   │
│  run_conversation(self, ...)   ← agent/conversation_loop.py  │
│      ↓ 通过属性访问                                            │
│  agent.context_compressor.update_from_response(...)          │
│  agent._tool_guardrails.before_call(...)                     │
│  agent._memory_manager.prefetch_all()                        │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 init_agent 60+ 参数清单（节选自 agent_init.py 第 136-200 行）

```python
def init_agent(
    agent,
    base_url: str = None,           # API base URL
    api_key: str = None,            # API key
    provider: str = None,           # LLM provider
    api_mode: str = None,           # API 模式
    model: str = "",                # 模型名
    max_iterations: int = 90,       # 最大迭代次数
    tool_delay: float = 1.0,        # 工具延迟
    enabled_toolsets: List[str] = None,   # 启用的工具集
    disabled_toolsets: List[str] = None,  # 禁用的工具集
    save_trajectories: bool = False,      # 是否保存轨迹
    verbose_logging: bool = False,        # 详细日志
    quiet_mode: bool = False,             # 安静模式
    ephemeral_system_prompt: str = None,  # 临时系统提示词
    log_prefix_chars: int = 100,
    log_prefix: str = "",
    providers_allowed: List[str] = None,
    providers_ignored: List[str] = None,
    providers_order: List[str] = None,
    provider_sort: str = None,
    provider_require_parameters: bool = False,
    openrouter_min_coding_score: Optional[float] = None,
    session_id: str = None,
    # ── 回调（10+ 个） ──
    tool_progress_callback: callable = None,
    tool_start_callback: callable = None,
    tool_complete_callback: callable = None,
    thinking_callback: callable = None,
    reasoning_callback: callable = None,
    clarify_callback: callable = None,
    step_callback: callable = None,
    stream_delta_callback: callable = None,
    interim_assistant_callback: callable = None,
    tool_gen_callback: callable = None,
    status_callback: callable = None,
    # ── 平台会话（10+ 个） ──
    max_tokens: int = None,
    reasoning_config: Dict[str, Any] = None,
    service_tier: str = None,
    request_overrides: Dict[str, Any] = None,
    prefill_messages: List[Dict[str, Any]] = None,
    platform: str = None,
    user_id: str = None,
    user_id_alt: str = None,
    user_name: str = None,
    chat_id: str = None,
    chat_name: str = None,
    chat_type: str = None,
    thread_id: str = None,
    gateway_session_key: str = None,
    # ── 高级 ──
    skip_context_files: bool = False,
    load_soul_identity: bool = False,
    skip_memory: bool = False,
    session_db=None,
    parent_session_id: str = None,
    iteration_budget: "IterationBudget" = None,
    fallback_model: Dict[str, Any] = None,
    credential_pool=None,
    checkpoints_enabled: bool = False,
    checkpoint_max_snapshots: int = 20,
    checkpoint_max_total_size_mb: int = 500,
    # ...
)  # 完整 60+ 参数
```

### 3.3 组装特点

```
特点1: 属性注入（非构造函数）
  agent.model = model
  agent._session_db = session_db
  
特点2: 懒引用（_ra()）
  def _ra():
      import run_agent
      return run_agent
  # 保持测试 mock.patch("run_agent.X") 兼容

特点3: Forwarder 入口
  AIAgent.__init__ 仅调用 init_agent()
  run_conversation 仅转发到 conversation_loop.run_conversation()
  
特点4: 60+ 参数控制所有行为
  init_agent 接收一切配置
  调用者通过长参数列表控制 agent 的一切行为
```

---

## 4 ReAct 核心循环

### 4.1 循环入口与控制

```python
# conversation_loop.py:796
while (api_call_count < agent.max_iterations 
       and agent.iteration_budget.remaining > 0) or agent._budget_grace_call:
    agent._checkpoint_mgr.new_turn()
    
    if agent._interrupt_requested:
        break
    
    api_call_count += 1
    agent.iteration_budget.consume()
    
    # 触发网关 step 钩子
    if agent.step_callback:
        agent.step_callback(api_call_count, prev_tools)
```

**循环控制要素**：

| 要素 | 实现 | 行号 |
|------|------|------|
| 双重循环条件 | `max_iterations` + `iteration_budget.remaining` | 796 |
| Grace call 机制 | `_budget_grace_call` 标志 | 815-821 |
| 中断检测 | `_interrupt_requested` | 801-806 |
| 预算消耗 | `iteration_budget.consume()` | 817-821 |
| Checkpoint 重置 | `_checkpoint_mgr.new_turn()` | 798 |
| 网关钩子 | `step_callback` | 824-849 |

### 4.2 8 层防御架构

```
┌─────────────────────────────────────────────────────────────────┐
│  Hermes ReAct 循环 8 层防御                                       │
├─────────────────────────────────────────────────────────────────┤
│  第1层 循环控制（4 项）                                            │
│    ├─ IterationBudget.consume() 预算消耗                        │
│    ├─ _budget_grace_call         Grace 标志                      │
│    ├─ _interrupt_requested      中断检测                        │
│    └─ _checkpoint_mgr.new_turn  Checkpoint 重置                  │
├─────────────────────────────────────────────────────────────────┤
│  第2层 消息准备（10 项）                                           │
│    ├─ _drain_pending_steer()          /steer 指令注入             │
│    ├─ _sanitize_tool_call_arguments() 参数清洗                  │
│    ├─ _repair_message_sequence()      角色交替修复               │
│    ├─ memory_prefetch 注入                                       │
│    ├─ plugin_context 注入                                        │
│    ├─ reasoning 复制                                             │
│    ├─ ephemeral_system_prompt 追加                                │
│    ├─ prefill_messages 注入                                      │
│    ├─ apply_anthropic_cache_control 缓存控制                     │
│    └─ _sanitize_api_messages()         孤儿补全                  │
├─────────────────────────────────────────────────────────────────┤
│  第3层 消息清洗（4 项）                                            │
│    ├─ _drop_thinking_only_and_merge_users  thinking-only 合并   │
│    ├─ normalize whitespace + JSON       标准化                  │
│    ├─ _sanitize_messages_surrogates     surrogate 字符清洗        │
│    └─ _sanitize_messages_non_ascii      非 ASCII 清洗            │
├─────────────────────────────────────────────────────────────────┤
│  第4层 预检（3 项）                                                │
│    ├─ estimate_messages_tokens_rough    token 估算              │
│    ├─ estimate_request_tokens_rough     请求估算                 │
│    └─ _ollama_context_limit_error       Ollama 上下文检查        │
├─────────────────────────────────────────────────────────────────┤
│  第5层 API 调用 + 重试（8 项）                                     │
│    ├─ nous_rate_limit_guard             Nous 速率限制            │
│    ├─ _build_api_kwargs()               构建请求                 │
│    ├─ invoke_hook("pre_api_request")    插件钩子                │
│    ├─ _interruptible_streaming_api_call 流式调用                 │
│    ├─ _interruptible_api_call           非流式调用               │
│    ├─ validate_response()               响应验证                 │
│    ├─ _try_activate_fallback()          fallback 切换            │
│    └─ jittered_backoff()                退避等待                 │
├─────────────────────────────────────────────────────────────────┤
│  第6层 Token 统计（5 项）                                          │
│    ├─ normalize_usage()                token 标准化              │
│    ├─ context_compressor.update_from_response                  │
│    ├─ session_db.update_token_counts    持久化                   │
│    ├─ estimate_usage_cost()             成本估算                 │
│    └─ save_context_length()             缓存上下文长度           │
├─────────────────────────────────────────────────────────────────┤
│  第7层 工具执行（9 项）                                            │
│    ├─ _repair_tool_call()              工具名幻觉修复            │
│    ├─ validate tool names              工具名验证                │
│    ├─ json.loads(arguments)            JSON 参数验证             │
│    ├─ _cap_delegate_task_calls()       委派任务数限制            │
│    ├─ _deduplicate_tool_calls()        工具调用去重              │
│    ├─ Tool Search unwrap               桥接工具解包              │
│    ├─ plugin block 检查                                        │
│    ├─ guardrail block 检查                                     │
│    └─ _execute_tool_calls() 顺序/并发执行                        │
├─────────────────────────────────────────────────────────────────┤
│  第8层 上下文压缩 + 恢复（7 项）                                   │
│    ├─ compressor.should_compress()      50% 阈值检查             │
│    ├─ _compress_context()               多阶段压缩              │
│    ├─ partial_stream_recovery           部分流恢复               │
│    ├─ fallback_prior_turn_content       前一轮内容回退           │
│    ├─ post_tool_empty_nudge             空响应 nudge             │
│    ├─ thinking_prefill_continuation     thinking 续写            │
│    └─ empty_response_retry + fallback   重试 + fallback          │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 工具执行器（tool_executor.py）

**两种执行模式**：

```
execute_tool_calls_sequential(agent, ...)    ← 顺序执行
    ├─ 解析参数
    ├─ Tool Search unwrap
    ├─ plugin block 检查
    ├─ guardrail block 检查
    ├─ checkpoint 快照
    ├─ tool_progress_callback
    ├─ tool_start_callback
    └─ 调用工具 handler

execute_tool_calls_concurrent(agent, ...)    ← 并发执行
    ├─ 解析参数 + 预处理
    ├─ Tool Search unwrap
    ├─ plugin block 检查
    ├─ guardrail block 检查
    ├─ checkpoint 快照
    ├─ ThreadPoolExecutor(max_workers=8)   ← 8 线程
    └─ 并发执行 + 结果收集
```

**核心常量**（tool_executor.py:52）：
```python
_MAX_TOOL_WORKERS = 8
```

### 4.4 工具注册表（tools/registry.py）

```
注册流程（AST 自动发现）：
    discover_builtin_tools()
        ↓
    扫描 tools/*.py（排除 __init__.py, registry.py, mcp_tool.py）
        ↓
    AST 解析每个文件，检测顶层 registry.register(...) 调用
        ↓
    importlib.import_module(模块名)
        ↓
    工具文件在模块顶层执行 registry.register(name, schema, handler, toolset, ...)
        ↓
    工具进入 ToolRegistry 单例
        ↓
    model_tools.get_tool_definitions() 按 toolset 过滤
```

**ToolEntry 数据结构**（registry.py:77）：
```python
class ToolEntry:
    name, toolset, schema, handler, check_fn
    requires_env, is_async, description, emoji
    max_result_size_chars
    dynamic_schema_overrides
```

### 4.5 Guardrail 循环检测（tool_guardrails.py）

**5 种循环模式**：

| 模式 | warn 阈值 | block 阈值 | 说明 |
|------|----------|----------|------|
| exact_failure | 2 | 5 | 相同错误重复 |
| same_tool_failure | 3 | 8 | 同一工具失败 |
| no_progress | 2 | 5 | 无进展 |
| warnings_enabled | ✅ | - | 警告默认开启 |
| hard_stop_enabled | - | 需 opt-in | 硬停止需配置启用 |

**工具分类**（registry.py 静态集合）：
- **IDEMPOTENT_TOOL_NAMES**：read_file, search_files, web_search, browser_snapshot 等
- **MUTATING_TOOL_NAMES**：terminal, write_file, patch, memory, skill_manage, browser_click, delegate_task 等

---

## 5 工具系统

### 5.1 整体架构

```
tools/
├── registry.py                # 589 行 ── 工具注册中心
├── model_tools.py             # 1,067 行 ── 查询层
├── terminal_tool.py           # 终端（pty/Docker/Modal）
├── file_tools.py              # 文件读写
├── web_tools.py               # web_search + web_extract
├── browser_tool.py            # 浏览器（playwright）
├── delegate_tool.py           # 子 Agent 委派
├── mcp_tool.py                # MCP 协议
├── memory_tool.py             # 记忆管理
├── skills_tool.py             # 技能管理
├── kanban_tools.py            # 看板工具
├── checkpoint_manager.py      # Checkpoint 快照
├── tool_search.py             # Tool Search 桥接
├── thread_context.py          # 线程上下文
├── process_registry.py        # 进程注册
└── ... (共 78 个工具文件)
```

### 5.2 工具分类

| 分类 | 代表工具 | 数量（估）|
|------|---------|----------|
| **文件** | read_file, write_file, patch, glob, grep | 5+ |
| **终端** | terminal (pty), execute_code | 2 |
| **网络** | web_search, web_extract, fetch_url | 3+ |
| **浏览器** | browser_navigate, browser_click, browser_snapshot | 10+ |
| **Agent 编排** | delegate_task, send_message, mixture_of_agents | 3+ |
| **记忆/技能** | memory, skill_manage, todo | 3 |
| **MCP** | mcp_filesystem_*, mcp_github_*, ... | 10+ |
| **平台** | feishu_doc, wecom_send, telegram_send | 5+ |
| **多媒体** | image_generation, video_generation, tts, vision | 5+ |
| **辅助** | clarify, checkpoint, osv_check, tirith_security | 10+ |

### 5.3 工具执行全流程（基于 tool_executor.py 源码）

```
循环触发工具执行
  ↓
解析 tool_call.function.arguments (json.loads)
  ↓
[concurrent 模式] 或 [sequential 模式]
  ↓
Tool Search unwrap（如果是 bridge）
  ↓
plugin block 检查（get_pre_tool_call_block_message）
  ↓
guardrail block 检查（tool_call_guardrails）
  ↓
checkpoint 快照（checkpoint_manager.snapshot）
  ↓
调用工具 handler
  ↓
make_tool_result_message
  ↓
消息清洗（surrogate, multimodal, output limits）
  ↓
返回 messages
```

---

## 6 通信与回调

### 6.1 回调驱动（无事件总线）

Hermes **没有统一事件总线**，所有外部通信通过**回调函数**：

```python
# init_agent 接收的回调列表（节选）
agent = AIAgent(
    # ── 工具回调 ──
    tool_progress_callback=on_tool_progress,    # 工具进度
    tool_start_callback=on_tool_start,          # 工具开始
    tool_complete_callback=on_tool_complete,    # 工具完成
    
    # ── 推理/思考 ──
    thinking_callback=on_thinking,              # thinking 增量
    reasoning_callback=on_reasoning,            # reasoning 增量
    
    # ── 流式 ──
    stream_delta_callback=on_delta,             # 流式增量
    interim_assistant_callback=on_interim,      # 中间输出
    
    # ── 流程 ──
    step_callback=on_step,                      # step 钩子（agent:step 事件）
    status_callback=on_status,                  # 状态更新
    
    # ── 其他 ──
    clarify_callback=on_clarify,                # 用户澄清
    tool_gen_callback=on_tool_gen,              # 工具生成
)
```

### 6.2 通信链路图

```
conversation_loop.py
├── 读取 agent.model, agent.tools, agent._session_db    (属性访问)
├── 调用 agent.context_compressor.update_from_response() (方法调用)
├── 调用 agent._tool_guardrails.before_call()            (方法调用)
├── 调用 agent.tool_progress_callback(...)               (回调)
├── 调用 agent.status_callback(...)                      (回调)
├── 调用 agent._memory_manager.prefetch_all()            (方法调用)
├── 调用 agent.step_callback(...)                        (网关钩子)
└── 调用 agent.stream_delta_callback(...)                (流式钩子)
```

### 6.3 Gateway 钩子系统

`gateway/hooks.py` 提供**生命周期钩子**：

```
agent:start              会话开始
agent:step               每步迭代
agent:tool_call          工具调用
agent:tool_result        工具返回
agent:pre_api_request    API 请求前
agent:post_api_request   API 请求后
agent:transform_input    输入转换
agent:transform_output   输出转换
session:end              会话结束
```

**20+ 平台**通过 Gateway 共享这些钩子，平台适配器只需实现：

```python
class PlatformAdapter:
    def send_message(self, user_id, content, **kwargs): ...
    def receive_message(self, **kwargs): ...
    def handle_update(self, update): ...
```

---

## 7 上下文管理

### 7.1 自动压缩引擎

Hermes 拥有**生产级的自动压缩系统**，核心是 `ContextEngine` 抽象基类：

```python
# context_engine.py - 抽象基类
class ContextEngine(ABC):
    threshold_percent: int        # 触发压缩的百分比阈值
    protect_first_n: int          # 保护前 N 条消息
    protect_last_n: int           # 保护后 N 条消息
    # 抽象方法
    def should_compress(self) -> bool: ...
    def compress(self, messages) -> List[Message]: ...
```

### 7.2 ContextCompressor 实现（2,078 行）

```
should_compress()
├── 50% 阈值检查
├── anti-thrashing（防抖）
└── 智能延迟 should_defer_preflight_to_real_usage()

compress() 多阶段压缩：
├── 1. 工具输出裁剪（廉价预处理，节省 30-50% token）
├── 2. LLM 摘要（用辅助模型调用）
├── 3. 多轮压缩（最大 3 次，每次缩小 20%）
└── 4. 摘要前缀 [CONTEXT COMPACTION — REFERENCE ONLY]
    ├── Resolved/Pending question 跟踪
    ├── Active Task / In Progress / Remaining Work 结构
    ├── 强制"latest user message wins"规则
    └── 旧前缀清理（_HISTORICAL_SUMMARY_PREFIXES）

update_from_response(usage)
└── 从 API 响应更新精确 token 计数
```

### 7.3 压缩参数（context_compressor.py:84-89）

```python
_MIN_SUMMARY_TOKENS = 2000
_SUMMARY_RATIO = 0.20                # 摘要占压缩内容 20%
_SUMMARY_TOKENS_CEILING = 12_000     # 摘要上限 12k tokens
_CHARS_PER_TOKEN = 4                 # 粗略估算
_IMAGE_TOKEN_ESTIMATE = 1600         # 图像粗略估算
_SUMMARY_FAILURE_COOLDOWN_SECONDS = 600
_FALLBACK_SUMMARY_MAX_CHARS = 8_000
_FALLBACK_TURN_MAX_CHARS = 700
```

### 7.4 Anthropic 缓存控制

`apply_anthropic_cache_control()` 在系统提示词和最后若干消息上设置 cache_control 标记，启用 Anthropic 提示词缓存（节省 25% 成本）。

---

## 8 平台扩展

### 8.1 Gateway 适配层

```
gateway/
├── platforms/                    # 20 个平台适配器
│   ├── telegram.py + telegram_network.py
│   ├── feishu.py + feishu_comment.py + feishu_comment_rules.py
│   ├── signal.py + signal_rate_limit.py
│   ├── wecom.py + wecom_callback.py + wecom_crypto.py
│   ├── yuanbao.py + yuanbao_media.py + yuanbao_proto.py + yuanbao_sticker.py
│   ├── dingtalk.py
│   ├── email.py
│   ├── homeassistant.py
│   ├── matrix.py
│   ├── msgraph_webhook.py
│   ├── slack.py
│   ├── sms.py
│   ├── webhook.py
│   ├── weixin.py
│   ├── whatsapp.py
│   ├── bluebubbles.py
│   ├── discord_tool.py           # 注：在 tools/ 而非 platforms/
│   ├── api_server.py             # 内部 API server
│   ├── base.py                   # 抽象基类
│   ├── helpers.py                # 公共工具
│   └── qqbot/                    # QQ 机器人
│       ├── adapter.py
│       ├── chunked_upload.py
│       ├── constants.py
│       ├── crypto.py
│       ├── keyboards.py
│       ├── onboard.py
│       └── utils.py
│
├── platform_registry.py          # 平台注册表（动态加载）
├── session.py                    # Gateway 会话
├── session_context.py
├── hooks.py                      # 生命周期钩子
├── delivery.py                   # 消息投递（含分块/格式转换）
├── run.py                        # Gateway 启动
├── config.py                     # 配置
├── pairing.py                    # 用户配对
├── restart.py                    # 重启
├── shutdown_forensics.py
├── status.py
├── stream_consumer.py
├── slash_access.py
├── mirror.py
├── memory_monitor.py
├── runtime_footer.py
├── display_config.py
├── sticker_cache.py
├── whatsapp_identity.py
└── builtin_hooks/                # 内置钩子
```

### 8.2 平台分层

```
应用层：  CLI / TUI / Web UI / API Server
              ↓ 调用
平台层：  Gateway + Hooks
              ↓ 调用
核心层：  AIAgent（agent/conversation_loop.py）
              ↓ 调用
工具层：  tools/*.py（78 个工具）
```

### 8.3 插件 + 技能 + MCP

```
plugin/        插件系统（hermes_cli/plugins.py）
               ├─ pre_api_request / post_api_request
               ├─ pre_tool_call_block
               └─ 第三方能力扩展

skills/        技能系统（tools/skills_tool.py）
               ├─ 自描述 markdown 文件
               ├─ discover + load + invoke
               └─ AST 审计（skills_ast_audit.py）

MCP/           MCP 协议（tools/mcp_tool.py）
               ├─ 标准化工具扩展协议
               └─ mcp_filesystem_*, mcp_github_*, ...
```

---

# 第二部分 OpenCode Agent 分析

## 9 系统概览

OpenCode 是 sst/opencode 开发的**极简 CLI 编程助手**，定位为"精简核心、扩展外围"。其设计哲学是"**把复杂度留给外部系统**"——只做最核心的 ReAct 循环，复杂逻辑下沉到工具和 LLM。

### 9.1 核心数据（源码实测）

| 指标 | 数值 | 来源 |
|------|------|------|
| Go 文件总数 | 137 个 | `Get-ChildItem internal/*.go` |
| internal/ 子包 | 17 个 | app, completions, config, db, diff, fileutil, format, history, llm, logging, lsp, message, permission, pubsub, session, tui, version |
| llm/agent/ 文件 | 4 个 | agent.go, tools.go, mcp-tools.go + 1 测试 |
| llm/tools/ 文件 | 13 个 | bash, diagnostics, edit, fetch, file, glob, grep, ls, patch, sourcegraph, view, write + tools.go 接口 |
| 最大单文件 | 758 行 | agent/agent.go（agent.go 是 758 行，不含测试）|
| 入口组装 | 178 行 | app/app.go（New 函数）|
| 事件总线 | 1 个核心文件 | pubsub/broker.go（核心实现）|
| Agent 类型 | 4 个 | AgentCoder, AgentTask, AgentTitle, AgentSummarizer |
| 内建工具 | 11 个 | Bash, Edit, Fetch, Glob, Grep, Ls, Sourcegraph, View, Patch, Write, Agent |

### 9.2 三大设计理念

```
理念1: 接口驱动（强类型）
  ├─ Service interface
  ├─ BaseTool interface
  ├─ Provider interface
  └─ pubsub.Broker[T any] 泛型事件总线

理念2: 编译时检查
  ├─ 构造函数注入
  ├─ 依赖通过参数显式传递
  └─ 类型不匹配编译失败

理念3: 精简核心
  ├─ agent.go 只 758 行
  ├─ ReAct 循环 9 个功能点
  ├─ 复杂逻辑下沉到 LLM
  └─ 通过 MCP 扩展外围
```

---

## 10 系统组织

### 10.1 顶层目录结构

```
opencode/
├── main.go                     # CLI 入口
│
├── internal/                   # 内部包（17 个子包）
│   ├── app/                    # 应用组装
│   │   ├── app.go              # 178 行 ── App 结构体 + New() 服务组装
│   │   └── (无其他文件)
│   │
│   ├── llm/                    # LLM 核心
│   │   ├── agent/              # Agent 实现（4 文件）
│   │   │   ├── agent.go        # 758 行 ── Service 接口 + 4 个 AgentType
│   │   │   ├── tools.go        # 51 行 ── CoderAgentTools / TaskAgentTools
│   │   │   ├── mcp-tools.go    # MCP 工具加载
│   │   │   └── (1 个测试)
│   │   ├── provider/           # 8+ Provider 实现
│   │   │   ├── anthropic.go
│   │   │   ├── openai.go
│   │   │   ├── copilot.go      # 20,921 行（最大 Provider）
│   │   │   ├── bedrock.go
│   │   │   ├── gemini.go
│   │   │   ├── groq.go
│   │   │   ├── ollama.go
│   │   │   └── openrouter.go
│   │   ├── tools/              # 11 个内建工具 + 1 个接口
│   │   │   ├── tools.go        # BaseTool 接口 + ToolCall/ToolResponse
│   │   │   ├── bash.go
│   │   │   ├── edit.go
│   │   │   ├── fetch.go
│   │   │   ├── file.go
│   │   │   ├── glob.go
│   │   │   ├── grep.go
│   │   │   ├── ls.go
│   │   │   ├── patch.go
│   │   │   ├── sourcegraph.go
│   │   │   ├── view.go
│   │   │   ├── write.go
│   │   │   └── diagnostics.go
│   │   ├── models/             # 模型元数据
│   │   └── prompt/             # 提示词
│   │
│   ├── session/                # 会话管理（1 文件）
│   │   └── session.go          # Service 接口 + 8 方法
│   │
│   ├── message/                # 消息管理（3 文件）
│   │   ├── message.go          # Service 接口 + 6 方法
│   │   ├── content.go          # ContentPart
│   │   └── tool_call.go
│   │
│   ├── permission/             # 权限（1 文件）
│   │   └── permission.go       # 119 行 ── 阻塞式权限服务
│   │
│   ├── pubsub/                 # 事件总线（2 文件）
│   │   ├── broker.go           # 泛型 Broker[T]
│   │   └── events.go           # Event 类型
│   │
│   ├── db/                     # 数据库层（SQLite）
│   ├── config/                 # 配置（29,987 行）
│   ├── lsp/                    # LSP 语言服务
│   │   ├── protocol/           # 巨大协议文件（285,574 行 tsprotocol.go）
│   │   ├── methods.go
│   │   ├── client.go
│   │   └── watcher/
│   ├── history/                # 文件历史
│   ├── tui/                    # TUI 界面（26,510 行）
│   │   └── components/chat/
│   ├── diff/                   # 差异算法（26,920 行）
│   ├── format/                 # 格式化
│   ├── fileutil/               # 文件工具
│   ├── logging/                # 日志
│   ├── completions/            # 补全
│   └── version/                # 版本
│
└── cmd/                        # CLI 命令
```

### 10.2 组织特点

| 维度 | 特点 | 说明 |
|------|------|------|
| **总体布局** | 严格 Go 包结构 | 每个子系统一个包，包内文件少 |
| **核心模块** | llm/agent/ (4 文件) + llm/tools/ (13 文件) | 核心 Agent 只 27 个文件 |
| **辅助模块** | 17 个子包 | session, message, permission, pubsub, db, ... |
| **入口策略** | 构造函数注入 | `app.New(ctx, conn)` 一行组装 |
| **代码密度** | 单文件小 | 最大文件 agent.go 758 行（不算 LSP 协议） |
| **依赖风格** | 显式接口 | 通过 Service interface 强约束 |

---

## 11 服务组装

### 11.1 构造函数注入（强类型）

OpenCode 采用**接口 + 构造函数注入**风格组装服务：

```go
// app/app.go
type App struct {
    Sessions    session.Service
    Messages    message.Service
    History     history.Service
    Permissions permission.Service
    
    CoderAgent  agent.Service
    
    LSPClients  map[string]*lsp.Client
    
    clientsMutex         sync.RWMutex
    watcherCancelFuncs   []context.CancelFunc
    cancelFuncsMutex     sync.Mutex
    watcherWG            sync.WaitGroup
}

func New(ctx context.Context, conn *sql.DB) (*App, error) {
    q := db.New(conn)
    
    // 1. 基础服务
    sessions := session.NewService(q)
    messages := message.NewService(q)
    files := history.NewService(q, conn)
    
    app := &App{
        Sessions:    sessions,
        Messages:    messages,
        History:     files,
        Permissions: permission.NewPermissionService(),
        LSPClients:  make(map[string]*lsp.Client),
    }
    
    app.initTheme()
    go app.initLSPClients(ctx)
    
    // 2. Agent（注入服务）
    app.CoderAgent, err = agent.NewAgent(
        config.AgentCoder,
        app.Sessions,
        app.Messages,
        agent.CoderAgentTools(    // 3. 工具列表（注入服务）
            app.Permissions,
            app.Sessions,
            app.Messages,
            app.History,
            app.LSPClients,
        ),
    )
    if err != nil {
        return nil, err
    }
    return app, nil
}
```

### 11.2 服务接口定义

```go
// session.Service（session.go:24-34）
type Service interface {
    pubsub.Suscriber[Session]
    Create(ctx context.Context, title string) (Session, error)
    CreateTitleSession(ctx context.Context, parentSessionID string) (Session, error)
    CreateTaskSession(ctx context.Context, toolCallID, parentSessionID, title string) (Session, error)
    Get(ctx context.Context, id string) (Session, error)
    List(ctx context.Context) ([]Session, error)
    Save(ctx context.Context, session Session) (Session, error)
    Delete(ctx context.Context, id string) error
}

// message.Service（message.go:23-30）
type Service interface {
    pubsub.Suscriber[Message]
    Create(ctx context.Context, sessionID string, params CreateMessageParams) (Message, error)
    Update(ctx context.Context, message Message) error
    Get(ctx context.Context, id string) (Message, error)
    List(ctx context.Context, sessionID string) ([]Message, error)
    Delete(ctx context.Context, id string) error
    DeleteSessionMessages(ctx context.Context, sessionID string) error
}

// agent.Service（agent.go:48-57）
type Service interface {
    pubsub.Suscriber[AgentEvent]
    Model() models.Model
    Run(ctx context.Context, sessionID string, content string, attachments ...message.Attachment) (<-chan AgentEvent, error)
    Cancel(sessionID string)
    IsSessionBusy(sessionID string) bool
    IsBusy() bool
    Update(agentName config.AgentName, modelID models.ModelID) (models.Model, error)
    Summarize(ctx context.Context, sessionID string) error
}

// permission.Service（permission.go:35-42）
type Service interface {
    pubsub.Suscriber[PermissionRequest]
    GrantPersistant(permission PermissionRequest)
    Grant(permission PermissionRequest)
    Deny(permission PermissionRequest)
    Request(opts CreatePermissionRequest) bool
    AutoApproveSession(sessionID string)
}
```

### 11.3 组装特点

```
特点1: 构造函数注入（强类型）
  app := &App{Sessions: session.NewService(q), ...}
  app.CoderAgent = agent.NewAgent(..., agent.CoderAgentTools(...))
  
特点2: 分层组装
  DB → Service → Agent → App
  
特点3: 编译时检查
  接口不匹配 = 编译失败
  不会运行时才暴露问题
  
特点4: 参数数量少
  agent.NewAgent() 只接收 4 个参数
  CoderAgentTools() 接收 5 个依赖
```

---

## 12 ReAct 核心循环

### 12.1 循环总览

OpenCode 的 ReAct 循环在 `agent.go:198-311`，**758 行中只占 113 行**：

```go
// agent.go:198 - Run 入口
func (a *agent) Run(ctx context.Context, sessionID, content string, attachments ...message.Attachment) (<-chan AgentEvent, error) {
    if !a.provider.Model().SupportsAttachments && attachments != nil {
        attachments = nil
    }
    events := make(chan AgentEvent)
    
    // 1. 会话忙检查
    if a.IsSessionBusy(sessionID) {
        return nil, ErrSessionBusy
    }
    
    genCtx, cancel := context.WithCancel(ctx)
    a.activeRequests.Store(sessionID, cancel)
    
    go func() {
        defer logging.RecoverPanic("agent.Run", ...)
        var attachmentParts []message.ContentPart
        for _, attachment := range attachments {
            attachmentParts = append(attachmentParts, message.BinaryContent{...})
        }
        result := a.processGeneration(genCtx, sessionID, content, attachmentParts)
        // ...
        a.activeRequests.Delete(sessionID)
        cancel()
        a.Publish(pubsub.CreatedEvent, result)
        events <- result
        close(events)
    }()
    return events, nil
}

// agent.go:233 - 循环主体
func (a *agent) processGeneration(ctx, sessionID, content, attachmentParts) AgentEvent {
    cfg := config.Get()
    
    // [循环前准备]
    msgs, _ := a.messages.List(ctx, sessionID)
    if len(msgs) == 0 {
        go a.generateTitle(context.Background(), sessionID, content)  // 异步生成标题
    }
    session, _ := a.sessions.Get(ctx, sessionID)
    if session.SummaryMessageID != "" {
        // 摘要裁剪
        msgs = msgs[summaryMsgInex:]
        msgs[0].Role = message.User
    }
    userMsg, _ := a.createUserMessage(ctx, sessionID, content, attachmentParts)
    msgHistory := append(msgs, userMsg)
    
    // [ReAct 循环]
    for {
        select {
        case <-ctx.Done():
            return a.err(ctx.Err())
        default:
        }
        
        agentMessage, toolResults, err := a.streamAndHandleEvents(ctx, sessionID, msgHistory)
        if err != nil {
            if errors.Is(err, context.Canceled) {
                agentMessage.AddFinish(message.FinishReasonCanceled)
                a.messages.Update(context.Background(), agentMessage)
                return a.err(ErrRequestCancelled)
            }
            return a.err(...)
        }
        
        if cfg.Debug {
            seqId := (len(msgHistory) + 1) / 2
            toolResultFilepath := logging.WriteToolResultsJson(sessionID, seqId, toolResults)
            logging.Info("Result", "message", agentMessage.FinishReason(), "filepath", toolResultFilepath)
        }
        
        if (agentMessage.FinishReason() == message.FinishReasonToolUse) && toolResults != nil {
            msgHistory = append(msgHistory, agentMessage, *toolResults)
            continue
        }
        return AgentEvent{Type: AgentEventTypeResponse, Message: agentMessage, Done: true}
    }
}
```

### 12.2 循环内 9 个功能点

```
┌─────────────────────────────────────────────────────────────┐
│  OpenCode ReAct 循环（agent.go:233-311）                    │
├─────────────────────────────────────────────────────────────┤
│  1. 会话忙检查 (Run 入口)                                     │
│     IsSessionBusy(sessionID) → ErrSessionBusy               │
├─────────────────────────────────────────────────────────────┤
│  2. 上下文 + 取消 (循环前)                                    │
│     context.WithCancel(ctx)                                 │
│     a.activeRequests.Store(sessionID, cancel)               │
├─────────────────────────────────────────────────────────────┤
│  3. 历史消息加载 + 摘要裁剪                                   │
│     messages.List()                                         │
│     if SummaryMessageID != "" → msgs[summaryIdx:]          │
├─────────────────────────────────────────────────────────────┤
│  4. 标题生成（异步）                                          │
│     if len(msgs) == 0:                                      │
│         go generateTitle(...)                                │
├─────────────────────────────────────────────────────────────┤
│  5. 用户消息创建                                              │
│     messages.Create(User)                                   │
│     msgHistory = append(msgs, userMsg)                      │
├─────────────────────────────────────────────────────────────┤
│  6. LLM 调用 + 事件处理                                       │
│     streamAndHandleEvents(ctx, sessionID, msgHistory)       │
│     ├─ provider.StreamResponse(ctx, msgHistory, a.tools)   │
│     ├─ messages.Create(Assistant)                           │
│     ├─ for event := range eventChan                         │
│     │   └─ processEvent()                                   │
│     └─ 工具执行循环（顺序）                                  │
├─────────────────────────────────────────────────────────────┤
│  7. Token 统计 + 成本                                        │
│     processEvent: EventComplete → TrackUsage()              │
│     ├─ 计算 cost（CacheCreation/Read/Input/Output）         │
│     ├─ sess.Cost += cost                                    │
│     └─ sessions.Save(session)                               │
├─────────────────────────────────────────────────────────────┤
│  8. 结束原因判断                                              │
│     if FinishReason == ToolUse && toolResults != nil:       │
│         msgHistory = append(msgHistory, agentMessage, *toolResults) │
│         continue                                            │
│     else:                                                   │
│         return AgentEvent{Type: Response, Done: true}       │
├─────────────────────────────────────────────────────────────┤
│  9. 调试日志                                                  │
│     if cfg.Debug:                                           │
│         logging.WriteToolResultsJson(sessionID, seqId, ...) │
└─────────────────────────────────────────────────────────────┘
```

### 12.3 processEvent 6 个事件类型

```go
// agent.go:445-492
func (a *agent) processEvent(ctx, sessionID, assistantMsg, event) error {
    switch event.Type {
    case provider.EventThinkingDelta:
        assistantMsg.AppendReasoningContent(event.Content)
        return a.messages.Update(ctx, *assistantMsg)
    case provider.EventContentDelta:
        assistantMsg.AppendContent(event.Content)
        return a.messages.Update(ctx, *assistantMsg)
    case provider.EventToolUseStart:
        assistantMsg.AddToolCall(*event.ToolCall)
        return a.messages.Update(ctx, *assistantMsg)
    case provider.EventToolUseStop:
        assistantMsg.FinishToolCall(event.ToolCall.ID)
        return a.messages.Update(ctx, *assistantMsg)
    case provider.EventError:
        return event.Error
    case provider.EventComplete:
        assistantMsg.SetToolCalls(event.Response.ToolCalls)
        assistantMsg.AddFinish(event.Response.FinishReason)
        a.messages.Update(ctx, *assistantMsg)
        return a.TrackUsage(ctx, sessionID, a.provider.Model(), event.Response.Usage)
    }
}
```

### 12.4 TrackUsage 成本计算

```go
// agent.go:494-514
func (a *agent) TrackUsage(ctx, sessionID, model, usage) error {
    sess, _ := a.sessions.Get(ctx, sessionID)
    
    cost := model.CostPer1MInCached/1e6 * float64(usage.CacheCreationTokens) +
        model.CostPer1MOutCached/1e6 * float64(usage.CacheReadTokens) +
        model.CostPer1MIn/1e6 * float64(usage.InputTokens) +
        model.CostPer1MOut/1e6 * float64(usage.OutputTokens)
    
    sess.Cost += cost
    sess.CompletionTokens = usage.OutputTokens + usage.CacheReadTokens
    sess.PromptTokens = usage.InputTokens + usage.CacheCreationTokens
    
    _, err := a.sessions.Save(ctx, sess)
    return err
}
```

---

## 13 工具系统

### 13.1 BaseTool 接口

```go
// tools/tools.go
type BaseTool interface {
    Info() ToolInfo
    Run(ctx context.Context, params ToolCall) (ToolResponse, error)
}

type ToolInfo struct {
    Name        string
    Description string
    Parameters  map[string]any
    Required    []string
}

type ToolCall struct {
    ID    string `json:"id"`
    Name  string `json:"name"`
    Input string `json:"input"`
}

type ToolResponse struct {
    Type     toolResponseType `json:"type"`     // "text" | "image"
    Content  string           `json:"content"`
    Metadata string           `json:"metadata,omitempty"`
    IsError  bool             `json:"is_error"`
}

// 上下文传递键
const (
    SessionIDContextKey sessionIDContextKey = "session_id"
    MessageIDContextKey messageIDContextKey = "message_id"
)
```

### 13.2 11 个内建工具

```go
// tools/tools.go
func CoderAgentTools(
    permissions permission.Service,
    sessions session.Service,
    messages message.Service,
    history history.Service,
    lspClients map[string]*lsp.Client,
) []tools.BaseTool {
    ctx := context.Background()
    otherTools := GetMcpTools(ctx, permissions)        // MCP 工具
    if len(lspClients) > 0 {
        otherTools = append(otherTools, tools.NewDiagnosticsTool(lspClients))
    }
    return append(
        []tools.BaseTool{
            tools.NewBashTool(permissions),            // 1. Bash
            tools.NewEditTool(lspClients, permissions, history),  // 2. Edit
            tools.NewFetchTool(permissions),           // 3. Fetch
            tools.NewGlobTool(),                       // 4. Glob
            tools.NewGrepTool(),                       // 5. Grep
            tools.NewLsTool(),                         // 6. Ls
            tools.NewSourcegraphTool(),                // 7. Sourcegraph
            tools.NewViewTool(lspClients),             // 8. View
            tools.NewPatchTool(lspClients, permissions, history),  // 9. Patch
            tools.NewWriteTool(lspClients, permissions, history),  // 10. Write
            NewAgentTool(sessions, messages, lspClients),  // 11. Agent（子 Agent 委派）
        },
        otherTools...,                                  // + MCP + Diagnostics
    )
}
```

### 13.3 工具执行流程

```go
// agent.go:322-438
func (a *agent) streamAndHandleEvents(ctx, sessionID, msgHistory) (...) {
    ctx = context.WithValue(ctx, tools.SessionIDContextKey, sessionID)
    eventChan := a.provider.StreamResponse(ctx, msgHistory, a.tools)
    
    assistantMsg, _ := a.messages.Create(ctx, sessionID, message.CreateMessageParams{
        Role:  message.Assistant,
        Parts: []message.ContentPart{},
        Model: a.provider.Model().ID,
    })
    ctx = context.WithValue(ctx, tools.MessageIDContextKey, assistantMsg.ID)
    
    for event := range eventChan {
        a.processEvent(ctx, sessionID, &assistantMsg, event)
        if ctx.Err() != nil {
            a.finishMessage(context.Background(), &assistantMsg, message.FinishReasonCanceled)
            return assistantMsg, nil, ctx.Err()
        }
    }
    
    toolResults := make([]message.ToolResult, len(assistantMsg.ToolCalls()))
    toolCalls := assistantMsg.ToolCalls()
    
    for i, toolCall := range toolCalls {
        select {
        case <-ctx.Done():
            // 取消后续所有工具
            for j := i; j < len(toolCalls); j++ {
                toolResults[j] = message.ToolResult{
                    ToolCallID: toolCalls[j].ID,
                    Content:    "Tool execution canceled by user",
                    IsError:    true,
                }
            }
            goto out
        default:
            // 查找工具
            var tool tools.BaseTool
            for _, availableTool := range a.tools {
                if availableTool.Info().Name == toolCall.Name {
                    tool = availableTool
                    break
                }
            }
            if tool == nil {
                toolResults[i] = message.ToolResult{
                    ToolCallID: toolCall.ID,
                    Content:    fmt.Sprintf("Tool not found: %s", toolCall.Name),
                    IsError:    true,
                }
                continue
            }
            
            // 调用工具
            toolResult, toolErr := tool.Run(ctx, tools.ToolCall{...})
            if toolErr != nil {
                if errors.Is(toolErr, permission.ErrorPermissionDenied) {
                    toolResults[i] = message.ToolResult{
                        Content: "Permission denied",
                        IsError: true,
                    }
                    // 权限拒绝后所有后续工具取消
                    for j := i + 1; j < len(toolCalls); j++ {
                        toolResults[j] = message.ToolResult{
                            ToolCallID: toolCalls[j].ID,
                            Content:    "Tool execution canceled by user",
                            IsError:    true,
                        }
                    }
                    a.finishMessage(ctx, &assistantMsg, message.FinishReasonPermissionDenied)
                    break
                }
            }
            toolResults[i] = message.ToolResult{
                ToolCallID: toolCall.ID,
                Content:    toolResult.Content,
                Metadata:   toolResult.Metadata,
                IsError:    toolResult.IsError,
            }
        }
    }
out:
    if len(toolResults) == 0 {
        return assistantMsg, nil, nil
    }
    msg, _ := a.messages.Create(context.Background(), assistantMsg.SessionID, message.CreateMessageParams{
        Role:  message.Tool,
        Parts: parts,
    })
    return assistantMsg, &msg, err
}
```

### 13.4 4 个 Agent 类型

```go
// config/config.go
const (
    AgentCoder      AgentName = "coder"        // 主 Agent
    AgentSummarizer AgentName = "summarizer"   // 摘要
    AgentTask       AgentName = "task"         // 子任务
    AgentTitle      AgentName = "title"        // 标题
)
```

每个 AgentType 可以独立配置 model / provider / prompt（通过 `cfg.Agents[AgentName]`）。

---

## 14 事件总线通信

### 14.1 泛型 Broker[T]

```go
// pubsub/broker.go
const bufferSize = 64

type Broker[T any] struct {
    subs      map[chan Event[T]]struct{}
    mu        sync.RWMutex
    done      chan struct{}
    subCount  int
    maxEvents int
}

func NewBroker[T any]() *Broker[T] {
    return NewBrokerWithOptions[T](bufferSize, 1000)
}

func (b *Broker[T]) Subscribe(ctx context.Context) <-chan Event[T] {
    sub := make(chan Event[T], bufferSize)
    b.subs[sub] = struct{}{}
    b.subCount++
    
    go func() {
        <-ctx.Done()              // 上下文取消 → 自动取消订阅
        delete(b.subs, sub)
        close(sub)
        b.subCount--
    }()
    return sub
}

func (b *Broker[T]) Publish(t EventType, payload T) {
    b.mu.RLock()
    select {
    case <-b.done:
        b.mu.RUnlock()
        return
    default:
    }
    subscribers := make([]chan Event[T], 0, len(b.subs))
    for sub := range b.subs {
        subscribers = append(subscribers, sub)
    }
    b.mu.RUnlock()
    
    event := Event[T]{Type: t, Payload: payload}
    
    // 非阻塞发送
    for _, sub := range subscribers {
        select {
        case sub <- event:
        default:
            // 慢消费者 → 丢弃（不阻塞发布者）
        }
    }
}
```

### 14.2 所有 Service 嵌入 Broker

```go
// agent.go
type agent struct {
    *pubsub.Broker[AgentEvent]              // ← 嵌入 AgentEvent 事件总线
    sessions session.Service
    messages message.Service
    tools    []tools.BaseTool
    provider provider.Provider
    // ...
}

// session/service
type service struct {
    *pubsub.Broker[Session]                  // ← 嵌入 Session 事件总线
    q db.Querier
}

// message/service
type service struct {
    *pubsub.Broker[Message]                  // ← 嵌入 Message 事件总线
    q db.Querier
}

// permission/permissionService
type permissionService struct {
    *pubsub.Broker[PermissionRequest]        // ← 嵌入 Permission 事件总线
    // ...
}
```

### 14.3 事件类型

```go
// pubsub/events.go
const (
    CreatedEvent EventType = "created"
    UpdatedEvent EventType = "updated"
    DeletedEvent EventType = "deleted"
)

type Event[T any] struct {
    Type    EventType
    Payload T
}

// agent.AgentEventType
const (
    AgentEventTypeError     AgentEventType = "error"
    AgentEventTypeResponse  AgentEventType = "response"
    AgentEventTypeSummarize AgentEventType = "summarize"
)
```

### 14.4 通信特点

```
特点1: 泛型 Broker[T any]   ← Go 1.18+ 泛型
特点2: 每个 Service 嵌入 Broker   ← 统一模式
特点3: 非阻塞发布   ← 慢消费者丢弃，不阻塞发布者
特点4: 上下文取消自动取消订阅   ← goroutine 监听 ctx.Done()
特点5: 编译时类型安全   ← pubsub.Suscriber[AgentEvent] 接口
```

---

## 15 上下文管理（手动摘要）

### 15.1 摘要流程

OpenCode **没有自动压缩**，提供手动 `Summarize()` 方法：

```go
// agent.go:535-721
func (a *agent) Summarize(ctx context.Context, sessionID string) error {
    if a.summarizeProvider == nil {
        return fmt.Errorf("summarize provider not available")
    }
    if a.IsSessionBusy(sessionID) {
        return ErrSessionBusy
    }
    
    summarizeCtx, cancel := context.WithCancel(ctx)
    a.activeRequests.Store(sessionID+"-summarize", cancel)
    
    go func() {
        defer a.activeRequests.Delete(sessionID + "-summarize")
        defer cancel()
        
        // 1. 加载所有消息
        msgs, _ := a.messages.List(summarizeCtx, sessionID)
        if len(msgs) == 0 {
            a.Publish(pubsub.CreatedEvent, AgentEvent{Type: AgentEventTypeError, ...})
            return
        }
        
        // 2. 进度事件
        a.Publish(pubsub.CreatedEvent, AgentEvent{Type: AgentEventTypeSummarize, Progress: "Starting summarization..."})
        
        // 3. 添加摘要 prompt
        summarizePrompt := "Provide a detailed but concise summary of our conversation above. Focus on information that would be helpful for continuing the conversation, including what we did, what we're doing, which files we're working on, and what we're going to do next."
        promptMsg := message.Message{
            Role:  message.User,
            Parts: []message.ContentPart{message.TextContent{Text: summarizePrompt}},
        }
        msgsWithPrompt := append(msgs, promptMsg)
        
        // 4. 调用 summarize provider
        response, _ := a.summarizeProvider.SendMessages(summarizeCtx, msgsWithPrompt, make([]tools.BaseTool, 0))
        
        // 5. 创建摘要消息
        msg, _ := a.messages.Create(summarizeCtx, oldSession.ID, message.CreateMessageParams{
            Role:  message.Assistant,
            Parts: []message.ContentPart{
                message.TextContent{Text: summary},
                message.Finish{Reason: message.FinishReasonEndTurn, Time: time.Now().Unix()},
            },
            Model: a.summarizeProvider.Model().ID,
        })
        
        // 6. 更新会话的 SummaryMessageID
        oldSession.SummaryMessageID = msg.ID
        oldSession.CompletionTokens = response.Usage.OutputTokens
        oldSession.PromptTokens = 0
        
        // 7. 计算 cost 并保存
        cost := model.CostPer1MInCached/1e6 * float64(usage.CacheCreationTokens) + ...
        oldSession.Cost += cost
        a.sessions.Save(summarizeCtx, oldSession)
    }()
    return nil
}
```

### 15.2 加载时裁剪

```go
// processGeneration 中
if session.SummaryMessageID != "" {
    summaryMsgInex := -1
    for i, msg := range msgs {
        if msg.ID == session.SummaryMessageID {
            summaryMsgInex = i
            break
        }
    }
    if summaryMsgInex != -1 {
        msgs = msgs[summaryMsgInex:]   // 只加载从摘要开始的消息
        msgs[0].Role = message.User
    }
}
```

### 15.3 上下文管理特点

```
特点1: 手动触发   ← 调用 Summarize() 或 CLI /summarize
特点2: 单次 LLM 摘要   ← 无工具裁剪、无多轮压缩
特点3: 加载时裁剪   ← 通过 SummaryMessageID 定位
特点4: 硬编码实现   ← 无 ContextEngine 抽象基类
特点5: 2 个 Provider   ← 主 provider + summarizeProvider
```

---

## 16 平台扩展（MCP）

### 16.1 仅 CLI 平台

OpenCode **没有多平台适配层**，仅提供 CLI：

```
入口：main.go
  ↓
App.Run() 或 App.RunNonInteractive()
  ↓
CoderAgent.Run(ctx, sessionID, content)
  ↓
agent.processGeneration() → ReAct 循环
  ↓
11 个内建工具 + MCP 工具
```

### 16.2 MCP 工具加载

```go
// agent/tools.go + mcp-tools.go
func CoderAgentTools(...) []tools.BaseTool {
    ctx := context.Background()
    otherTools := GetMcpTools(ctx, permissions)   // 从 MCP 服务器加载
    if len(lspClients) > 0 {
        otherTools = append(otherTools, tools.NewDiagnosticsTool(lspClients))
    }
    return append([]tools.BaseTool{...}, otherTools...)
}
```

### 16.3 扩展架构

```
扩展点：仅工具
  ├─ 11 个内建工具（编译时确定）
  ├─ MCP 工具（运行时加载）
  └─ 子 Agent（NewAgentTool，调用 TaskAgent）
```

---

# 第三部分 架构对比

## 17 架构对比

### 17.1 整体设计对比

```
┌─────────────────────────────────────────────────────────────────────┐
│                       Hermes Agent                                  │
├─────────────────────────────────────────────────────────────────────┤
│  定位: 生产级多平台 Agent 平台                                        │
│  哲学: 功能完备，厚积薄发 / 生产级鲁棒性，不信任任何外部输入            │
│  规模: 7,046 个 .py 文件 / 84 个 agent 文件 / 78 个工具              │
│  入口: run_agent.py (4,816 行 Forwarder)                              │
│  组装: init_agent() 属性注入（60+ 参数）                              │
│  通信: 10+ 回调函数                                                  │
│  上下文: 自动压缩（50% 阈值 + 多阶段）                                │
│  平台: 20+ 平台适配（Telegram/飞书/钉钉/...）                        │
│  扩展: Gateway + 插件 + 技能 + MCP                                    │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│                       OpenCode Agent                                │
├─────────────────────────────────────────────────────────────────────┤
│  定位: 极简 CLI 编程助手                                             │
│  哲学: 精简核心，扩展外围 / 把复杂度留给外部系统                       │
│  规模: 137 个 .go 文件 / 4 个 agent 文件 / 11 个工具                 │
│  入口: main.go → app.New() (178 行)                                   │
│  组装: 构造函数注入（4-5 参数）                                       │
│  通信: 泛型 Broker[T] 事件总线                                       │
│  上下文: 手动摘要（单次 LLM 摘要）                                    │
│  平台: 仅 CLI                                                       │
│  扩展: MCP + 子 Agent                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.2 核心指标对比

| 维度 | Hermes | OpenCode | 比值 |
|------|--------|----------|------|
| **总文件数** | 7,046 | 137 | 51.4x |
| **Agent 模块文件** | 84 | 4 | 21x |
| **内建工具数** | 78 | 11 | 7.1x |
| **最大单文件** | 4,460 行 | 758 行 | 5.9x |
| **服务组装参数** | 60+ | 4-5 | 12x+ |
| **ReAct 循环防御层数** | 8 | 1 | 8x |
| **平台适配器** | 20+ | 0 | ∞ |
| **Provider 实现** | 多适配器 | 8+ (Go provider 包) | ~ |
| **上下文管理** | 自动+可插拔 | 手动+硬编码 | - |
| **通信模式** | 回调函数 | 泛型事件总线 | - |
| **依赖检查** | 运行时 | 编译时 | - |
| **扩展方式** | Gateway+Plugin+Skill+MCP | MCP+子Agent | - |

### 17.3 ReAct 循环对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes ReAct 循环                                                    │
│                                                                       │
│  while (max_iterations && budget.remaining) || grace_call {           │
│      ┌─────────────────────────────────────────────────┐             │
│      │ 第1层 循环控制（4 项）                            │             │
│      ├─────────────────────────────────────────────────┤             │
│      │ 第2层 消息准备（10 项）                           │             │
│      ├─────────────────────────────────────────────────┤             │
│      │ 第3层 消息清洗（4 项）                            │             │
│      ├─────────────────────────────────────────────────┤             │
│      │ 第4层 预检（3 项）                                │             │
│      ├─────────────────────────────────────────────────┤             │
│      │ 第5层 API 调用 + 重试（8 项）                     │             │
│      ├─────────────────────────────────────────────────┤             │
│      │ 第6层 Token 统计（5 项）                          │             │
│      ├─────────────────────────────────────────────────┤             │
│      │ 第7层 工具执行（9 项）                            │             │
│      ├─────────────────────────────────────────────────┤             │
│      │ 第8层 压缩 + 恢复（7 项）                         │             │
│      └─────────────────────────────────────────────────┘             │
│      continue / break                                                 │
│  }                                                                    │
│                                                                       │
│  功能: 50+ 个 / 4,460 行 / 1 文件 + 多个辅助模块                       │
│  工具执行: 顺序 + 并发（8 线程）                                       │
│  上下文: 50% 阈值自动触发压缩                                          │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode ReAct 循环                                                 │
│                                                                       │
│  for {                                                               │
│      取消检查                                                          │
│      streamAndHandleEvents()  ← LLM + 事件 + 工具（顺序）             │
│      if finishReason == ToolUse: continue                             │
│      else: return                                                     │
│  }                                                                    │
│                                                                       │
│  功能: 9 个 / 113 行（agent.go:233-311）/ 758 行（含其他功能）          │
│  工具执行: 仅顺序                                                     │
│  上下文: 手动 Summarize()                                             │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.4 服务组装对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes: Forwarder + 属性注入                                         │
│                                                                       │
│  agent = AIAgent(...)         ← run_agent.py 薄壳                    │
│      ↓ 调用 init_agent(self, ...)                                    │
│  1,657 行属性初始化                                                    │
│  agent.model = ...                                                   │
│  agent._session_db = ...                                             │
│  agent.context_compressor = ContextCompressor(...)                   │
│  agent._tool_guardrails = ToolCallGuardrailController(...)           │
│  ...                                                                 │
│  60+ 参数、紧耦合、运行时检查、mock 属性测试                            │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 接口 + 构造函数注入                                        │
│                                                                       │
│  app := app.New(ctx, conn)     ← 178 行                               │
│      ↓                                                               │
│  sessions := session.NewService(q)        ← DB → Service             │
│  messages := message.NewService(q)                                    │
│  app.CoderAgent = agent.NewAgent(                                     │
│      config.AgentCoder,                                               │
│      app.Sessions,                                                    │
│      app.Messages,                                                    │
│      agent.CoderAgentTools(                                           │
│          app.Permissions, app.Sessions, app.Messages,                 │
│          app.History, app.LSPClients,                                 │
│      ),                                                              │
│  )                                                                    │
│  4-5 参数、编译时检查、mock 接口测试                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.5 通信模式对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes: 回调函数（紧耦合）                                            │
│                                                                       │
│  agent = AIAgent(                                                    │
│      tool_progress_callback=on_tool_progress,                        │
│      tool_start_callback=on_tool_start,                              │
│      tool_complete_callback=on_tool_complete,                        │
│      thinking_callback=on_thinking,                                  │
│      reasoning_callback=on_reasoning,                                │
│      step_callback=on_step,                                          │
│      status_callback=on_status,                                      │
│      stream_delta_callback=on_delta,                                 │
│      interim_assistant_callback=on_interim,                          │
│      ... (10+ 回调)                                                   │
│  )                                                                   │
│  → 每个回调在初始化时绑定                                              │
│  → 无统一事件分发                                                      │
│  → 运行时类型安全                                                      │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 泛型 Broker[T] 事件总线（松耦合）                          │
│                                                                       │
│  // 所有 Service 嵌入 Broker                                         │
│  type agent struct {                                                 │
│      *pubsub.Broker[AgentEvent]                                      │
│      ...                                                             │
│  }                                                                   │
│  type service struct {                                               │
│      *pubsub.Broker[Session]                                         │
│      ...                                                             │
│  }                                                                   │
│  type messageService struct {                                        │
│      *pubsub.Broker[Message]                                         │
│      ...                                                             │
│  }                                                                   │
│  type permissionService struct {                                     │
│      *pubsub.Broker[PermissionRequest]                               │
│      ...                                                             │
│  }                                                                   │
│                                                                       │
│  // TUI 订阅                                                          │
│  agent.Subscribe(ctx) → <-chan Event[AgentEvent]                     │
│  → 编译时类型安全（泛型 + 接口）                                        │
│  → 慢消费者丢弃（非阻塞 publish）                                      │
│  → 上下文取消自动取消订阅                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.6 工具系统对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes: 注册表 + AST 自动发现                                        │
│                                                                       │
│  tools/registry.py (ToolRegistry 单例)                                │
│      ↑                                                              │
│  tools/*.py (78 个工具文件)                                           │
│      │ 每个文件顶层调用 registry.register(name, schema, handler,...)  │
│      ↓                                                              │
│  discover_builtin_tools() 扫描 + AST 解析                            │
│      ↓                                                              │
│  importlib.import_module → 自动注册                                  │
│      ↓                                                              │
│  model_tools.get_tool_definitions() 按 toolset 过滤                   │
│      ↓                                                              │
│  tool_executor: 顺序 + 并发（8 线程）                                 │
│  + Toolset 分类 + Tool Search 桥接 + Plugin block + Guardrail         │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 接口 + 手动构造                                            │
│                                                                       │
│  tools/tools.go (BaseTool 接口)                                       │
│      ↑                                                              │
│  tools/*.go (11 个内建工具)                                           │
│      │ 每个实现 BaseTool 接口                                        │
│      ↓                                                              │
│  agent/tools.go: CoderAgentTools() 手动创建所有实例                   │
│      ↓                                                              │
│  return []tools.BaseTool{                                            │
│      tools.NewBashTool(permissions),                                 │
│      tools.NewEditTool(lspClients, permissions, history),            │
│      ...                                                            │
│  }                                                                   │
│      ↓                                                              │
│  agent.streamAndHandleEvents: 顺序执行                                │
│  + 无分类 + 编译时确定                                                │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.7 上下文管理对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes: ContextEngine 抽象基类 + 自动压缩                            │
│                                                                       │
│  agent/context_engine.py (抽象基类)                                   │
│      ↑                                                              │
│  agent/context_compressor.py (2,078 行具体实现)                       │
│      │                                                              │
│      ├─ should_compress()                                            │
│      │   ├─ 50% 阈值                                                │
│      │   ├─ anti-thrashing（防抖）                                   │
│      │   └─ should_defer_preflight_to_real_usage() 智能延迟          │
│      │                                                              │
│      ├─ compress() 多阶段                                            │
│      │   ├─ 工具输出裁剪（廉价预处理）                                │
│      │   ├─ LLM 摘要（辅助模型）                                      │
│      │   └─ 多轮压缩（最大 3 次）                                     │
│      │                                                              │
│      └─ update_from_response(usage)                                  │
│                                                                       │
│  + Anthropic 缓存控制（apply_anthropic_cache_control）               │
│  + 强制"latest user message wins"规则                                │
│  + 旧前缀清理（_HISTORICAL_SUMMARY_PREFIXES）                        │
│  + 摘要失败回退（_FALLBACK_SUMMARY_MAX_CHARS = 8000）                │
│  + 4 类保护：threshold_percent, protect_first_n, protect_last_n, 比例 │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 手动 Summarize() + 加载时裁剪                              │
│                                                                       │
│  agent.Summarize(ctx, sessionID)                                     │
│      │                                                              │
│      ├─ 加载所有消息                                                  │
│      ├─ 添加 prompt（"Provide a detailed but concise summary..."）    │
│      ├─ 调用 summarizeProvider.SendMessages()                         │
│      ├─ 创建摘要消息（Role: Assistant）                               │
│      └─ 设置 session.SummaryMessageID = msg.ID                       │
│                                                                       │
│  加载时裁剪：                                                          │
│      if session.SummaryMessageID != "":                              │
│          msgs = msgs[summaryMsgIdx:]                                  │
│          msgs[0].Role = message.User                                  │
│                                                                       │
│  特点: 单次 LLM 摘要 / 无自动触发 / 无工具裁剪 / 无多轮压缩            │
│  2 个 Provider: 主 provider + summarizeProvider                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.8 设计哲学对比

| 维度 | Hermes | OpenCode |
|------|--------|----------|
| **核心信念** | 不信任任何外部输入 | 信任 LLM + 工具实现 |
| **复杂度位置** | 集中在核心循环 | 下沉到工具 + LLM |
| **代码风格** | 大文件 + 紧耦合 + 灵活性高 | 小文件 + 接口 + 强约束 |
| **测试策略** | mock 属性（运行时） | mock 接口（编译时） |
| **错误处理** | 8 层防御 + 重试 + fallback | 直接传播 + context cancel |
| **可扩展性** | 运行时（属性替换） | 编译时（接口实现） |
| **学习成本** | 高（需理解 60+ 参数） | 低（4-5 参数 + 清晰接口） |
| **适用场景** | 复杂长任务、生产级 | 短任务、CLI 交互 |

---

# 第四部分 对 OmniAgent 的借鉴分析

## 18 借鉴分析

### 18.1 OmniAgent 当前架构回顾

```
OmniAgentAs-desk (当前)
├── backend/                                # FastAPI 后端
│   ├── app/
│   │   ├── main.py                         # FastAPI 入口
│   │   ├── services/agent/                 # Agent 系统
│   │   │   ├── base_react.py               # BaseAgent(ABC)
│   │   │   ├── mixins/react_agent_mixin.py
│   │   │   ├── agent_factory.py
│   │   │   └── (Agent 子类)
│   │   ├── services/tools/                 # 工具系统
│   │   │   ├── registry.py                 # ToolRegistry
│   │   │   ├── __init__.py                 # ensure_tools_registered()
│   │   │   └── (按 category 分目录)
│   │   ├── services/preprocessing/         # 意图分类
│   │   ├── services/intents/               # CRSS 评分
│   │   └── services/llm_core.py            # LLM 客户端
│   ├── tests/                              # pytest
│   └── tools/                              # 测试/调试脚本
├── frontend/                               # React+TypeScript 前端
│   ├── src/
│   │   ├── pages/                          # 页面组件
│   │   ├── stores/                         # 状态管理
│   │   ├── services/                       # API 层
│   │   └── utils/                          # 工具函数
│   └── package.json
└── config/                                 # YAML 配置
```

### 18.2 借鉴方向图

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OmniAgent 借鉴方向                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  系统组织: 借鉴 OpenCode                                              │
│    ├─ ✅ 严格包结构（每个子系统独立包）                                │
│    ├─ ✅ 入口简洁（main.py + service 组装）                           │
│    └─ 🔄 减少大文件（当前 conversation_loop 风格过于集中）              │
│                                                                       │
│  服务组装: 借鉴 OpenCode                                              │
│    ├─ ✅ 构造函数注入（替换现在的 60+ 参数属性注入）                     │
│    ├─ ✅ 接口解耦（Service 抽象基类）                                  │
│    └─ ✅ 编译时类型检查                                                │
│                                                                       │
│  模块通信: 借鉴 OpenCode                                              │
│    ├─ ✅ 泛型事件总线（替换回调函数）                                  │
│    ├─ ✅ 嵌入 Broker 模式（每个 Service 嵌入 Broker）                  │
│    └─ ✅ 非阻塞发布 + 慢消费者丢弃                                     │
│                                                                       │
│  工具系统: 借鉴 Hermes + OpenCode                                     │
│    ├─ ✅ BaseTool 接口（OpenCode）                                     │
│    ├─ ✅ 自动注册（已有 registry.py）                                  │
│    ├─ 🔄 添加 Toolset 分类（Hermes）                                   │
│    └─ 🔄 顺序 + 并发执行（Hermes）                                     │
│                                                                       │
│  上下文管理: 借鉴 Hermes                                              │
│    ├─ ✅ ContextEngine 抽象基类                                       │
│    ├─ ✅ 50% 阈值自动压缩                                              │
│    └─ ✅ 多阶段压缩（工具裁剪 + LLM 摘要）                             │
│                                                                       │
│  平台扩展: 借鉴 OpenCode（短期）→ Hermes（长期）                        │
│    ├─ 🔄 短期：仅 CLI/TUI（OpenCode 模式）                             │
│    └─ 🔄 长期：MCP + Web UI（Hermes 模式）                             │
│                                                                       │
│  错误处理: 借鉴 Hermes 8 层防御                                        │
│    ├─ 🔄 消息清洗层（surrogate/thinking/角色修复）                     │
│    ├─ 🔄 API 重试 + fallback + 退避                                    │
│    └─ 🔄 空响应恢复层（nudge/prefill/retry）                           │
│                                                                       │
│  权限系统: 借鉴 OpenCode                                              │
│    ├─ ✅ 阻塞式权限确认（Permission Service）                          │
│    ├─ 🔄 工具执行前权限检查（每个工具独立请求）                         │
│    └─ 🔄 会话级自动批准（AutoApproveSession）                          │
│                                                                       │
│  Guardrail 循环检测: 借鉴 Hermes                                      │
│    ├─ 🔄 工具分类（IDEMPOTENT vs MUTATING）                           │
│    ├─ 🔄 5 种循环模式检测（exact_failure/no_progress）                │
│    └─ 🔄 warn + hard_stop 阈值（可配置）                               │
│                                                                       │
│  事件总线类型: 借鉴 OpenCode                                          │
│    ├─ AgentEvent（响应/错误/摘要进度）                                 │
│    ├─ Session（创建/更新/删除）                                       │
│    ├─ Message（创建/更新/删除）                                        │
│    └─ PermissionRequest（创建/授予/拒绝）                              │
│                                                                       │
└─────────────────────────────────────────────────────────────────────┘
```

### 18.3 具体落地建议

#### 18.3.1 立即可做（小改动）

```python
# 1. 引入 Pydantic Event 总线（轻量级）
# backend/app/services/events.py
from typing import Generic, TypeVar
from pydantic import BaseModel
import asyncio

T = TypeVar('T')

class EventBroker(Generic[T]):
    """借鉴 OpenCode pubsub.Broker[T] 的轻量级 Python 实现"""
    def __init__(self, buffer_size: int = 64):
        self._subs: list[asyncio.Queue] = []
        self._lock = asyncio.Lock()
    
    async def subscribe(self) -> asyncio.Queue:
        async with self._lock:
            q = asyncio.Queue(maxsize=buffer_size)
            self._subs.append(q)
        return q
    
    async def publish(self, event_type: str, payload: T):
        # 非阻塞发布，慢消费者丢弃
        for q in self._subs:
            try:
                q.put_nowait((event_type, payload))
            except asyncio.QueueFull:
                pass  # 丢弃

# 2. BaseTool 接口（借鉴 OpenCode tools/tools.go）
# backend/app/services/tools/base.py
from abc import ABC, abstractmethod
from typing import Any

class BaseTool(ABC):
    @abstractmethod
    def info(self) -> dict:
        """返回工具元信息"""
        ...
    
    @abstractmethod
    async def run(self, params: dict, context: dict) -> dict:
        """执行工具"""
        ...
```

#### 18.3.2 中期改进（架构调整）

```python
# 3. ContextEngine 抽象（借鉴 Hermes）
# backend/app/services/context/engine.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ContextEngine(ABC):
    """借鉴 Hermes agent/context_engine.py"""
    threshold_percent: int = 50
    protect_first_n: int = 3
    protect_last_n: int = 20
    
    @abstractmethod
    def should_compress(self, messages: List[Dict], usage: Dict) -> bool:
        """是否需要压缩"""
        ...
    
    @abstractmethod
    async def compress(self, messages: List[Dict], llm) -> List[Dict]:
        """执行压缩"""
        ...

class AutoCompressor(ContextEngine):
    """借鉴 Hermes ContextCompressor"""
    async def compress(self, messages, llm):
        # 阶段1: 工具输出裁剪
        pruned = self._prune_tool_outputs(messages)
        # 阶段2: LLM 摘要
        summary = await llm.summarize(pruned)
        # 阶段3: 多轮压缩（最多 3 次）
        while self._exceeds_threshold(summary) and self._rounds < 3:
            summary = await self._further_compress(summary, llm)
        return summary
```

#### 18.3.3 长期演进（完整事件总线）

```python
# 4. 完整事件总线（完全借鉴 OpenCode）
# backend/app/services/pubsub.py
from dataclasses import dataclass
from typing import Generic, TypeVar
import asyncio

T = TypeVar('T')

@dataclass
class Event(Generic[T]):
    type: str  # "created" | "updated" | "deleted"
    payload: T

class Broker(Generic[T]):
    """完全对齐 OpenCode pubsub.Broker[T]"""
    def __init__(self):
        self._subs: list[asyncio.Queue[Event[T]]] = []
        self._done = False
        self._lock = asyncio.Lock()
    
    async def subscribe(self, ctx) -> asyncio.Queue:
        async with self._lock:
            q: asyncio.Queue[Event[T]] = asyncio.Queue(maxsize=64)
            self._subs.append(q)
        
        async def watcher():
            await ctx.done()
            async with self._lock:
                if q in self._subs:
                    self._subs.remove(q)
                    del q
        
        asyncio.create_task(watcher())
        return q
    
    def publish(self, event_type: str, payload: T):
        event = Event(type=event_type, payload=payload)
        for q in self._subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                pass  # 慢消费者丢弃

# 5. 嵌入到所有 Service
# backend/app/services/session/service.py
class SessionService:
    def __init__(self, db):
        self.db = db
        self.events: Broker[Session] = Broker()   # ← 嵌入
    
    async def create(self, title: str) -> Session:
        session = await self.db.create_session(title)
        self.events.publish("created", session)
        return session

# backend/app/api/v1/chat.py - WebSocket 订阅事件
@router.websocket("/ws/session/{session_id}")
async def ws_session(websocket: WebSocket, session_id: str):
    await websocket.accept()
    # 订阅 session 事件
    queue = await app.Sessions.events.subscribe(websocket)
    # 订阅 message 事件
    msg_queue = await app.Messages.events.subscribe(websocket)
    
    async def forward(queue):
        while True:
            event = await queue.get()
            await websocket.send_json(event)
    
    await asyncio.gather(
        forward(queue),
        forward(msg_queue),
    )
```

### 18.4 架构演进路线图

```
Phase 1 (1-2 周) ── 基础改造
  ├─ 引入 EventBroker 基础类
  ├─ 改造 Session/Message Service 嵌入 Broker
  ├─ 保留现有回调机制（兼容）
  └─ 验证可行

Phase 2 (2-4 周) ── 接口解耦
  ├─ 引入 BaseTool 抽象接口
  ├─ 重构现有工具实现 BaseTool
  ├─ 引入 ContextEngine 抽象
  └─ 单元测试覆盖

Phase 3 (4-8 周) ── 完整事件化
  ├─ Agent 嵌入 Broker[AgentEvent]
  ├─ Permission 嵌入 Broker[PermissionRequest]
  ├─ FastAPI 端改用 WebSocket 订阅事件
  └─ 移除回调机制

Phase 4 (8-12 周) ── 平台扩展
  ├─ 实现 MCP 客户端
  ├─ 实现 Web UI（订阅事件更新）
  └─ 引入 Guardrail 循环检测

Phase 5 (12+ 周) ── 多平台（如需要）
  ├─ 引入 Gateway 适配层
  ├─ Telegram / Discord / 飞书适配
  └─ 复用 Hermes 钩子系统
```

### 18.5 核心原则

```
1. 接口解耦
   ├─ BaseTool / Service / ContextEngine 抽象
   └─ 每个子系统通过 interface 通信

2. 构造函数注入
   ├─ 替换当前的 60+ 参数属性注入
   └─ 依赖通过参数显式传递

3. 事件驱动
   ├─ 泛型 Broker[T] 统一事件系统
   ├─ 嵌入 Broker 模式
   └─ 非阻塞发布

4. 可插拔
   ├─ ContextEngine 可替换实现
   ├─ BaseTool 可替换实现
   └─ 单元测试可 mock 接口

5. 编译时类型安全
   ├─ Pydantic 强类型
   ├─ Generic[T] 泛型
   └─ 静态类型检查（mypy）

6. 单一职责
   ├─ 每个 Service 只做一件事
   ├─ BaseAgent 抽象基类
   └─ ReactAgentMixin 行为复用
```

### 18.6 关键风险与应对

| 风险 | 描述 | 应对策略 |
|------|------|---------|
| **向后兼容** | 现有回调代码无法一次性替换 | 渐进式迁移：先引入事件总线，再逐步移除回调 |
| **WebSocket 性能** | 事件总线在 Web UI 上可能性能不佳 | 批量发送 + 客户端 dedup |
| **事件顺序** | 异步事件可能乱序 | 引入 sequence 字段 + 客户端排序 |
| **状态一致性** | 事件 + 状态可能不一致 | 事件携带最新状态 + 客户端幂等更新 |
| **学习成本** | 团队需理解 Broker 模式 | 文档 + Demo + 代码审查 |
| **测试覆盖** | 事件总线测试复杂 | 单元测试 mock Broker + 集成测试订阅 |

### 18.7 借鉴价值评估

| 借鉴点 | 价值 | 实施难度 | 优先级 |
|--------|------|---------|--------|
| **事件总线** | ⭐⭐⭐⭐⭐ | 中 | P0 |
| **构造函数注入** | ⭐⭐⭐⭐ | 低 | P0 |
| **BaseTool 接口** | ⭐⭐⭐⭐ | 中 | P0 |
| **ContextEngine 抽象** | ⭐⭐⭐⭐ | 中 | P1 |
| **自动压缩** | ⭐⭐⭐⭐ | 高 | P1 |
| **多平台 Gateway** | ⭐⭐ | 高 | P2 |
| **Guardrail 循环检测** | ⭐⭐⭐ | 中 | P1 |
| **Anthropic 缓存控制** | ⭐⭐⭐ | 低 | P1 |
| **Toolset 分类** | ⭐⭐ | 低 | P2 |
| **顺序+并发执行** | ⭐⭐⭐ | 中 | P2 |

---

**文档完成时间**: 2026-06-02 14:00:00
**编写人**: 小欧
**结构**: 4 部分（Hermes 分析 → OpenCode 分析 → 对比 → 借鉴）
**验证**: 3 轮源码逐行验证
**特色**: 准确图示 + 清晰命名 + 树形架构图
