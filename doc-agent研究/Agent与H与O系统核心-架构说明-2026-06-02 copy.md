# Hermes Agent 与 OpenCode Agent 架构性对比研究

**创建时间**: 2026-06-02 12:18:53
**编写人**: 小欧
**版本**: v4.2（3遍复查精简版）
**研究对象**: Hermes Agent (Nous Research) / OpenCode Agent (sst/opencode)
---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v4.0 | 2026-06-02 14:00:00 | 小欧 | 4部分结构重构：Hermes分析→OpenCode分析→对比→借鉴 |
| v4.1 | 2026-06-02 14:58:27 | 小欧 | 流程图纯文字化:移除3.1/4.1/11/12/13/14/15/16中函数体代码,改为文字描述,关键签名/常量保留 |
| v4.2 | 2026-06-02 15:37:04 | 小欧 | 3遍复查精简:5.2去估数、5.3去代码细节、6.1回调分类树、7.1/7.2压缩精简、8.1/8.3文件枚举精简、11.1/11.3构造函数逻辑化、12.3/12.4事件流化、15.1/15.2摘要步骤化、16.2/17.4/17.5/17.6/17.7去代码 |

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

Hermes 采用 **Forwarder 模式 + 属性注入** 风格组装服务。

**Forwarder 模式**：对外暴露的 `AIAgent` 类是一个薄壳，仅做参数转发，所有真正的逻辑都在 `agent/` 子包的内部模块中。

**属性注入风格**：`init_agent()` 不通过构造函数传参，而是把 60+ 个参数逐个赋值给 `agent` 实例的属性。下游模块通过 `agent.xxx` 访问这些属性。

```
[用户代码入口]
   │
   │ 调用 AIAgent(base_url=..., model=...)
   ↓
[AIAgent 类 - run_agent.py 的薄壳]
   │  职责：接收用户参数,转发给 init_agent
   │  __init__ 内部调用 init_agent(self, ...)
   ↓
[init_agent() - agent/agent_init.py 的服务组装器]
   │  职责：把 60+ 参数转换为 70+ 实例属性
   │  1,657 行属性赋值,涵盖 LLM 客户端、压缩器、内存、
   │  守卫、工具、会话数据库、回调、平台上下文、checkpoint 等
   ↓
[agent 实例 - 配置完毕]
   │
   │ 用户调用 agent.run_conversation(user_msg)
   ↓
[run_conversation() - agent/conversation_loop.py 的主循环]
   │  职责：执行 ReAct 循环
   │  通过属性访问下游模块:
   │  - agent.context_compressor  上下文压缩器
   │  - agent._tool_guardrails    工具守卫
   │  - agent._memory_manager     内存管理器
   │  - agent._session_db         会话数据库
   │  - agent.tools               工具列表
   ↓
[输出结果]
```

### 3.2 init_agent 60+ 参数分类清单

`init_agent()` 把全部配置按 8 大类别接收,逐类赋值为 `agent` 实例属性:

**[1] LLM 连接配置(8 项)**
- 用途:配置与 LLM API 的连接
- 字段:`base_url`、`api_key`、`provider`、`api_mode`、`model`、`service_tier`、`max_tokens`、`reasoning_config`

**[2] 路由与降级配置(8 项)**
- 用途:多 provider 路由、备选模型、降级策略
- 字段:`providers_allowed`、`providers_ignored`、`providers_order`、`provider_sort`、`provider_require_parameters`、`openrouter_min_coding_score`、`fallback_model`、`credential_pool`

**[3] 循环控制(5 项)**
- 用途:控制 ReAct 主循环的执行上限
- 字段:`max_iterations`(默认 90)、`iteration_budget`、`tool_delay`、`checkpoints_enabled`、`checkpoint_max_snapshots`(默认 20)、`checkpoint_max_total_size_mb`(默认 500)

**[4] 工具集配置(3 项)**
- 用途:启用/禁用工具集
- 字段:`enabled_toolsets`、`disabled_toolsets`、`tool_delay`

**[5] 内存与上下文(5 项)**
- 用途:加载用户记忆、跳过文件、加载身份
- 字段:`skip_context_files`、`load_soul_identity`、`skip_memory`、`prefill_messages`、`session_db`

**[6] 平台会话上下文(13 项)**
- 用途:对接 Telegram/飞书/微信等平台时的会话身份
- 字段:`platform`、`user_id`、`user_id_alt`、`user_name`、`chat_id`、`chat_name`、`chat_type`、`thread_id`、`gateway_session_key`、`session_id`、`parent_session_id`、`request_overrides`

**[7] 回调函数(11 项)**
- 用途:运行时通知外部(进度、思考、流式、状态)
- 字段:`tool_progress_callback`、`tool_start_callback`、`tool_complete_callback`、`thinking_callback`、`reasoning_callback`、`clarify_callback`、`step_callback`、`stream_delta_callback`、`interim_assistant_callback`、`tool_gen_callback`、`status_callback`

**[8] 日志与杂项(6 项)**
- 用途:调试输出、轨迹保存
- 字段:`save_trajectories`、`verbose_logging`、`quiet_mode`、`log_prefix_chars`(默认 100)、`log_prefix`、`ephemeral_system_prompt`

> **总计约 60+ 参数,全部通过 `agent.xxx = xxx` 形式赋值为实例属性**

### 3.3 组装特点

```
特点 1: 属性注入(替代构造函数注入)
   ├─ init_agent 不通过 __init__ 接收依赖
   ├─ 而是把 60+ 参数赋值为 agent.xxx 属性
   └─ 下游模块通过 agent.xxx 访问

特点 2: 懒引用 _ra() — 保持测试 mock 兼容
   ├─ 函数 _ra() 返回 run_agent 模块引用
   ├─ 全局模块通过 _ra() 获取 run_agent
   └─ 目的:让 mock.patch("run_agent.X") 在测试中生效

特点 3: Forwarder 入口
   ├─ AIAgent.__init__ 仅调用 init_agent()
   └─ run_conversation 仅转发到 conversation_loop.run_conversation()

特点 4: 60+ 参数控制所有行为
   ├─ init_agent 是唯一的配置入口
   └─ 调用者通过长参数列表控制 agent 的所有行为

特点 5: 配置/逻辑分离
   ├─ run_agent.py 只做参数接收
   └─ agent_init.py 负责属性组装,真正的逻辑在 agent/ 各子模块
```

