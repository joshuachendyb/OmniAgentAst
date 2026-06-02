
# Hermes Agent 系统架构分析

> **分析日期：** 2026-06-02  
> **代码仓库：** [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)  
> **分析路径：** `/mnt/f/agenttool/hermes`  
> **总代码量：** 核心文件 ~51,000+ 行，加上插件/工具/平台 ~20 万行+

---

## 目录

- [1. 整体拓扑](#1-整体拓扑)
- [2. 五层架构模型](#2-五层架构模型)
- [3. 数据流向](#3-数据流向)
- [4. 文件依赖链](#4-文件依赖链)
- [5. 核心执行循环](#5-核心执行循环)
- [6. 工具系统详解](#6-工具系统详解)
- [7. Gateway 多平台网关](#7-gateway-多平台网关)
- [8. Profile 多租户](#8-profile-多租户)
- [9. 关键设计模式](#9-关键设计模式)
- [10. 安全体系](#10-安全体系)
- [11. 代码规模统计](#11-代码规模统计)
- [12. 设计哲学](#12-设计哲学)

---

## 1. 整体拓扑

```
CLI (prompt_toolkit)    TUI (Ink/React + JSON-RPC)
        │                        │
        ▼                        ▼
 ┌──────────────┐     ┌─────────────────┐
 │  HermesCLI   │     │  tui_gateway    │
 └──────┬───────┘     └────────┬────────┘
        │                      │
        ▼                      ▼
 ┌──────────────────────────────────────┐
 │         AIAgent 核心                  │
 │  (run_agent.py + conversation_loop)   │
 └──────────┬────────────┬──────────────┘
            │            │
     ┌──────▼─────┐  ┌──▼──────────┐
     │  Gateway   │  │  ACP Adapter │
     │ (20+平台)  │  │  (IDE集成)   │
     └────────────┘  └─────────────┘
```

三条用户交互路径：
- **CLI** (终端命令 `hermes`) → HermesCLI → AIAgent
- **TUI** (终端 `hermes --tui`) → Ink/React UI → tui_gateway → AIAgent
- **Gateway** (微信/Telegram/Slack...) → gateway/run.py → AIAgent

---

## 2. 五层架构模型

```
┌───────────────────────────────────────────────────────────┐
│  第 1 层 · 交互入口层  (Interface Layer)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐     │
│  │  CLI     │ │   TUI    │ │ Gateway  │ │ ACP(IDE) │     │
│  │ 终端聊天  │ │ Ink界面  │ │ 20+平台  │ │ VS/Zed   │     │
│  │ 15,744行 │ │ TS+JSON  │ │ 19,556行 │ │          │     │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘     │
├───────┼─────────────┼───────────┼─────────────┼───────────┤
│       ▼             ▼           ▼             ▼           │
│  第 2 层 · 智能体核心层  (Agent Core Layer)                 │
│  ┌───────────────────────────────────────────────────┐    │
│  │  AIAgent (run_agent.py, 4,816行)                   │    │
│  │    ├─ 对话循环 (conversation_loop.py, 4,707行)     │    │
│  │    ├─ 提示词构建 (prompt_builder.py)               │    │
│  │    ├─ 上下文压缩 (compression)                     │    │
│  │    └─ 记忆系统 (memory, user_profile)              │    │
│  └───────────────────┬───────────────────────────────┘    │
├──────────────────────┼────────────────────────────────────┤
│  第 3 层 · 工具系统层  (Tool System Layer)                  │
│       ┌──────────────▼───────────────────────────┐        │
│       │  model_tools.py (1,067行) ← 工具调度中心  │        │
│       │    ├─ 同步核心 ↔ 异步工具 桥接            │        │
│       │    ├─ 持久化事件循环（每线程独立）         │        │
│       │    └─ 工具发现 → handle_function_call()   │        │
│       └────────┬───────────────┬──────────────────┘        │
│                ▼               ▼                          │
│     ┌──────────────┐   ┌────────────────┐                │
│     │ 工具注册表     │   │  82 个工具文件   │               │
│     │ registry.py   │   │  tools/*.py     │               │
│     │ (589行)       │   │  (AST自发现)     │               │
│     │ AST扫描+导入  │   │  每文件调用       │               │
│     └──────────────┘   │  register()     │               │
│                │   ▲   └────────────────┘                │
│                ▼   │                                     │
│     ┌──────────────────┐                                 │
│     │ toolsets.py      │  ← 工具集安全开关                 │
│     │ _HERMES_CORE     │    57个核心工具                   │
│     │ _TOOLS list      │    安全子集: safe(只读)            │
│     └──────────────────┘                                 │
├───────────────────────────────────────────────────────────┤
│  第 4 层 · 基础设施层  (Infrastructure Layer)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │ 会话存储  │ │ 配置管理  │ │ 日志系统  │ │ 定时任务    │  │
│  │ SQLite   │ │ YAML+env │ │ 分级日志  │ │ Cron/      │  │
│  │ FTS5全文 │ │ 多Profile │ │ agent.log│ │ Profile    │  │
│  │ 3,923行  │ │          │ │          │ │ 隔离       │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘  │
├───────────────────────────────────────────────────────────┤
│  第 5 层 · 插件扩展层  (Plugin Layer)                       │
│  ┌───────────────────────────────────────────────────┐    │
│  │  152 个插件目录                                     │    │
│  │  ├─ model-providers/ (15+ 模型厂商适配)             │    │
│  │  ├─ memory/ (Honcho, Mem0, SuperMemory...)         │    │
│  │  ├─ image_gen/ (FAL, Krea, OpenAI, xAI...)         │    │
│  │  ├─ context_engine/                                │    │
│  │  └─ kanban/ (多智能体工作队列)                       │    │
│  └───────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

---

## 3. 数据流向

### 3.1 用户消息 → 回复 完整路径

```
用户消息 (微信/终端/IDE)
    │
    ▼
┌──────────────────────────────────┐
│【第1层】Gateway / CLI / TUI       │
│  接收消息，解析来源，路由          │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│【第2层】AIAgent 核心               │
│  ├─ 构建 system prompt            │
│  │   (你是谁、什么环境、有什么工具)  │
│  ├─ 加载 记忆 (用户偏好、历史事实)  │
│  ├─ 加载 技能 (怎么做这件事)       │
│  └─ 进入循环:                     │
│       │                           │
│       ▼                           │
│    调用 LLM (DeepSeek/Claude/...)  │
│       │                           │
│       ├─ 文本回复 → 返回给用户     │
│       │                           │
│       └─ tool_calls               │
│            │                      │
│            ▼                      │
└───────────┬───────────────────────┘
            │
            ▼
┌──────────────────────────────────┐
│【第3层】model_tools.py 派发        │
│   ├─ 同步核心 ↔ 异步工具桥接       │
│   ├─ 安全检查 (Tirith)            │
│   └─ 执行工具                     │
│       │                           │
│       ▼                           │
│  工具执行结果 → 回填消息 → 继续循环 │
└──────────────┬───────────────────┘
               │
               ▼
┌──────────────────────────────────┐
│【第4层】状态持久化                 │
│   ├─ 会话存入 SQLite (FTS5索引)   │
│   ├─ 配置读写 (YAML + .env)       │
│   └─ 日志记录 (agent.log)         │
└──────────────┬───────────────────┘
               │
               ▼
      回复 →【第1层】Gateway 投递到微信
```

### 3.2 为什么会话不会丢？

- 每条消息实时写入 `~/.hermes/state.db`（SQLite + FTS5 全文索引）
- `/resume` 或 `--resume` 可以接回任何历史会话
- `session_search` 工具能搜索所有历史对话内容

---

## 4. 文件依赖链

```
tools/registry.py  (零依赖 — 所有工具文件的导入根)
       ↑
tools/*.py  (每个文件 import registry 并在模块顶层调用 register())
       ↑
model_tools.py  (导入 tools/registry + 触发工具发现)
       ↑
run_agent.py, cli.py, batch_runner.py, environments/
       ↑
gateway/run.py  (顶层编排器，创建 AIAgent 实例)
```

**核心依赖原则：越底层的模块依赖越少，越顶层越组合底层。**

---

## 5. 核心执行循环

```python
# 伪代码 — 实际实现在 agent/conversation_loop.py

while (api_call_count < max_iterations and budget > 0) or grace_call:
    if interrupt_requested:
        break  # 用户发了 /stop

    # 调用 LLM
    response = client.chat.completions.create(
        model=model,
        messages=messages,           # OpenAI 格式
        tools=tool_schemas           # 可用工具定义
    )

    if response.tool_calls:
        for tool_call in response.tool_calls:
            result = handle_function_call(name, args, task_id)
            messages.append(tool_result_message(result))
        api_call_count += 1
    else:
        return response.content      # 文本回复，结束
```

**关键约束：**
- 最大循环次数：`max_iterations` (默认 90)
- 一次"恩惠调用"：预算耗尽时再多跑一次
- 中断检查：每轮循环检查 `_interrupt_requested` 标志
- 上下文压缩：接近 token 上限时自动触发

---

## 6. 工具系统详解

### 6.1 两层发现 + 门控

```
          AST 扫描源码               工具集白名单
         (自动发现)                  (安全门控)
              │                         │
              ▼                         ▼
    ┌──────────────┐           ┌──────────────┐
    │ registry.py  │           │ toolsets.py  │
    │ ast.parse()  │──────────▶│ _HERMES_     │──▶ 对外暴露
    │ 扫描所有      │  发现后    │ CORE_TOOLS   │    57 个工具
    │ tools/*.py   │  导入      │              │
    └──────────────┘           └──────────────┘
```

- **第 1 层 (发现)：** AST 解析源码，无需导入即可知道哪些文件有工具
- **第 2 层 (门控)：** 只有 `_HERMES_CORE_TOOLS` 列表中的工具才对 agent 可见

### 6.2 工具集安全层级

| 工具集 | 工具数 | 说明 |
|--------|--------|------|
| `_HERMES_CORE_TOOLS` | 57 | 默认共享集合 |
| `messaging` | +消息工具 | Telegram/Slack/Discord 等 |
| `safe` | 只读子集 | 无 terminal/write_file，安全模式 |
| `webhook` | 4 | web_search + web_extract + vision + clarify |
| `debugging` | 额外 | 调试专用，默认关闭 |

### 6.3 同步核心 + 异步工具桥接

```
AIAgent 循环 (同步)
    │
    ▼
model_tools.py
    ├─ 检测工具是否是 async
    ├─ 为每个线程维护持久化 event loop
    └─ 在持久化 loop 上执行异步工具
        └─ 避免 "Event loop is closed" 崩溃
```

---

## 7. Gateway 多平台网关

### 7.1 支持的平台 (20+)

| 平台 | 适配器文件 | 特点 |
|------|-----------|------|
| Telegram | `telegram.py` | 话题/线程支持 |
| Discord | `discord.py` | 服务器+频道 |
| Slack | `slack.py` | 企业集成 |
| **WeChat/微信** | `weixin.py` | iLink Bot API |
| WhatsApp | `whatsapp.py` | Meta API |
| Signal | `signal.py` | 端到端加密 |
| 企业微信 | `wecom.py` | 企业通讯 |
| 飞书 | `feishu.py` | 企业协作 |
| 钉钉 | `dingtalk.py` | 企业通讯 |
| Email/SMS | `email.py` / `sms.py` | 邮件短信 |
| API Server | `api_server.py` | REST API |
| Webhooks | `webhook.py` | 事件触发 |
| 元宝 | `yuanbao.py` | 腾讯元宝群 |
| Matrix | `matrix.py` | 联邦协议 |
| Mattermost | `mattermost.py` | 自托管 |

### 7.2 WeChat (微信) 适配器细节

```
用户发消息
    │
    ▼
┌─────────────────────────────┐
│  Tencent iLink Bot API       │
│  ilinkai.weixin.qq.com      │
│                              │
│  登录: QR 码扫描              │
│  接收: _poll_loop() 长轮询    │
│  媒体: AES-128-ECB 加密CDN   │
│                              │
│  ⚠️ 限制: iLink Bot 身份      │
│  不能加普通微信群，仅DM        │
└─────────────────────────────┘
```

**配置 (`~/.hermes/.env`)：**
```
WEIXIN_TOKEN=xxx
WEIXIN_ACCOUNT_ID=xxx
WEIXIN_DM_POLICY=open|allowlist|disabled
```

### 7.3 消息双门安全机制

```
用户发送 "/stop" (agent 正在运行中)
    │
    ▼
Gate 1: Base adapter 排队到 _pending_messages
    │
Gate 2: Gateway runner 内联拦截 /stop
    │
    ▼
agent.interrupt() → 下一轮循环触发
```

---

## 8. Profile 多租户

### 8.1 隔离机制

```
~/.hermes/
├── config.yaml          ← 默认 profile
├── .env
├── skills/
├── sessions/
├── state.db
└── profiles/
    └── work/            ← "work" profile
        ├── config.yaml  完全独立
        ├── .env
        ├── skills/
        ├── sessions/
        └── state.db
```

### 8.2 实现原理

```python
# 在任何模块导入之前
_apply_profile_override()
os.environ["HERMES_HOME"] = profile_path

# 所有代码使用
from hermes_constants import get_hermes_home
path = get_hermes_home()  # 从不硬编码 ~/.hermes
```

**隔离范围：** 配置、API Key、技能、会话、记忆、定时任务 — 全部独立。

---

## 9. 关键设计模式

| # | 模式 | 说明 | 代码位置 |
|---|------|------|---------|
| 1 | **AST 自发现注册** | 工具文件不手写列表，用 `ast.parse()` 扫描 `registry.register()` 调用 | `tools/registry.py` |
| 2 | **Forwarder 代理** | `run_agent.py` 是薄壳，真正的实现在 `agent/` 子模块 | `run_agent.py` → `agent/conversation_loop.py` |
| 3 | **两层门控** | 发现工具 ≠ 暴露工具 | `registry.py` + `toolsets.py` |
| 4 | **同步核心+异步桥接** | 同步 agent 循环调用异步工具 | `model_tools.py` |
| 5 | **持久化 Event Loop** | 每线程一个持久化 loop，解决 httpx/AsyncOpenAI 缓存报错 | `model_tools.py` |
| 6 | **PluginManager** | 插件发现、加载、生命周期管理 | `hermes_cli/plugins.py` |
| 7 | **Profile 路径注入** | 环境变量注入 → 所有路径自动切换 | `hermes_constants.py` |
| 8 | **双门消息安全** | Gateway 消息通道 + runner 内联拦截 | `gateway/run.py` |

---

## 10. 安全体系

### 10.1 多层安全防护

```
┌─────────────────────────────────────┐
│ 输入层                               │
│  ├─ DM 策略 (open/allowlist/disabled)│
│  └─ 配对审批                          │
├─────────────────────────────────────┤
│ 执行层                               │
│  ├─ Tirith 命令安全检查               │
│  ├─ 危险命令审批 (/approve /deny)     │
│  ├─ 密钥自动脱敏 (redact_secrets)     │
│  └─ PII 脱敏 (redact_pii)            │
├─────────────────────────────────────┤
│ 工具层                               │
│  ├─ 工具集白名单 (toolsets.py)        │
│  ├─ 安全子集 safe (只读)              │
│  └─ 每个工具独立 check_fn             │
├─────────────────────────────────────┤
│ 数据层                               │
│  ├─ ~/.hermes/ 权限控制              │
│  ├─ .env 不提交到 git                │
│  └─ auth.json OAuth 令牌             │
└─────────────────────────────────────┘
```

### 10.2 密钥脱敏

```
终端输出: "sk-abc123xyz..." 
    ↓
redact_secrets 扫描
    ↓
终端输出: "sk-***REDACTED***"
```

**重要：** `security.redact_secrets` 是在进程启动时快照的，不能在会话中途通过工具调用修改——防止 LLM 自己关闭保护。

---

## 11. 代码规模统计

### 11.1 核心文件

| 文件 | 行数 | 职责 |
|------|------|------|
| `gateway/run.py` | 19,556 | 多平台消息网关主程序 |
| `cli.py` | 15,744 | 交互式 CLI 编排器 |
| `run_agent.py` | 4,816 | AIAgent 类 + forwarder |
| `agent/conversation_loop.py` | 4,707 | 核心 agent 循环 |
| `hermes_state.py` | 3,923 | SQLite 会话存储 (FTS5) |
| `hermes_cli/plugins.py` | 1,846 | 插件系统 |
| `model_tools.py` | 1,067 | 工具编排调度 |
| `toolsets.py` | 882 | 工具集定义 |
| `tools/registry.py` | 589 | 工具注册表 |

### 11.2 目录规模

| 目录 | 文件数 | 说明 |
|------|--------|------|
| `tools/` | 82 `.py` | 工具实现 |
| `agent/` | 84 `.py` | 智能体核心 |
| `hermes_cli/` | 101 `.py` | CLI 子系统 |
| `gateway/platforms/` | 30 `.py` | 平台适配器 |
| `plugins/` | 152 目录 | 插件系统 |

---

## 12. 设计哲学

### 12.1 原则

1. **自学习 (Self-improving)**
   - 通过 **Skills** 积累经验：解决复杂问题 → 存为技能 → 下次自动加载
   - Curator 后台自动维护技能生命周期（使用追踪、过期归档）

2. **Provider 无关 (Provider-agnostic)**
   - 同一套工具/流程，随时切换模型厂商
   - 支持的 Providers：OpenRouter, Anthropic, OpenAI, DeepSeek, Google, xAI, 15+ 其他

3. **多界面统一 (Multi-surface)**
   - 终端 CLI、Web TUI、微信、Telegram、IDE — 同一个 AIAgent 核心
   - 你在微信聊的内容，终端 `/resume` 能接上

4. **安全默认 (Secure by default)**
   - 密钥自动脱敏、命令审批、工具白名单、PII 保护 — 全部默认开启

5. **可扩展 (Extensible)**
   - 152 个插件目录：模型、记忆、生图、工作流 — 按需加载
   - MCP 协议支持：接入外部工具服务器

### 12.2 设计取舍

| 选择 | 代价 |
|------|------|
| 同步核心循环 | 异步工具需要桥接层 |
| AST 发现工具 | 启动时需扫描 ~82 个文件 |
| 多 Profile 完全隔离 | 磁盘空间翻倍 |
| OpenAI 消息格式 | 非 OpenAI 模型需要转换层 |
| Skill 文件注入 user message | 会影响对话上下文（但保护 prompt 缓存） |

---

## 附录：常用命令速查

```bash
# 启动
hermes                          # 交互式 CLI
hermes --tui                    # TUI 界面
hermes gateway run              # 启动多平台网关

# 会话管理
hermes sessions list            # 列出历史会话
hermes --resume <session_id>    # 恢复指定会话
hermes --continue               # 恢复最近会话

# 配置
hermes model                    # 选择模型/Provider
hermes config edit              # 编辑配置
hermes setup                    # 设置向导

# 调试
hermes doctor                   # 健康检查
hermes status                   # 组件状态
tail -f ~/.hermes/logs/agent.log  # 实时日志
```
