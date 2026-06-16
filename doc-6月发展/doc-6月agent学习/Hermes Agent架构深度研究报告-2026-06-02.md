# Hermes Agent 架构深度研究报告

> 研究时间：2026-06-02
> 研究对象：hermes-agent (Nous Research)
> 代码库路径：/mnt/f/agenttool/hermes

---

## 目录

1. [整体拓扑：多前端 × 单核心 × 多平台](#一整体拓扑多前端--单核心--多平台)
2. [文件依赖链：自下而上的注册模式](#二文件依赖链自下而上的注册模式)
3. [核心执行循环：同步 + 异步桥接](#三核心执行循环同步--异步桥接)
4. [工具系统：三层抽象](#四工具系统三层抽象)
5. [插件系统：三条独立发现路径](#五插件系统三条独立发现路径)
6. [Gateway：多平台消息架构](#六gateway多平台消息架构)
7. [Profile 多租户隔离](#七profile-多租户隔离)
8. [委派（Delegation）系统](#八委派delegation系统)
9. [Cron 定时调度器](#九cron-定时调度器)
10. [状态存储与记忆系统](#十状态存储与记忆系统)
11. [TypeScript TUI 前端](#十一typescript-tui-前端)
12. [Kanban 多智能体协作](#十二kanban-多智能体协作)
13. [技能（Skills）系统](#十三技能skills系统)
14. [核心代码量统计](#十四核心代码量统计)
15. [设计哲学总结](#十五设计哲学总结)
16. [对 OmniAgent 的参考价值](#十六对-omniagent-的参考价值)

---

## 一、整体拓扑：多前端 × 单核心 × 多平台

```
          CLI (prompt_toolkit)         TUI (Ink/React + JSON-RPC)
                │                              │
                ▼                              ▼
         ┌──────────────┐            ┌─────────────────┐
         │  HermesCLI   │            │  tui_gateway    │
         │  (cli.py)    │            │  (Python后端)    │
         └──────┬───────┘            └────────┬────────┘
                │                              │
                ▼                              ▼
         ┌──────────────────────────────────────────┐
         │              AIAgent 核心                  │
         │   (run_agent.py + agent/conversation_loop)  │
         └──────────┬──────────────┬────────────────┘
                    │              │
          ┌────────▼─────┐  ┌──────▼──────────┐
          │  Gateway     │  │  ACP Adapter     │
          │  (多平台消息)  │  │  (VS Code/Zed/   │
          │              │  │  JetBrains 集成)  │
          └──────────────┘  └─────────────────┘
```

**核心洞察：AIAgent 是唯一的核心执行引擎。** CLI、TUI、Gateway（Telegram/Discord/Slack 等 20+ 平台）、ACP（IDE 集成）都是它的*前端适配器*，不是独立实现的对话系统。这意味着只要写一个新的 adapter（适配器），就能让 agent 出现在任何地方。

---

## 二、文件依赖链：自下而上的注册模式

这是 Hermes 最优雅的架构设计之一 —— 不是手工维护一个中央工具列表，而是用 **自注册 + AST 自动发现**：

```
tools/registry.py          ← 无依赖，定义 ToolEntry + register() 函数
      ↑
tools/*.py                 ← 每个工具文件 import registry，在模块顶层调用 registry.register()
      ↑
model_tools.py             ← 导入 tools.registry，触发 discover_builtin_tools()
      ↑                       (用 AST 解析源码，检测顶层 registry.register() 调用)
run_agent.py, cli.py,
batch_runner.py            ← 消费层：调用 get_tool_definitions() / handle_function_call()
```

### 为什么用 AST 而不是装饰器？

```python
# 传统装饰器方式（Hermes 没用）：
@registry.register(name="web_search", toolset="web")
def web_search(query: str) -> str:
    ...

# Hermes 的方式（AST 源码扫描）：
# 1. 遍历 tools/*.py 文件
# 2. 用 ast.parse() 解析源码
# 3. 检测是否有顶层的 registry.register(...) 调用
# 4. 如果有，才 import 该模块
```

**这样做的原因**：避免导入不相关的模块；不需要手工维护 import 列表；模块在 import 时自动注册。

### 两层注册

| 层面 | 机制 | 说明 |
|------|------|------|
| **自动发现** | AST 扫描 → import | 任何 `tools/*.py` 有 `registry.register()` 就会被发现 |
| **显式 toolset** | `toolsets.py` 的 `_HERMES_CORE_TOOLS` 列表 | 工具必须有 toolset 归属才会暴露给 agent |

自动发现是"知道有这个工具"，显式 toolset 是"让 agent 能用这个工具" —— 两者缺一不可。

---

## 三、核心执行循环：同步 + 异步桥接

`agent/conversation_loop.py`（~4700 行）是从 `run_agent.py` 抽出的核心循环：

```python
# 伪代码表示核心循环
while (api_call_count < max_iterations
       and iteration_budget.remaining > 0) \
       or budget_grace_call:      # 预算用完前的一次"grace call"
    
    if interrupted:               # 用户 /stop 或超时中断
        break

    response = llm.chat.completions.create(model, messages, tools)
    
    if response.tool_calls:
        for each tool_call:
            result = handle_function_call(name, args, task_id)
            messages.append(result)
        api_call_count += 1
    else:
        return response.content   # 最终文本回复
```

### 异步桥接机制

核心循环是**同步**的（Python 同步代码），但很多工具 handler 是 async 的（如 web_search 用 httpx）：

```
同步核心循环
    │
    ▼
model_tools.py._run_async(coro)
    ├── 主线程 → 使用持久化事件循环（不是 asyncio.run()）
    └── worker 线程 → 使用 thread-local 持久化循环
```

**为什么不直接用 `asyncio.run()`？** 因为 `asyncio.run()` 每次都创建新的事件循环并在执行后关闭它。这会导致缓存的 httpx/AsyncOpenAI 客户端在 GC 时尝试在已关闭的循环上清理资源，抛出 "Event loop is closed" 错误。持久化循环解决了这个问题。

### 中断机制

- `_interrupt_requested` 标志在每次迭代开始时检查
- 由 `/stop` 命令或超时触发
- 工具调用之间是中断点

---

## 四、工具系统：三层抽象

```
                 TOOLSETS (toolsets.py)
               ┌───────────────────────────┐
               │  _HERMES_CORE_TOOLS       │  ← 共享工具列表（57个工具）
               │  (所有平台继承)            │     包括 web_search, terminal,
               │                           │     read_file, write_file, patch,
               └──────────────┬────────────┘     delegate_task, cronjob,
                              │                  browser_*, kanban_* ...
               ┌──────────────▼───────────┐
               │  可组合的工具集 (27个)       │
               │  web, file, terminal,    │  ← 每个平台选一个 base toolset
               │  delegation, browser,    │     如 Telegram 用 "messaging"
               │  kanban, skills...       │
               └──────────┬───────────────┘
                          │
               ┌──────────▼──────────────┐
               │  独立工具 (60+个)           │
               │  tools/web_search.py    │  ← 每个文件 self-register
               │  tools/terminal_tool.py │     含 schema + handler + check_fn
               │  ...                    │
               └─────────────────────────┘
```

### Toolset 安全分层

| Toolset | 用途 | 安全级别 |
|---------|------|---------|
| `_HERMES_CORE_TOOLS` | 所有平台的默认工具集 | 标准 |
| `messaging` | Telegram/Discord 等消息平台 | 标准 |
| `safe` | 只读分析 | 高（无 terminal/write） |
| `webhook` | 来自第三方的不受信内容 | 极高（4个工具） |
| `kanban` | 多智能体协作 | 限制 |

**`webhook_safe_tools`** 只有：`web_search`、`web_extract`、`vision_analyze`、`clarify` —— 因为 webhook 内容来自不可信的第三方（如公开 PR 标题/评论），防止 prompt injection 导致本地文件操作。

### 动态 Schema 重写

工具 schema 描述必须避免引用其他 toolset 中的工具（那些工具可能不可用）。
跨工具引用通过 `get_tool_definitions()` 中的后处理逻辑动态添加 —— 检查目标工具是否真的可用后才注入引用。

---

## 五、插件系统：三条独立发现路径

```
PluginManager (hermes_cli/plugins.py)
├── Bundled: <repo>/plugins/<name>/
├── User:    ~/.hermes/plugins/<name>/
├── Project: ./.hermes/plugins/<name>/
└── Pip:     "hermes_agent.plugins" entry point

但有三类插件走独立发现（不在 PluginManager 管辖范围）：
├── Memory providers:      plugins/memory/<name>/       → agent/memory_manager.py
├── Model providers:       plugins/model-providers/<name>/ → providers/__init__.py
└── Image-gen / Context-engine: 各自独立的 ABC + orchestrator
```

### 插件能力

一个插件通过 `register(ctx)` 可以：

| 能力 | API | 说明 |
|------|-----|------|
| 注册新工具 | `ctx.register_tool(...)` | 带 schema + handler + check_fn |
| 注册 CLI 子命令 | `ctx.register_cli_command(...)` | 自动接入 `hermes <plugin> <subcmd>` |
| 生命周期钩子 | `pre_tool_call`, `post_tool_call` | 在 `model_tools.py` 中调用 |
| 生命周期钩子 | `pre_llm_call`, `post_llm_call` | 在 `run_agent.py` 中调用 |
| 生命周期钩子 | `on_session_start`, `on_session_end` | 会话级别 |

### 硬规则 (Teknium, 2026.05)

- 插件**禁止**修改核心文件（`run_agent.py`, `cli.py`, `gateway/run.py`）
- 插件需要新能力 → 扩展通用 hook API，不把插件逻辑硬编码进核心
- Memory providers：不再接受新的 in-tree provider —— 必须发布为独立插件 repo

---

## 六、Gateway：多平台消息架构

`gateway/run.py`（~19,500 行）是最大的单文件。核心职责：

```
GatewayRunner.start()
    ├── Telegram  adapter
    ├── Discord   adapter
    ├── Slack     adapter
    ├── WhatsApp  adapter
    ├── Signal    adapter
    ├── Matrix    adapter
    ├── Email     adapter
    ├── SMS       adapter
    ├── Feishu    adapter  (飞书)
    ├── WeCom     adapter  (企业微信)
    ├── DingTalk  adapter  (钉钉)
    ├── Weixin    adapter  (微信)
    ├── QQBot     adapter
    ├── HomeAssistant    (智能家居)
    ├── BlueBubbles       (iMessage)
    ├── Yuanbao           (腾讯元宝)
    ├── Webhook / API Server
    └── ... (20+ 平台)
```

### 平台适配器流程

```
用户消息到达
    │
    ▼
平台 adapter (如 telegram.py)
    │
    ├── 获取或创建 per-session AIAgent 实例
    │   └── LRU 缓存：128 上限，空闲 1h TTL 自动驱逐
    │
    ├── agent.run_conversation()
    │
    └── 结果返回对应平台
```

### 双门卫消息机制（关键安全设计）

```
用户发 "/stop" 想中断正在运行的 agent
    │
    ▼
【第一道门】base adapter (_process_message_background)
    │  检测 session 是否活跃
    │  活跃时 → 消息进入 _pending_messages 队列（不打断 agent）
    │
    ▼
【第二道门】gateway runner
    │  拦截 /stop, /new, /queue, /status, /approve, /deny
    │  Inline 处理（非后台），确保控制命令不被卡住
    │
    ▼
agent.interrupt() → 下一轮循环开始时退出
```

### 缓存感知的消息传递

网关确保：
- AIAgent 实例缓存复用时不重建系统 prompt
- 工具集在会话期间不变
- 记忆在会话期间不重新加载
- 这样保持 LLM 的 prompt caching 有效

---

## 七、Profile 多租户隔离

```
~/.hermes/                    ← 默认 profile
├── config.yaml
├── .env                      ← API keys (secrets only)
├── state.db                  ← SQLite 会话存储
├── skills/                   ← 用户技能
├── plugins/                  ← 用户插件
├── cron/                     ← 定时任务
├── logs/                     ← agent.log / errors.log
└── profiles/
    ├── coder/                ← 独立 profile "coder"
    │   ├── config.yaml, .env, state.db
    │   └── skills/
    └── writer/               ← 独立 profile "writer"
        ├── config.yaml, .env, state.db
        └── skills/
```

### 实现机制

```python
# hermes -p coder 启动时
_apply_profile_override("coder")
    ↓
HERMES_HOME = ~/.hermes/profiles/coder
    ↓
# 之后所有模块 import 时读取的配置/密钥/会话
# 都自动指向该 profile 的目录
```

**核心规则**：
- 所有路径引用必须用 `get_hermes_home()` 而非硬编码 `Path.home() / ".hermes"`
- `HERMES_HOME` 环境变量在任何模块 import 之前设置
- 配置文件 bridge：`config.yaml` 做结构化设置，`.env` 只放 API keys/密码

---

## 八、委派（Delegation）系统

```
Parent Agent (大上下文)
    │ delegate_task(goal="审查代码", context="文件在 /src/api.py")
    ▼
tools/delegate_tool.py
    │ 为子任务创建隔离的 AIAgent 实例
    │ 独立 context window, terminal session, toolset
    ▼
Subagent (小上下文，leaf/orchestrator)
    │ 执行任务
    │ 只返回摘要给父 agent（中间工具调用不进入父上下文）
    ▼
Parent Agent ← 看到摘要，继续工作
```

### 两种模式

| 模式 | 输入 | 并发 | 适用场景 |
|------|------|------|---------|
| 单任务 | `goal` + 可选 `context`/`toolsets` | ×1 | 审查代码、深度研究 |
| 批量 | `tasks: [{goal, context, toolsets}, ...]` | 最多 3 (可配置) | 并行多个独立研究 |

### 角色限制

| 角色 | 可用工具 | 不能用的工具 |
|------|---------|-------------|
| `leaf`（默认） | 大多数工具 | `delegate_task`, `clarify`, `memory`, `send_message`, `execute_code` |
| `orchestrator` | 含 `delegate_task` | `clarify`, `memory`, `send_message`, `execute_code` |

### 关键设计决策

- **同步**：子 agent 是同步执行的 —— 父 agent 被中断则子 agent 也被取消
- **不持久**：子 agent 的工作不跨 turn 保存。需要长期任务用 `cronjob`
- **前向验证**：子 agent 的摘要不能盲目信任 —— 父 agent 应验证关键操作结果

---

## 九、Cron 定时调度器

```
cron/scheduler.py (tick loop)
    │ 每 ~60s 检查到期任务
    ▼
cron/jobs.py (SQLite job store)
    ├── 周期性任务 ("30m", "every 2h", "0 9 * * *")
    ├── 一次性任务 (ISO timestamp)
    ├── 脚本任务 (script + no_agent=True → 零 token 开销)
    │   └── 适用场景：内存/磁盘看门狗、阈值告警
    └── 链式任务 (context_from: 上游 job 的输出注入下游 job)
```

### Cron Job 类型对比

| 类型 | 设置 | 行为 |
|------|------|------|
| **LLM 驱动** (默认) | `prompt` + 可选 `skills` | 每次触发完整 agent 循环 |
| **纯脚本** | `script` + `no_agent=True` | 只运行脚本，stdout 直接投递 |
| **链式** | `context_from` 引用其他 job ID | 上游结果注入下游 prompt |
| **脚本收集 + LLM 处理** | `script` + `prompt` | 脚本输出作为 agent prompt 的上下文 |

### 硬保障

| 机制 | 说明 |
|------|------|
| 3 分钟强制中断 | Cron session 超时，防止失控循环 |
| Catchup 窗口 | 错过执行窗口的任务，在半个周期内补跑 |
| 文件锁 | `~/.hermes/cron/.tick.lock` 防多进程重复 tick |
| skip_memory=True | Cron 不消耗 memory provider |
| 独立 session | Cron 结果不进主会话的消息历史 |
| 多平台投递 | `deliver` 参数控制投到哪里 |

---

## 十、状态存储与记忆系统

### SessionDB (hermes_state.py, ~3900 行)

```
SQLite 数据库 (WAL mode)
├── sessions 表        ← 会话元数据 (title, source, parent_session_id)
├── messages 表         ← 完整消息历史 (role + content JSON)
├── FTS5 全文索引       ← 跨所有 session 的快速文本搜索
└── 压缩分裂            ← 超长会话自动分裂为 parent/child 链
```

**设计决策**：
- WAL mode 支持并发读 + 一个写者（gateway 多平台场景）
- 网络文件系统（NFS/SMB）上自动降级为 journal_mode=DELETE
- `session_search` 工具通过 FTS5 搜索历史会话，返回相关片段 + 上下文窗口
- Schema v14，带迁移机制

### Memory Providers (插件式)

```
agent/memory_manager.py
    │
    ▼
MemoryProvider ABC
├── honcho      ← 默认
├── mem0
├── supermemory
├── byterover
├── hindsight
├── holographic
├── openviking
└── retaindb
```

**生命周期钩子**：
- `sync_turn(turn_messages)` — 每轮结束后同步
- `prefetch(query)` — 每轮开始前获取记忆
- `post_setup(hermes_home, config)` — 初次设置

---

## 十一、TypeScript TUI 前端

```
hermes --tui
  └─ Node (Ink/React)  ──stdio JSON-RPC──  Python (tui_gateway)
       │                                        └─ AIAgent + tools + sessions
       └─ 渲染聊天、composer、工具活动、审批
```

### 架构分层

| 层 | 技术 | 职责 |
|----|------|------|
| **渲染层** | Ink (React for terminal) | UI 渲染，所有视觉元素 |
| **通信层** | JSON-RPC over stdio | TypeScript ↔ Python 双向通信 |
| **业务层** | Python (tui_gateway) | AIAgent、工具执行、会话管理 |

### 关键 Surface 映射

| 功能 | Ink 组件 | Gateway 方法 |
|------|---------|-------------|
| 聊天流式输出 | `app.tsx` + `messageLine.tsx` | `prompt.submit` → `message.delta/complete` |
| 工具活动 | `thinking.tsx` | `tool.start/progress/complete` |
| 审批请求 | `prompts.tsx` | `approval.respond` ← `approval.request` |
| 会话选择 | `sessionPicker.tsx` | `session.list/resume` |
| 斜杠命令 | 本地 handler + 后端 fallthrough | `slash.exec` → `command.dispatch` |

### 斜杠命令流

1. 内置客户端命令（`/help`, `/quit`, `/clear`, `/resume`, `/copy`, `/paste`）在 `app.tsx` 本地处理
2. 其他命令 → `slash.exec`（运行在持久 `_SlashWorker` 子进程）→ `command.dispatch`

### Dashboard 集成（Web）

Dashboard 嵌入真正的 `hermes --tui`，不是重新实现：
- 浏览器加载 `web/src/pages/ChatPage.tsx`，用 xterm.js 渲染
- `/api/pty` WebSocket 端点 → PTY bridge → 真正的 `hermes --tui` 进程
- PTY 字节直接双向传输，服务端应用 `TIOCSWINSZ` 做窗口大小调整

---

## 十二、Kanban 多智能体协作

```
kanban board (SQLite)
    │
    ├── 任务池 (ready/claimed/blocked/completed)
    │
    ▼
Kanban Dispatcher (长驻循环)
    │ 每 60s 检查
    ├── 回收过期 claims
    ├── 提升 ready 任务
    ├── 原子性 claim 任务
    └── spawn 对应 profile 的 worker agent
        │
        ▼
Worker Agent (隔离的 AIAgent + kanban tools)
    ├── kanban_show     ← 看任务详情
    ├── kanban_complete ← 标记完成
    ├── kanban_block    ← 标记阻塞
    ├── kanban_comment  ← 添加评论
    └── kanban_heartbeat ← 保持 claim 活跃
```

### 隔离模型

- **Board** 是硬边界 —— worker 的 `HERMES_KANBAN_BOARD` 环境变量锁定 board
- **Tenant** 是软命名空间 —— 同一 board 内可以隔离多个商业客户
- **失败保护**：同一任务连续 `failure_limit` 次非成功即自动 block（防止死旋）

---

## 十三、技能（Skills）系统

### 两个技能表面

| 表面 | 位置 | 说明 |
|------|------|------|
| **skills/** | 仓库内置 | 按类别组织，默认可加载 |
| **optional-skills/** | 仓库内置但不活跃 | 重型/小众技能，用户显式安装 |

### SKILL.md 规范

```yaml
# 标准 frontmatter
name: skill-name
description: 一句话，≤60 字符，句号结尾。  # HARDLINE 要求
version: "1.0.0"
author: 人类贡献者优先  # HARDLINE：credit 人类而非 AI tool
platforms: [linux, macos]   # OS gating
metadata:
  hermes:
    tags: [python, testing]
    category: devops
    related_skills: [other-skill]
    config:         # 需要的 config.yaml 设置
      api_key: "YOUR_KEY"
```

### 技能引用工具规范（HARDLINE）

SKILL.md 中的工具引用必须使用 Hermes 原生工具名：
- `grep` → `search_files`
- `cat/head/tail` → `read_file`
- `sed/awk` → `patch`
- `find/ls` → `search_files target='files'`

### 缓存感知

斜杠命令（如 `/skills install`）默认 **延迟生效**（下个 session），带 `--now` 才会立即让当前 session 的 prompt cache 失效。这保护了 Anthropic 等提供商的 prompt caching 成本。

---

## 十四、核心代码量统计

| 文件 | 行数 | 职责 |
|------|------|------|
| `gateway/run.py` | 19,556 | 多平台消息网关主入口 |
| `cli.py` | 15,744 | 交互式 CLI orchestrator |
| `run_agent.py` | 4,816 | AIAgent 类定义 + forwarder |
| `agent/conversation_loop.py` | 4,707 | 核心代理循环 |
| `hermes_state.py` | 3,923 | SQLite 会话存储 |
| `hermes_cli/plugins.py` | 1,846 | 插件系统 |
| `model_tools.py` | 1,067 | 工具编排 |
| `toolsets.py` | 882 | 工具集定义 |
| `tools/registry.py` | 589 | 工具注册中心 |
| **总计** | **~53,000+** | 仅核心文件 |

加上 `agent/` 目录的 88 个模块、`tools/` 目录的 60+ 工具文件、`gateway/platforms/` 的 20+ 平台适配器、`plugins/` 的各种插件、`tests/` 的 ~17,000 测试（~900 文件），这是一个**大工程**。

---

## 十五、设计哲学总结

| 原则 | 体现 |
|------|------|
| **自注册优于中央列表** | 工具/插件/命令都通过 register 自描述，AST 自动发现 |
| **分层安全** | 每层有自己的安全边界（webhook safe tools, leaf subagent 禁用危险工具） |
| **Profile 完全隔离** | 通过 HERMES_HOME 环境变量实现，而非全局单例 |
| **插件不侵入核心** | 核心文件对插件封闭，扩展通过 hook API |
| **缓存是头等公民** | Prompt caching 贯穿整个会话生命周期，/skills install 默认延迟生效 |
| **Forwarder 模式抗膨胀** | `run_agent.py.__init__` 是 thin forwarder，实际逻辑在 `agent/agent_init.py` |
| **大文件不避讳** | 核心文件数千行到一万九千行，但不拆碎（forwarder 向内部分流） |
| **测试即契约** | 子进程隔离、hermetic env、不变式测试而非快照测试 |
| **依赖有上界** | 供应链安全 —— 所有依赖 `>=floor,<next_major`，禁止裸 `>=X.Y.Z` |
| **AST 扫描代替反射** | 工具发现、插件种类判定都通过 AST 源码扫描，解决 import 时机问题 |
| **持久化事件循环** | 异步桥接不用 `asyncio.run`，避免 "Event loop is closed" 问题 |

---

## 十六、对 OmniAgent 的参考价值

基于以上分析，Hermes Agent 对 OmniAgent 项目的参考价值如下：

### 1. 工具注册表模式（最值得借鉴）

```
Registry (无依赖) ← Tool files (自注册) ← Auto-discovery (AST 扫描) ← Consumer
```

这个模式的优点：
- 添加新工具只需一个文件，不需要修改任何中央注册表
- AST 扫描确保只有真正的工具文件被导入
- Toolset 提供安全分组，不同场景使用不同工具集

### 2. 工具集（Toolset）安全分层

- `_HERMES_CORE_TOOLS` → 所有平台共享
- 每个平台选自己的 base toolset
- 有高安全性的场景（webhook）使用受限工具集
- 这种分层设计在 OmniAgent 的多租户场景中很有用

### 3. 插件系统的三条路径

区分不同类型插件（通用插件 / Memory / Model Provider）使用独立发现路径，避免一个 PluginManager 包揽一切。OmniAgent 如果有多类型插件可以借鉴这个思路。

### 4. Profile 多租户方案

通过环境变量 `HERMES_HOME` 切换整个实例，而非在运行时通过参数传递。简单、彻底、不会遗漏，所有代码路径自动正确。

### 5. Delegation 子代理模式

子代理的关键设计：
- 隔离上下文（父看不到子的中间过程）
- 角色限制（leaf 不能 delegate，避免无限嵌套）
- 同步执行（不持久化）
- 前向验证（不信任子代理的摘要）

### 6. Gateway 双门卫消息机制

当 agent 正在运行时，用户消息如何处理：
- 普通消息 → 进队列
- 控制命令（/stop, /new, /approve）→ 必须 inline 处理，不能被队列卡住

### 7. 不需要借鉴的

- **大文件**：19,556 行的 `gateway/run.py` 有历史原因，OmniAgent 可以从开始就拆分
- **sync/async 混用**：同步核心循环 + 异步工具是历史包袱，建议全部 async
- **WSL 兼容负担**：很多代码在处理 Windows/WSL 边缘情况，纯 Linux 部署可以更简洁