---

## 4 ReAct 核心循环

### 4.1 循环入口与控制

**核心函数**:`run_conversation` 位于 `agent/conversation_loop.py`,是 Hermes ReAct 循环的主入口。

**主 while 循环的逻辑判定**——三层 OR 条件:

```
[while 循环判定逻辑]
│
├─ 条件 A:迭代次数硬上限(api_call_count < max_iterations,默认 90)
│   作用:绝对防止无限循环
│
├─ 条件 B:动态 token 预算(iteration_budget.remaining > 0)
│   作用:按 token 消耗实时计算,可低于硬上限提前停止
│
└─ 条件 C:Grace call 标志(_budget_grace_call)
    作用:预算耗尽时允许多执行一次以完成收尾(避免半截响应)
```

**循环每次迭代的固定开头逻辑**——4 步:

```
[循环开始逻辑]
│
├─ 逻辑 1:开启新检查点
│   └─ 为本轮迭代建立状态快照,失败时可回滚
│
├─ 逻辑 2:检测用户中断信号
│   └─ 若用户通过网关发出中断请求,跳出循环
│
├─ 逻辑 3:递增迭代计数 + 消耗预算
│   └─ api_call_count += 1,iteration_budget.consume()
│
└─ 逻辑 4:触发网关 step 钩子
    └─ 通知外部网关当前迭代进度
```

**循环控制要素**:

| 要素 | 逻辑机制 |
|------|---------|
| 双重循环条件 | 硬上限(max_iterations)+ 动态预算(iteration_budget) |
| Grace call 机制 | 预算耗尽时允许多一次收尾 |
| 中断检测 | 网关可设置中断标志让循环优雅退出 |
| 预算消耗 | 每次迭代扣除 token 预算 |
| Checkpoint 重置 | 每轮开始建立新检查点 |
| 网关钩子 | 每轮迭代开头通知外部 |

### 4.2 8 层防御架构

`run_conversation()` 的主 while 循环内部不是单一直线逻辑,而是按 8 个防御层级组织。每层处理一类失败场景,从循环控制到压缩恢复,层层兜底。

```
[Hermes ReAct 循环 8 层防御架构]
│
├─ 第 1 层 循环控制
│   职责:管理主循环是否继续迭代,防止无限循环和资源耗尽
│   手段:迭代次数硬上限(max_iterations)+ token 动态预算(IterationBudget)
│       + 用户中断信号 + 检查点快照
│
├─ 第 2 层 消息准备
│   职责:把当前会话状态、用户中途指令(/steer)、预取记忆、插件上下文
│       整合为发往 LLM 的完整消息列表
│   关键设计:支持 Anthropic prompt cache(节省 25% 成本)
│
├─ 第 3 层 消息清洗
│   职责:剔除导致 LLM API 报错的非法字符和格式
│   处理对象:surrogate 字符、非 ASCII、thinking-only 消息、JSON 格式
│
├─ 第 4 层 预检
│   职责:在真正调用 LLM 前估算 token 数,提前拦截超限请求
│   关键:针对 Ollama 等本地 provider 做上下文超限检测
│
├─ 第 5 层 API 调用 + 重试
│   职责:实际调用 LLM 并处理各种失败(限流、网络、中断)
│   关键设计:支持用户中断的流式/非流式调用 + fallback provider 切换
│       + jittered exponential backoff
│
├─ 第 6 层 Token 统计
│   职责:记录每次 LLM 调用的 token 消耗,估算 USD 成本
│   持久化:写入会话数据库(session_db)供后续查询和成本归因
│
├─ 第 7 层 工具执行
│   职责:处理 LLM 返回的工具调用,执行前/中/后多层校验
│   防御措施:工具名幻觉修复、白名单校验、JSON 格式校验、插件拦截、
│       guardrail 循环检测、并发限流(8 线程)
│
└─ 第 8 层 上下文压缩 + 恢复
    职责:处理上下文超限和空响应,保证长会话可用
    手段:50% 阈值自动压缩 + 多阶段(工具裁剪+LLM 摘要) +
        部分流恢复 + 空响应 nudge/prefill/fallback
```

### 4.3 工具执行器(`agent/tool_executor.py`)

**核心职责**:承接主循环第 7 层,把 LLM 返回的工具调用列表真正执行出去,收集结果回传 LLM。

**两种执行模式**——根据工具特性自动选择:

```
[execute_tool_calls_sequential — 顺序执行]
│  适用:有依赖关系的工具调用(后一个依赖前一个的结果)
│  逻辑流程:解析参数 → 桥接工具解包 → 插件拦截检查
│           → 守卫拦截检查 → 检查点快照 → 进度/开始回调
│           → 顺序执行工具 handler
↓
[execute_tool_calls_concurrent — 并发执行]
│  适用:互相独立、无依赖的工具调用
│  逻辑流程:解析参数 → 桥接工具解包 → 插件/守卫检查
│           → 检查点快照 → ThreadPoolExecutor(8 线程)并发执行
│           → 主线程等待全部完成 → 按原始顺序收集结果
↓
[结果回传主循环]
```

**核心常量**(`tool_executor.py` 模块顶部):

```python
_MAX_TOOL_WORKERS = 8
```

- 含义:`ThreadPoolExecutor` 的 `max_workers` 参数值
- 作用:限制单次 LLM 响应触发的并发工具数,防止打爆 CPU/内存/文件句柄

### 4.4 工具注册表(`tools/registry.py`)

**逻辑机制**:AST 自动发现,无需手动 import 工具模块。

```
[工具注册逻辑流程]
│
├─ 1. discover_builtin_tools
│     └─ 扫描 tools/*.py(排除 __init__.py、registry.py、mcp_tool.py)
│
├─ 2. AST 解析每个文件
│     └─ 检测顶层 registry.register 调用
│
├─ 3. importlib.import_module 触发模块加载
│     └─ 模块顶层代码执行,自动调用 registry.register
│
├─ 4. 工具元信息进入 ToolRegistry 单例
│     └─ 名称、JSON Schema、handler、check_fn、toolset 等
│
└─ 5. model_tools.get_tool_definitions
      └─ 按 toolset 过滤后,返回给 LLM 作为可用工具列表
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

按 10 大类组织,涵盖终端、文件、网络、浏览器、Agent 编排、记忆/技能、MCP、平台、多媒体、辅助。

| 分类 | 代表工具 |
|------|---------|
| **文件** | read_file, write_file, patch, glob, grep |
| **终端** | terminal(pty), execute_code |
| **网络** | web_search, web_extract, fetch_url |
| **浏览器** | browser_navigate, browser_click, browser_snapshot |
| **Agent 编排** | delegate_task, send_message, mixture_of_agents |
| **记忆/技能** | memory, skill_manage, todo |
| **MCP** | mcp_filesystem_*, mcp_github_*, ... |
| **平台** | feishu_doc, wecom_send, telegram_send |
| **多媒体** | image_generation, video_generation, tts, vision |
| **辅助** | clarify, checkpoint, osv_check, tirith_security |

### 5.3 工具执行全流程

```
触发工具执行（来自 ReAct 循环）
   ↓
解析工具参数(LLM 返回的 JSON 字符串)
   ↓
选择执行模式:concurrent(并发) 或 sequential(顺序)
   ↓
Tool Search 桥接(若此工具是 bridge)
   ↓
plugin 拦截检查(返回 block 消息)
   ↓
guardrail 拦截检查(返回 block 消息)
   ↓
checkpoint 快照(失败可回滚)
   ↓
调用工具 handler 执行
   ↓
封装为工具结果消息
   ↓
消息清洗(处理代理对/多模态/超长输出)
   ↓
返回 messages 给 ReAct 循环
```

---

## 6 通信与回调

### 6.1 回调驱动(无事件总线)

Hermes **没有统一事件总线**,所有外部通信通过**回调函数**——按 4 类分组:

```
[init_agent 接收的 10 个核心回调]
│
├─ 工具生命周期
│  ├─ tool_progress   工具进度(可选)
│  ├─ tool_start      工具开始
│  └─ tool_complete   工具完成
│
├─ 推理/思考
│  ├─ thinking        thinking 增量
│  └─ reasoning       reasoning 增量
│
├─ 流式
│  ├─ stream_delta    流式增量
│  └─ interim_assistant  中间输出
│
├─ 流程/状态
│  ├─ step            step 钩子(对应 agent:step 网关事件)
│  └─ status          状态更新
│
└─ 其他
   ├─ clarify         用户澄清
   └─ tool_gen        工具生成
```

### 6.2 通信链路图

```
[ReAct 循环内部触发点]
│
├─ 读取自身状态:agent.model / agent.tools / agent._session_db
│
├─ 组件调用(方法调用,无中间件)
│  ├─ context_compressor.update_from_response
│  ├─ _tool_guardrails.before_call
│  └─ _memory_manager.prefetch_all
│
└─ 外部回调(注入的回调函数)
   ├─ status_callback(状态广播)
   ├─ step_callback(对应 agent:step 网关钩子)
   ├─ tool_progress_callback(工具进度)
   └─ stream_delta_callback(流式输出)
```

### 6.3 Gateway 钩子系统

`gateway/hooks.py` 提供**9 个生命周期钩子**:

```
[9 个 Gateway 钩子]
├─ agent:start            会话开始
├─ agent:step             每步迭代
├─ agent:tool_call        工具调用
├─ agent:tool_result      工具返回
├─ agent:pre_api_request  API 请求前
├─ agent:post_api_request API 请求后
├─ agent:transform_input  输入转换
├─ agent:transform_output 输出转换
└─ session:end            会话结束
```

**20+ 平台**通过 Gateway 共享这些钩子,平台适配器只需实现 3 个方法:`send_message` / `receive_message` / `handle_update`。

---

## 7 上下文管理

### 7.1 自动压缩引擎

Hermes 拥有**生产级的自动压缩系统**,核心是 `ContextEngine` 抽象基类——定义压缩触发条件和压缩动作:

```
[ContextEngine 抽象基类]
├─ 3 个可配置字段
│  ├─ threshold_percent  触发压缩的百分比阈值
│  ├─ protect_first_n    保护前 N 条消息
│  └─ protect_last_n     保护后 N 条消息
│
└─ 2 个抽象方法
   ├─ should_compress    判断是否需要压缩
   └─ compress           执行压缩并返回新消息列表
```

### 7.2 ContextCompressor 实现逻辑

```
[ContextCompressor 多阶段压缩]
│
├─ should_compress 决策
│  ├─ 50% 阈值检查
│  ├─ anti-thrashing 防抖(避免反复压缩)
│  └─ 智能延迟(等真实使用数据再决定)
│
└─ compress 多阶段压缩
   ├─ 第 1 阶段:工具输出裁剪(廉价,节省 30-50% token)
   ├─ 第 2 阶段:LLM 摘要(用辅助模型)
   ├─ 第 3 阶段:多轮压缩(最多 3 次,每次缩小 20%)
   └─ 第 4 阶段:结构化摘要前缀
      ├─ Resolved/Pending question 跟踪
      ├─ Active Task / In Progress / Remaining Work 结构
      ├─ 强制"latest user message wins"规则
      └─ 旧前缀清理
```

### 7.3 关键压缩常量

```
[ContextCompressor 关键参数]
├─ _MIN_SUMMARY_TOKENS = 2000          摘要最小 token
├─ _SUMMARY_RATIO = 0.20               摘要占压缩内容 20%
├─ _SUMMARY_TOKENS_CEILING = 12_000    摘要上限 12k tokens
└─ _SUMMARY_FAILURE_COOLDOWN_SECONDS = 600  失败冷却 10 分钟
```

### 7.4 Anthropic 缓存控制

`apply_anthropic_cache_control` 在系统提示词和最后若干消息上设置 `cache_control` 标记,启用 Anthropic 提示词缓存(节省 25% 成本)。

---

## 8 平台扩展

### 8.1 Gateway 适配层

```
[Gateway 核心模块逻辑]
│
├─ platforms/    20 个平台适配器(telegram/weixin/whatsapp/bluebubbles/qqbot 等)
│                └─ 每个平台只需实现 send_message/receive_message/handle_update
│
├─ platform_registry.py  平台注册表(动态加载)
├─ session.py / session_context.py   Gateway 会话
├─ hooks.py              9 个生命周期钩子(详见 6.3)
├─ delivery.py           消息投递(含分块/格式转换)
├─ run.py                Gateway 启动入口
├─ config.py             配置加载
├─ pairing.py            用户配对
├─ restart.py            重启管理
└─ builtin_hooks/        内置钩子实现
```

### 8.2 平台分层

```
[Hermes 平台分层架构]
│
├─ 应用层:CLI / TUI / Web UI / API Server
│
├─ 平台层:Gateway + Hooks(20+ 平台适配)
│
├─ 核心层:AIAgent(conversation_loop.py)
│
└─ 工具层:tools/*.py(78 个工具)
```

### 8.3 扩展机制三件套

```
[Hermes 三大扩展机制]
│
├─ plugin 插件系统
│  ├─ 钩子:pre_api_request / post_api_request / pre_tool_call_block
│  └─ 用途:第三方能力扩展
│
├─ skills 技能系统
│  ├─ 形式:自描述 markdown 文件
│  ├─ 流程:discover → load → invoke
│  └─ 安全:AST 审计
│
└─ MCP 协议集成
   ├─ 形式:标准化工具扩展协议
   └─ 示例:mcp_filesystem_* / mcp_github_* / ...
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
│   │   │   └── openrouter.go
│   │   ├── tools/              # 11 个内建工具 + 1 个接口
│   │   │   ├── tools.go        # BaseTool 接口 + ToolCall/ToolResponse
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

### 11.1 构造函数注入(强类型)

OpenCode 采用**接口 + 构造函数注入**风格组装服务,与 Hermes 的属性注入形成对比。

**`App` 结构体**(`app/app.go`)——整个应用的根容器,持有 6 大核心组件:

```
[App 结构体]
├─ 4 大基础 Service(接口类型)
│  ├─ Sessions    session.Service       会话管理
│  ├─ Messages    message.Service       消息管理
│  ├─ History     history.Service       文件历史
│  └─ Permissions permission.Service    权限管理
│
├─ 1 个 Agent Service
│  └─ CoderAgent  agent.Service         编码代理
│
└─ LSP 客户端集合
   └─ LSPClients  各语言的 LSP 连接(map 结构,加锁保护)
```

**`New` 构造函数**(`app/app.go`)——按 4 阶段组装,178 行:

```
[New 入口逻辑]
│
├─ 第 1 阶段: 构造 DB 查询器
│   └─ 把 *sql.DB 包装为 db.Querier 接口
│
├─ 第 2 阶段: 构造 4 大基础 Service
│   └─ session / message / history / permission 各 NewService(q)
│
├─ 第 3 阶段: 装配 App 实例
│   ├─ 把 4 个 Service 赋给 App 字段
│   ├─ 初始化 LSPClients 为空 map
│   ├─ 同步加载主题
│   └─ 异步初始化 LSP 客户端(后台,不阻塞)
│
└─ 第 4 阶段: 构造 Agent(注入 5 个依赖)
    └─ agent.NewAgent 接收 AgentType + 3 Service + CoderAgentTools
        └─ CoderAgentTools 再注入 5 个依赖
```

### 11.2 服务接口定义

OpenCode 的所有 Service 都是**接口类型**,由具体 struct 实现,客户端代码只依赖接口。

**4 个 Service 接口**——全部嵌入 `pubsub.Suscriber[T]`,自动获得订阅能力:

```
[4 大 Service 接口的逻辑职责]
│
├─ session.Service (session/session.go)
│   职责:管理会话生命周期
│   关键操作:CRUD + 子会话创建(标题/任务)
│
├─ message.Service (message/message.go)
│   职责:管理会话内消息(用户/助手/工具/系统)
│   关键操作:CRUD + 按会话批量删除
│
├─ agent.Service (llm/agent/agent.go)
│   职责:运行 ReAct 循环,产生 AgentEvent 流
│   关键操作:Run 启动 / Cancel 取消 / 忙检查 / 摘要触发
│
└─ permission.Service (permission/permission.go)
    职责:工具执行前的权限询问与授权管理
    关键操作:Grant / Deny / Request / 会话级自动批准
```

### 11.3 组装特点

```
特点 1: 构造函数注入(强类型)
   └─ 所有依赖通过函数参数显式传入,无任何全局状态

特点 2: 分层组装
   ├─ 底层: *sql.DB 连接
   ├─ 第 1 层: db.Querier 包装器
   ├─ 第 2 层: 4 大基础 Service(每个 NewService(q))
   ├─ 第 3 层: App 实例(把 Service 装配进字段)
   └─ 第 4 层: Agent Service(把 App.Service 注入 + 工具集)

特点 3: 编译时类型检查
   ├─ 所有 Service 都是接口
   ├─ NewService/NewAgent 接收接口类型
   └─ 传入类型不匹配 = 编译失败,不会到运行时才暴露问题

特点 4: 参数数量受控
   ├─ agent.NewAgent 只接收 4 个参数
   ├─ CoderAgentTools 接收 5 个依赖
   └─ 对比 Hermes init_agent 的 60+ 参数,大幅减少

特点 5: 接口嵌入组合
   └─ 每个 Service 接口嵌入 pubsub.Suscriber[T],自动获得订阅能力
```

---

## 12 ReAct 核心循环

### 12.1 循环总览

**核心结构**:`Run()` 是对外入口,`processGeneration()` 是循环主体。OpenCode 把 ReAct 循环拆成 2 个职责清晰的函数。

**核心函数签名**(`llm/agent/agent.go`):

```go
func (a *agent) Run(
    ctx context.Context,
    sessionID string,
    content string,
    attachments ...message.Attachment,
) (<-chan AgentEvent, error)

func (a *agent) processGeneration(
    ctx context.Context,
    sessionID string,
    content string,
    attachmentParts []message.ContentPart,
) AgentEvent
```

**`Run()` 入口**——负责启动异步 goroutine,把 LLM 流式事件通过 channel 返回给调用方:

```
[Run 入口逻辑]
│
├─ 逻辑 1: 附件兼容性检查
│   └─ 若当前 model 不支持附件,attachments 置空
│
├─ 逻辑 2: 会话忙检查
│   └─ 若会话已在运行,直接返回 ErrSessionBusy
│
├─ 逻辑 3: 建立可取消的子 context
│   └─ cancel 函数存入 activeRequests map,供后续 Cancel 调用
│
└─ 逻辑 4: 启动 goroutine
    └─ defer RecoverPanic 兜底
    └─ 调用 processGeneration
    └─ 清理 activeRequests / 取消 context
    └─ 通过事件总线发布结果 + 推入 events channel + 关闭 channel
```

**`processGeneration` 循环主体**——ReAct 核心逻辑:

```
[processGeneration 入口逻辑]
│
├─ [循环前准备阶段]
│   │
│   ├─ 1. 加载历史消息
│   │
│   ├─ 2. 异步标题生成(首次会话触发,后台不阻塞)
│   │
│   ├─ 3. 加载会话元数据(SummaryMessageID 等)
│   │
│   ├─ 4. 摘要裁剪(若存在摘要:丢弃之前的消息,把摘要标记为用户角色)
│   │
│   ├─ 5. 创建用户消息(content + attachments 写入数据库)
│   │
│   └─ 6. 构造完整历史 = 历史消息 + 用户消息
│
└─ [ReAct for 循环]
    │
    ├─ 逻辑 A: 取消检测(ctx.Done 时返回)
    │
    ├─ 逻辑 B: 调用 LLM + 处理事件(streamAndHandleEvents)
    │
    ├─ 逻辑 C: 错误处理
    │   ├─ 取消错误:标记 Canceled + 返回 ErrRequestCancelled
    │   └─ 其他错误:直接返回
    │
    ├─ 逻辑 D: 调试日志(可选,生产环境关闭)
    │
    ├─ 逻辑 E: 结束原因分支
    │   ├─ FinishReason == ToolUse 且 toolResults 非空:continue 进入下一轮
    │   └─ 否则:return AgentEvent{Type: Response, Done: true}
    │
    └─ 回到 for 循环顶部
```

### 12.2 循环内 9 个功能点

OpenCode 的 ReAct 循环虽然短(113 行),但功能点齐全:

```
[OpenCode ReAct 循环 9 个逻辑功能点]
│
├─ 1. 会话忙检查
│   逻辑:防止同一会话并发运行,避免状态污染
│
├─ 2. 上下文 + 取消机制
│   逻辑:支持用户随时中断正在运行的 Agent
│
├─ 3. 历史消息加载 + 摘要裁剪
│   逻辑:从数据库加载历史 + 若有摘要则丢弃之前的消息
│
├─ 4. 标题生成(异步,首次会话触发)
│   逻辑:后台生成会话标题,不阻塞主流程
│
├─ 5. 用户消息创建
│   逻辑:把 content + attachments 持久化,加入历史
│
├─ 6. LLM 流式调用 + 事件处理
│   逻辑:启动流式响应 → 累积 Assistant 消息 → 顺序执行工具
│
├─ 7. Token 统计 + 成本计算
│   逻辑:按 4 类 token 计算 USD 成本,累加并持久化到会话
│
├─ 8. 结束原因分支
│   逻辑:ToolUse → 继续下一轮,其他 → 完成响应
│
└─ 9. 调试日志(可选)
    逻辑:仅在 cfg.Debug=true 时,把 toolResults 写到 JSON 文件
```

### 12.3 processEvent 6 个事件类型

**核心函数**(`agent.go`):`processEvent` 把 provider 推来的事件分发到 assistant 消息对象,**每次分发后都 Update 写回数据库**——保证中途断开时已累积内容不丢。

**事件类型 → 动作** 6 种映射:

```
[processEvent 事件分发逻辑]
│
├─ EventThinkingDelta  思考片段 → 累积 reasoning → Update
├─ EventContentDelta   文本片段 → 累积 content → Update
├─ EventToolUseStart   工具调用开始 → AddToolCall → Update
├─ EventToolUseStop    工具调用结束 → FinishToolCall → Update
├─ EventError          LLM 错误 → 直接返回 event.Error
└─ EventComplete       LLM 完成 → SetToolCalls/AddFinish → Update → TrackUsage
```

### 12.4 TrackUsage 成本计算

**核心函数**(`agent.go`):`TrackUsage` 在 EventComplete 时被调用,把本次 LLM 调用的成本累加到会话。

**4 类 token 分别计费**(单价来自 model.CostPer1MInCached/OutCached/In/Out):

```
[TrackUsage 计算公式]
│
├─ cost = (CacheCreationTokens × InCached
│         + CacheReadTokens     × OutCached
│         + InputTokens         × In
│         + OutputTokens        × Out) / 1_000_000
│
├─ 累加到会话:sess.Cost += cost
│
├─ 统计 token 分类
│  ├─ CompletionTokens = OutputTokens + CacheReadTokens
│  └─ PromptTokens     = InputTokens + CacheCreationTokens
│
└─ 持久化:Save 写回数据库
```

---

## 13 工具系统

### 13.1 BaseTool 接口

**`BaseTool` 接口**(`llm/tools/tools.go`)——所有工具的逻辑抽象:

```
[BaseTool 接口逻辑]
├─ Info 返回工具元信息(名称、描述、参数 schema、必填字段)
└─ Run 执行工具逻辑,返回 ToolResponse
```

**4 个核心类型**——围绕工具调用的输入/输出:

```
[4 个核心类型的逻辑职责]
├─ ToolInfo    工具元信息(给 LLM 看)
├─ ToolCall    工具调用请求(LLM 返回)
├─ ToolResponse 工具执行结果(回传 LLM)
└─ ctx 键     SessionIDContextKey / MessageIDContextKey
   └─ 工具通过 ctx 拿到当前 session/message,无需 Run 参数显式传
```

### 13.2 11 个内建工具

**`CoderAgentTools` 构造逻辑**(`llm/agent/tools.go`):

```
[CoderAgentTools 构造逻辑]
│
├─ 1. 加载 MCP 工具(外部 MCP server 提供的工具)
│
├─ 2. 条件加载 LSP Diagnostics(仅 lspClients 非空时)
│
└─ 3. 合并 11 内建 + MCP + Diagnostics
    └─ 返回给 Agent 作为可用工具列表
```

**11 个内建工具**(`llm/tools/` 目录下,按功能分类):

```
[OpenCode 11 个内建工具(按功能分类)]
│
├─ 文件读取类(只读,不修改文件)
│  ├─ View       读取文件内容,支持 LSP 语义高亮
│  ├─ Glob       glob 模式匹配文件路径
│  ├─ Grep       正则搜索文件内容
│  ├─ Ls         列出目录
│  └─ Sourcegraph  通过 Sourcegraph API 搜索公开代码
│
├─ 文件修改类(写入,需权限)
│  ├─ Edit       局部编辑文件
│  ├─ Write      整体写入文件
│  └─ Patch      应用补丁
│
├─ 执行类(外部副作用,需权限)
│  ├─ Bash       执行 shell 命令
│  └─ Fetch      HTTP 请求获取内容
│
└─ 子 Agent 委派
   └─ Agent      创建子 Agent 处理子任务
```

**2 个可选工具**:
- **MCP 工具**——通过 `GetMcpTools` 加载,数量不固定,来自配置的 MCP server
- **Diagnostics**——仅当 `lspClients` 非空时添加,提供 LSP 诊断信息

### 13.3 工具执行流程

**核心函数**:`streamAndHandleEvents`(`agent.go`)——把 LLM 流式事件 + 工具执行合并到一个流程里。

**3 阶段执行**:

```
[streamAndHandleEvents 入口]
│
├─ 第 1 阶段:启动 LLM 流 + 准备 assistant 消息
│   ├─ 把 sessionID 塞入 ctx(供工具读取)
│   ├─ 启动 LLM 流式调用,返回 eventChan
│   ├─ 预创建空 Assistant 消息(用于累积)
│   └─ 把 messageID 也塞入 ctx
│
├─ 第 2 阶段:消费 LLM 流式事件
│   └─ for event := range eventChan:
│       ├─ processEvent 分发到 Assistant 消息对象
│       └─ 若 ctx 已取消:标记 Canceled + 返回
│
└─ 第 3 阶段:顺序执行工具
    │
    ├─ 3a: 取出所有工具调用
    │
    ├─ 3b: 准备 toolResults 数组
    │
    ├─ 3c: for 顺序遍历每个 toolCall
    │   ├─ 检查取消:若 ctx.Done 则把剩余工具填为 canceled + 跳出
    │   ├─ 查找工具实现:遍历 a.tools 按 Name 匹配,找不到则报错
    │   ├─ 调用工具:tool.Run 实际执行
    │   ├─ 权限拒绝处理:标记当前 + 取消后续所有工具 + finishMessage
    │   └─ 正常情况:填入 Content/Metadata/IsError
    │
    └─ 3d: 创建 Tool 消息(把全部 toolResults 打包)
        └─ return assistantMsg, &msg, nil
```

**关键设计**:
- **顺序执行**——不像 Hermes 那样支持并发,工具调用按 LLM 返回顺序逐个执行
- **取消粒度**——已开始的工具无法中断,但后续工具直接跳过并标记为 canceled
- **权限拒绝终止**——一个工具权限被拒,后面所有工具全部取消
- **助手消息累积**——前 5 种事件每次都 Update 消息,确保流式状态可恢复

### 13.4 4 个 Agent 类型

**Agent 类型常量**(`config/config.go`):

```
[4 个 Agent 类型的逻辑职责]
├─ AgentCoder      主编码 Agent(执行用户的编码任务)
├─ AgentSummarizer 摘要 Agent(手动触发上下文压缩)
├─ AgentTask       子任务 Agent(由 Agent 工具委派子任务)
└─ AgentTitle      标题生成 Agent(首次会话异步生成标题)
```

**每个 Agent 可独立配置**:model(选哪个 LLM)+ provider(选哪个 API)+ prompt(系统提示词),通过 `cfg.Agents[AgentName]` 在 YAML 中配置。

---

## 14 事件总线通信

### 14.1 泛型 Broker[T]

**核心位置**:`pubsub/broker.go`,由 OpenCode 自研,作为模块间通信的统一机制。

**核心常量**:`bufferSize = 64`(每个订阅者的 channel 容量)

**`Broker[T any]` 泛型结构**——Go 1.18+ 泛型,`T` 是事件 payload 的类型:

```
[Broker[T] 结构]
├─ subs      map[chan Event[T]]struct{}   订阅者集合
├─ mu        sync.RWMutex                 读写锁
├─ done      chan struct{}                关闭信号
├─ subCount  int                          订阅者计数
└─ maxEvents int                          最大事件数(1000)
```

**`Subscribe` 订阅逻辑**:

```
[Subscribe 逻辑流程]
│
├─ 1. 创建带缓冲的 channel(容量 64)
│
├─ 2. 注册到订阅者集合
│
├─ 3. 启动 goroutine 监听 ctx 取消
│   └─ ctx 取消时自动从订阅者集合移除 + 关闭 channel
│
└─ 4. 返回 sub channel 给订阅者
```

**`Publish` 发布逻辑**——关键设计是**非阻塞发布**:

```
[Publish 逻辑流程]
│
├─ 1. 加读锁 + 检查关闭信号
│   └─ 若已关闭:解锁并直接返回
│
├─ 2. 复制订阅者列表(关键:发布时不持锁)
│   └─ 复制后立即解读锁,允许发布期间订阅者增删
│
├─ 3. 构造事件 Event{Type, Payload}
│
└─ 4. 对每个订阅者非阻塞发送
    └─ select { case sub <- event: / default: 丢弃 }
       └─ 慢消费者被丢弃,发布者永不阻塞
```

**3 个关键设计**:
- **非阻塞**——发布者永不等待慢消费者
- **读锁 + 复制**——发布期间订阅者增删不影响
- **ctx 自动取消**——订阅者 goroutine 退出时自动清理

### 14.2 所有 Service 嵌入 Broker

**核心模式**:每个 Service 结构体都嵌入 `*pubsub.Broker[T]`,自动获得发布/订阅能力。

```
[4 大 Service 嵌入 Broker 的逻辑]
│
├─ agent.Service       嵌入 Broker[AgentEvent]        Agent 事件总线
├─ session.Service     嵌入 Broker[Session]           会话事件总线
├─ message.Service     嵌入 Broker[Message]           消息事件总线
└─ permission.Service  嵌入 Broker[PermissionRequest]  权限事件总线
```

**嵌入带来的逻辑好处**:
- 4 个 Service 各自有专属事件类型(类型安全)
- 调用方写 `service.Publish(eventType, payload)` 即可,无需额外字段
- 嵌入的 `Subscribe` 方法继承到 Service 上,客户端用同一接口

### 14.3 事件类型

**通用事件类型**(`pubsub/events.go`):

```
[通用 EventType 3 个值]
├─ CreatedEvent  EventType = "created"    新建事件
├─ UpdatedEvent  EventType = "updated"    更新事件
└─ DeletedEvent  EventType = "deleted"    删除事件
```

**泛型 Event 结构**:

```
[Event[T any] 结构]
├─ Type    EventType   事件类型(枚举)
└─ Payload T           事件携带的数据
```

**AgentEventType 专属事件**(`agent.AgentEventType`):

```
[AgentEventType 3 个值]
├─ AgentEventTypeError     = "error"       Agent 错误
├─ AgentEventTypeResponse  = "response"    Agent 响应(完成)
└─ AgentEventTypeSummarize = "summarize"   摘要进度
```

### 14.4 通信特点

```
特点 1: 泛型 Broker[T any]   Go 1.18+ 泛型,4 个 Service 复用同一实现
特点 2: 每个 Service 嵌入 Broker   统一模式,Publish/Subscribe 零成本继承
特点 3: 非阻塞发布   慢消费者直接丢弃,发布者永远不阻塞
特点 4: 上下文取消自动取消订阅   goroutine 监听 ctx.Done(),无需手动 Unsubscribe
特点 5: 编译时类型安全   pubsub.Suscriber[AgentEvent] 接口约束事件类型
```

---

## 15 上下文管理(手动摘要)

### 15.1 摘要流程

OpenCode **没有自动压缩**,提供手动 `Summarize()` 方法,由用户主动触发(CLI `/summarize` 命令或 API 调用)。

**核心函数**:`Summarize(ctx, sessionID) error`(`agent.go`)——**异步执行**,入口有 2 个守卫:

```
[Summarize 入口守卫]
├─ 检查 1: summarizeProvider 是否配置
└─ 检查 2: 会话是否忙
```

**7 步主流程**(goroutine 内部):

```
[Summarize 主流程]
│
├─ 1. 加载所有消息(空则发错误事件 + return)
│
├─ 2. 发进度事件(Progress: "Starting...")
│
├─ 3. 追加固定英文摘要 prompt 到消息末尾
│
├─ 4. 调用 summarizeProvider.SendMessages(不传工具)
│
├─ 5. 创建摘要消息:Role=Assistant,Parts=[summary, Finish]
│
├─ 6. 更新会话元数据
│   ├─ SummaryMessageID = msg.ID
│   ├─ CompletionTokens = response.Usage.OutputTokens
│   └─ PromptTokens = 0
│
└─ 7. 计算 cost 并 Save 写回数据库
```

**注意点**:
- 摘要使用**单独的 provider**(`summarizeProvider`),可与主对话用不同模型
- 摘要调用**不传工具**,纯粹 LLM 文本生成
- 摘要消息**不调用 LLM**,只是把 LLM 返回的文本作为 Assistant 角色存库

### 15.2 加载时裁剪

**裁剪逻辑**——在 `processGeneration` 加载历史消息时执行,**每次加载自动裁剪**,无需单独触发:

```
[加载时裁剪]
│
├─ 1. 加载会话元数据,session.SummaryMessageID 为空则不裁剪
│
├─ 2. 在 msgs 中按 ID 查找摘要消息的索引
│
├─ 3. 裁剪:msgs = msgs[summaryIdx:]  切片丢弃更早的消息
│   └─ 数据库中原始消息**完整保留**,只是不再发给 LLM
│
└─ 4. 角色修正:msgs[0].Role = User
    └─ 摘要原本是 Assistant,改为 User 让 LLM 视为用户提供的信息
```

### 15.3 上下文管理特点

```
特点 1: 手动触发     用户调 Summarize() 或 CLI /summarize,无自动阈值检测
特点 2: 单次 LLM 摘要  一次 LLM 调用,无工具裁剪阶段,无多轮压缩循环
特点 3: 加载时裁剪    通过 SummaryMessageID 定位,切片丢弃旧消息
特点 4: 硬编码实现    无 ContextEngine 抽象基类,逻辑直接写在 agent.go
特点 5: 2 个 Provider 主 provider + summarizeProvider(可独立配置)
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

OpenCode 通过 MCP(Model Context Protocol)协议在运行时从外部 MCP server 加载工具——这是与 Hermes 静态扫描工具文件完全不同的方式。

**MCP 加载流程**——由 `GetMcpTools` 完成,详见 13.2 节:

```
[GetMcpTools 加载流程]
│
├─ 1. 读取配置中的 MCP server 列表(YAML/JSON)
│
├─ 2. 与每个 server 建立连接(stdio/HTTP 客户端,握手)
│
├─ 3. 调用 listTools 协议获取工具清单(name/description/parameters)
│
└─ 4. 把 MCP 工具包装为 BaseTool 接口实现,直接被 agent 调用
```

**与 11 内建工具的关系**:
- MCP 工具与 11 内建工具**并列**,都实现 `BaseTool` 接口
- Agent 把它们**视为同等地位**的工具,不区分来源
- 用户在 YAML 中配置要连接哪些 MCP server

### 16.3 扩展架构

OpenCode 的扩展点**非常少**,只有 3 个:

```
[OpenCode 扩展点]
├─ 11 个内建工具
│   └─ 编译时确定,需要修改 Go 源码才能增加
├─ MCP 工具
│   └─ 运行时加载,配置 YAML 即可增加
└─ 子 Agent(NewAgentTool 调用 TaskAgent)
    └─ 运行时创建子任务会话
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
│  Hermes: Forwarder + 属性注入(运行时)                                  │
│                                                                       │
│  agent = AIAgent(...)         ← run_agent.py 薄壳                    │
│      ↓ 调用 init_agent                                               │
│  1,657 行属性初始化                                                    │
│  agent.model / agent._session_db / agent.context_compressor / ...    │
│                                                                       │
│  60+ 参数、紧耦合、运行时检查、mock 属性测试                            │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 接口 + 构造函数注入(编译时)                                 │
│                                                                       │
│  app := app.New(ctx, conn)     ← 178 行                               │
│      ↓                                                               │
│  4 大基础 Service:session / message / history / permission            │
│      ↓                                                               │
│  app.CoderAgent = agent.NewAgent(AgentType, 3 Services, Tools)       │
│      ↓                                                               │
│  CoderAgentTools 再注入 5 个依赖                                     │
│                                                                       │
│  4-5 参数、编译时检查、mock 接口测试                                   │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.5 通信模式对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes: 回调函数(紧耦合)                                              │
│                                                                       │
│  agent = AIAgent(                                                    │
│      tool_progress_callback / tool_start / tool_complete,            │
│      thinking / reasoning,                                            │
│      stream_delta / interim_assistant,                                │
│      step / status,                                                  │
│      ...  共 10+ 回调                                                  │
│  )                                                                   │
│                                                                       │
│  → 回调在初始化时绑定                                                  │
│  → 无统一事件分发                                                      │
│  → 运行时类型安全(鸭子类型)                                            │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 泛型 Broker[T] 事件总线(松耦合)                            │
│                                                                       │
│  4 大 Service 各自嵌入专属 Broker                                      │
│    ├─ agent.Service        Broker[AgentEvent]                         │
│    ├─ session.Service      Broker[Session]                            │
│    ├─ message.Service      Broker[Message]                            │
│    └─ permission.Service   Broker[PermissionRequest]                  │
│                                                                       │
│  调用方:service.Publish / service.Subscribe(ctx)                     │
│                                                                       │
│  → 编译时类型安全(泛型 + 接口)                                         │
│  → 慢消费者丢弃(非阻塞 publish)                                        │
│  → 上下文取消自动取消订阅                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.6 工具系统对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes: 注册表 + AST 自动发现(运行时)                                  │
│                                                                       │
│  tools/registry.py (单例)                                             │
│      ↑                                                              │
│  tools/*.py (78 个工具文件)                                           │
│      │ 文件顶层调用 registry.register                                 │
│      ↓                                                              │
│  discover_builtin_tools() 扫描 + AST 解析                            │
│      ↓                                                              │
│  importlib 动态加载 → 自动注册                                         │
│      ↓                                                              │
│  model_tools.get_tool_definitions() 按 toolset 过滤                   │
│                                                                       │
│  执行:顺序 + 并发(8 线程) + Plugin block + Guardrail                │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 接口 + 手动构造(编译时)                                     │
│                                                                       │
│  tools/tools.go (BaseTool 接口)                                       │
│      ↑                                                              │
│  tools/*.go (11 个内建工具)                                           │
│      │ 每个实现 BaseTool 接口                                         │
│      ↓                                                              │
│  agent/tools.go: CoderAgentTools() 手动创建所有实例                   │
│      ↓                                                              │
│  返回 []BaseTool(可追加 MCP + Diagnostics)                           │
│                                                                       │
│  执行:仅顺序 + 编译时确定                                              │
└─────────────────────────────────────────────────────────────────────┘
```

### 17.7 上下文管理对比

```
┌─────────────────────────────────────────────────────────────────────┐
│  Hermes: ContextEngine 抽象 + 自动压缩(可插拔)                        │
│                                                                       │
│  context_engine.py (抽象基类)                                         │
│      ↑ 继承                                                         │
│  context_compressor.py (具体实现)                                     │
│      ├─ should_compress:50% 阈值 + 防抖 + 智能延迟                    │
│      ├─ compress 多阶段:工具裁剪 → LLM 摘要 → 多轮压缩(≤3 次)         │
│      └─ update_from_response:从 API 更新 token 计数                   │
│                                                                       │
│  额外能力:                                                             │
│  + Anthropic 缓存控制(节省 25% 成本)                                  │
│  + latest user message wins 规则                                      │
│  + 旧前缀清理                                                         │
│  + 摘要失败回退                                                       │
│  + 4 类保护:threshold / protect_first_n / protect_last_n / 比例       │
├─────────────────────────────────────────────────────────────────────┤
│                          VS                                          │
├─────────────────────────────────────────────────────────────────────┤
│  OpenCode: 手动 Summarize() + 加载时裁剪(硬编码)                       │
│                                                                       │
│  Summarize 流程                                                       │
│    ├─ 加载所有消息                                                    │
│    ├─ 追加固定英文 prompt                                              │
│    ├─ 调用 summarizeProvider(不传工具)                                │
│    ├─ 创建摘要消息(Role: Assistant)                                   │
│    └─ 设置 session.SummaryMessageID                                   │
│                                                                       │
│  加载时裁剪:按 SummaryMessageID 切片 + 角色改 User                    │
│                                                                       │
│  特点:单次 LLM 摘要 / 无自动触发 / 无工具裁剪 / 无多轮压缩            │
│  2 个 Provider:主 provider + summarizeProvider(可独立配置)             │
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
