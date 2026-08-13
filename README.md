# OmniAgentAs-desk

> 基于 ReAct 架构的 AI 桌面智能体全栈 Web 应用（React + FastAPI），提供 Windows 桌面自动化能力（非独立桌面客户端）

**版本**: v0.19.14 | **更新时间**: 2026-08-13 16:53:24 | **作者**: 北京老陈团队 | **更新人**: 小欧-2026-08-13

---

## 一、项目概述

OmniAgentAs-desk 是一个基于 **ReAct (Reasoning + Acting)** 架构的智能助手桌面应用，具备以下核心能力：

| 能力 | 说明 |
|------|------|
| **63个工具函数** | 覆盖 file/shell/network/system/desktop/document/dataanalysis/fundamental/win_registry/timer 共10个分类 |
| **ReAct推理引擎** | thought → action → observation 循环推理 |
| **统一Agent调度** | 单一 UniversalAgent（BaseAgent 子类，配置驱动），无 AgentFactory 分发 |
| **多AI Provider** | OpenCode、智谱AI、DeepSeek、Kimi等 OpenAI兼容API |
| **流式响应** | SSE实时推送，推理过程即时可见 |
| **会话管理** | 历史记录、搜索、标题自动生成、跨会话切换 |
| **安全防护** | 四层安全体系：安全开关(config.yaml) → 工具安全级别 → 已知风险检测(路径越权/写入污染/代码注入/删除安全R1-R6) → safety DB事务编排 |

---

## 二、技术架构

### 2.1 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| **后端** | Python / FastAPI / Uvicorn | 3.13 / ≥0.109.0 / ≥0.27.0 |
| **前端** | React / TypeScript / Vite / Ant Design | 18 / 5 / — / 5 |
| **LLM集成** | 多Provider适配层（OpenAI兼容API） | — |
| **数据库** | SQLite 原生 `sqlite3`，3 个库：chat_history.db / operations.db / task_tracker.db；无 PostgreSQL/MySQL 连接 | — |
| **任务执行** | 请求内流式（SSE），`run_react_cycle` 单请求驱动；无独立任务队列/Redis | — |
| **测试** | pytest / Vitest / Playwright | — |

### 2.2 当前架构图（代码实际，v0.19.14）

```
┌─────────────────────────────────────────────────────────────┐
│                 前端 (React + Vite + Ant Design)             │
│  ┌─────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  Chat   │  │  Settings  │  │  Session   │  │ Security│ │
│  │   UI    │  │    UI      │  │    UI      │  │  Alert  │ │
│  └────┬────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘ │
│       └────────────┴─────────────┴────────────┘         │
│                         │ SSE 流式 / REST                 │
└─────────────────────────┬───────────────────────────────┘
                           │
┌─────────────────────────┴───────────────────────────────┐
│         后端 API 薄壳层 (FastAPI，单进程，无独立网关)      │
│  ┌──────────────────────────────────────────────────┐  │
│  │  api/v1 薄壳路由: chat/task/execution/health/     │  │
│  │  messages/sessions/model/tool/task-queries/metrics │  │
│  └──────────────────────┬───────────────────────────┘  │
│                         │                              │
│  ┌──────────────────────┴───────────────────────────┐  │
│  │  编排层 (services/chat/stream_orchestrator)       │  │
│  │   chat_stream_orchestrator → run_react_cycle      │  │
│  │   StreamState + SSE 流式编排                      │  │
│  ├──────────────────────────────────────────────────┤  │
│  │  Agent: agent_runner + UniversalAgent +          │  │
│  │         react_cycle + tool_loader                │  │
│  │  Tool:  tool_facade ─→ tool_executor(统一执行入口)│  │
│  │         ─→ ToolRegistry 10分类63工具 + security守卫│  │
│  │  LLM 客户端(httpx, 多Provider)                   │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │  安全层（app/safety，独立顶层）L0-L3:             │  │
│  │   config开关→安全级别→已知风险→DB事务编排          │  │
│  │   (+tools/security 守卫 + hooks ContextVar)      │  │
│  └──────────────────────────────────────────────────┘  │
│  数据层：SQLite 3库(chat_history/operations/task_tracker)│
└─────────────────────────────────────────────────────────┘
```

> 说明：v0.19.6-v0.19.14 完成 **A1-A7 架构分层重构**（详见 2.4）：`api/v1` 路由薄壳化（业务/编排 CRUD 下沉至 services）、`safety` 提升为独立顶层 `app/safety`、新增安全 hooks 与编排层 `stream_orchestrator`。FastAPI 直接对外提供 REST/SSE，未独立出「网关层（认证/权限/限流）」微服务；任务在单次请求内由 `run_react_cycle` 流式执行，无独立任务队列。详见 2.3/2.4。

### 2.2.1 分层依赖铁律（本次重构后确立）

backend/app 采用**六层单向依赖**架构，上层只允许依赖下层，禁止反向、禁止双向、禁止环：

```
API/接口适配层（api/v1，薄壳，只调 services）
   │  禁止：tools/*、safety/*、db/*
   ▼
编排层（services/agent + services/chat/stream_orchestrator）
   │  允许：services 子域 + safety + tools公共接口 + utils + db
   ▼
业务服务层（services/chat·task·llm·model·tool·prompts·lifecycle·monitoring·visualization）
   │  允许：safety + tools公共接口 + utils + db；禁止：tools具体实现模块
   ▼
安全层（app/safety，独立顶层目录）
   │  允许：tools/* + utils/* + db/*；禁止：services/*
   ▼
工具层（app/tools，10分类63工具 + security守卫 + validate校验 + toolhelper）
   │  允许：utils + config + constants；禁止：services/*、safety/*
   ▼
公共基础设施层（app/utils + app/logger + app/config + app/constants）
```

依赖方向恒为 **`api → services → safety → tools → utils/db/logger`**，单向无环。该铁律由守护测试 `tests/test_architecture_boundaries.py`（3 条规则）持续强制，防止腐化回退。


---

### 2.3 架构现状与初始设计蓝图的偏差

> 下表对比「当前代码实际（v0.19.14）」与「项目初始设计蓝图 `doc-系统初建/OmniAgentAst_系统设计方案.md` 中的理想架构」。该蓝图规划了微服务化、网关层（JWT+OAuth2 认证/限流）、Redis 任务队列、多端接入等形态，但当前实现为**单进程紧凑架构**，未落地这些分布式组件。下表如实标注差距与取舍原因。

| 维度 | 当前实现（代码实际） | 初始蓝图规划 | 取舍说明 |
|------|----------------|-------------|---------|
| 接入端 | 仅 React Web App + FastAPI REST/SSE | 多端接入（Web/桌面/移动） | 暂仅 Web，桌面能力由工具层提供 |
| API 网关 | FastAPI 直接对外，无独立 Gateway | 独立 gateway 微服务（JWT+OAuth2+限流 100req/min） | 单机直接暴露，未拆分微服务 |
| 用户认证 | 仅 HITL 人工确认 + 敏感字段脱敏 | JWT + OAuth2 登录体系 | 未落地用户体系 |
| 权限 | 工具/文件路径级校验 | 用户级 RBAC | 保留工具级，未做用户级 |
| 限流 | 仅 LLM 429 检测 | 请求级/IP 限流 | 未做请求级 |
| 日志 | `app/logger/` | 日志系统 | ✅ 已实现 |
| 任务队列 | 无；单次请求内流式执行，`TaskTracker`（`services/task`）做暂停/取消/恢复 | Celery + Redis 异步任务队列 | 未引入 Redis |
| 缓存 | 无 | Redis 缓存 | 未引入 |
| Agent 执行 | `UniversalAgent` + `run_react_cycle` | — | ✅ |
| 工具注册 | `ToolRegistry` 单例 + `ensure_tools_registered()`，10 分类 63 工具 | — | ✅ |
| 数据存储 | SQLite（chat_history.db/operations.db/task_tracker.db） | PostgreSQL + Redis + MinIO + Elasticsearch | 单机 SQLite，无 PG/MySQL 连接层 |

**结论**：系统按「单进程 FastAPI + React Web + ReAct Agent + 工具注册表 + SQLite」落地，未实现初始蓝图的分布式组件（网关/认证/RBAC/限流/Redis/任务队列/多端）。取舍原因是单机/单用户场景下这些组件增加部署复杂度而对核心 ReAct 能力无增益，属**有意的范围收敛**而非技术债。

---

### 2.4 v0.19.x 架构分层重构（A1-A7）：为什么变、变成什么样

> 本节回答「这次架构变化的重要点是什么、为什么这样变化」。本次重构（v0.19.6-v0.19.14）**不是加新功能，而是整理 backend/app 的分层与依赖**，目标是消除 7 个架构分层违规，确立「分层清晰、依赖单向、职责单一」的基线。完整设计见 `doc-8月优化/backend架构分层违规问题分析与修复实施方案-小欧-2026-08-12.md`。

#### 2.4.1 为什么要变（7 个违规问题）

| 编号 | 优先 | 问题 | 病根 | 重构手段 |
|------|------|------|------|---------|
| A1 | P0 | **tools 层与 services/safety 双向依赖** | file 工具直接 import `app.safety`（要记录/要保护）；safety 又 import `tools.registry`（要判断白名单），双方互把对方当地基 | **hooks 注入（ContextVar）**：工具改为 `get_current_hooks()` 取安全能力，`path_safe_check/temp_auth/SafetyResult` 迁入 `tools/security/` |
| A2 | P1 | **app/safety 内部循环依赖** + 越层 | backup/cleanup/record 三个模块互相引用成环；rollback 反向依赖 task | operation_cleanup 并入 operation_maintenance；回滚编排下沉 `task_rollback_service` |
| A3 | P1 | **tool_retry_engine 目录归属错误** | 工具层基础设施却放在 Agent 编排目录 | 移动归位 `tools/` |
| A4 | P2 | **API 层越层直操作工具** | `health.py` 直接 import tool_registry 并暴露 `/tool/execute`，绕过 Agent 编排层和安全层 | 新增 `services/tool/tool_facade` 门面（见 2.4.3） |
| A5 | P2 | **file_path_checker 职责混杂** | 路径校验与 SQL/数据/读写错误提示同文件 | 拆 `tools/toolhelper/error_hints.py` |
| A6 | P2 | **base_agent 抽象基类依赖具体 registry** | 抽象基类直接 import `app.tools.registry.tool_registry` | 独立 `tool_loader.py` |
| A7 | P1 | **API 层职责膨胀** | `openai.py/sessions.py/messages.py/model_routes.py` 内嵌编排与业务 CRUD | 编排迁 `stream_orchestrator`；CRUD 下沉 `session/message/config_service`；API 薄壳 |
| — | — | **safety 目录归属错位**（架构调整，非违规） | safety 原是 services 子目录，与"层=目录"不一致 | 提升为独立顶层 `app/safety` |

#### 2.4.2 重构后达成什么

| 成效 | 结果 |
|------|------|
| **tools 层零反向依赖** | `tools/` 下不再出现 `from app.services.*`、`from app.safety.*`（守护测试强制） |
| **API 层零越层** | `api/v1` 不再 `from app.tools.*`、`from app.safety.*` |
| **safety 独立顶层** | `app/safety/` 与 services/tools 平级，全文无 `app.services.safety` 残留 |
| **依赖单向** | 恒 `api → services → safety → tools → utils/db/logger`，由 `tests/test_architecture_boundaries.py` 3 规则守护 |
| **守护测试全绿** | api/tools/safety 三层边界规则 ✅ |
| **全量回归** | 架构重构 + 35 项核查修复后，`pytest` 全量通过（守护测试 3 规则全绿 + 既有测试零回归） |

#### 2.4.3 为什么需要 `tool_facade`（A4 的核心）

`tool_facade`（`services/tool/tool_facade.py`）是为解决 A4「API 层不能直接碰 tools/safety」而**新建的接口适配层门面**，但它不是简单"包一层"：

- **它承接的职责**：`api/v1/tool_routes.py` 的 `/tool/list`、`/tool/execute` 两个接口（挂载 `/api/v1`），统一走 `list_tools()` / `execute_tool()` 两个门面函数
- **为什么必须存在**：重构前 `health.py` 的 `/tool/execute` 直接 `tool_registry` 执行工具，**绕过了 Agent 编排层与安全层**——与 chat 路径（`action_handler → tool_safety_checker → tool_executor`）形成**两条独立执行路径**，安全检查力度可能不一致（安全盲区）
- **它解决什么**：`execute_tool` **复用 tool_executor 统一执行入口**（消双路径），门面只做「安全预检（`get_tool_safety_checker().check_before_execute`）+ 任务上下文管理（`try/finally reset ContextVar`，防并发污染）」，**不重复实现执行逻辑**，与 chat 路径共享同一套安全 hooks 与执行器
- **依赖方向**：`services/tool → safety(checker) + services/agent(tool_executor) + tools(registry)`，单向无环

```
重构前（A4，双路径/越层）:                         重构后（A4，统一门面）:
 /tool/execute ─→ tool_registry.impl() 越层执行    /tool/execute ─→ tool_facade.execute_tool
   （绕过安全层/编排层，安全盲区）                        ├─ 安全预检 check_before_execute
 chat路径 ─→ action_handler ─→ tool_safety_          ├─ set task ContextVar(finally reset)
   checker ─→ tool_executor（完整安全链）              └─ 复用 tool_executor（与 chat 同源）→ 同一安全链
```

**它到底什么时候被调用（主对话链路平时不经过它）：**

| 调用方 | 是否经 `tool_facade` | 说明 |
|--------|---------------------|------|
| **日常对话**（Agent 自动调工具） | ❌ 不走 | `action_handler.py:117` 直接 `tool_executor.execute_tool`，Agent 主链路不经过门面 |
| `/api/v1/tool/list` | ✅ 走 `list_tools()` | 正常接口，无开关限制，随时可用 |
| `/api/v1/tool/execute` | ✅ 走 `execute_tool()` | **仅测试用**：双保险 `X-Test-Mode: 1` 头 + 生产开关 `tools.execute_tool_enabled` 默认 **False**（`tool_routes.py:36-66`），生产拒执行 |

> **一句话**：`tool_facade` 平时（生产对话/演示）**几乎不干活**——`/tool/execute` 生产默认关闭，主对话链路也绕开它。它不是一个"常被调用的服务"，而是 A4 的**架构合规边界**：让「API 层可以合法暴露工具测试能力」且**不越层碰 tools**（守护测试 `api 禁 tools` 依赖它变绿）。真正干活的是它复用的 `tool_executor`——门面保证测试与对话**走同一条安全执行链路**，堵住 `health.py` 时代的越层安全盲区，这就是 A4 的实质价值。

---

## 三、工具体系（63个）

### 3.1 工具分类（10个ToolCategory，共63工具）

| 分类 | 数量 | 说明 |
|------|------|------|
| **FILE** | 14 | 文件读写、搜索、编辑、归档、树、校验等 |
| **SHELL** | 1 | 命令查找（which）；Shell/Python执行已迁入 FUNDAMENTAL |
| **NETWORK** | 5 | HTTP请求、下载、网页抓取、网络诊断、搜索 |
| **SYSTEM** | 4 | 系统计划任务、事件日志 |
| **DESKTOP** | 11 | 窗口管理、截屏、剪贴板、键鼠、通知 |
| **DOCUMENT** | 8 | PDF/Word/Excel/PPT 读写 |
| **DATAANALYSIS** | 6 | SQL查询/执行、图表生成、数据筛选/分析 |
| **FUNDAMENTAL** | 5 | Shell命令执行、系统信息、时间日期、通知、工具搜索 |
| **WIN_REGISTRY** | 3 | 注册表读/写/删 |
| **TIMER** | 6 | 定时器设置/列出/清除 + 时间计算(timeadd/timediff/calendar) |
| **合计** | **63** | |

> **注**：分类与数量以 `backend/app/tools/tool_constants.py` 的 `CATEGORY_MODULES` + 运行时 `ensure_tools_registered()` 为准（上述为 v0.19.14 实际加载值，已验证 63 工具 10 分类）。v0.18.35 起 Shell 命令执行迁入 FUNDAMENTAL（`execute_shell_command` 注册为 `shell` 工具），SHELL 分类仅保留 `which`；timeadd/timediff/calendar 自 FUNDAMENTAL 迁入 TIMER。`validate/` 为校验层（路径/URL/超时/注册表），不计入对外工具。

### 3.2 工具注册架构

```
backend/app/tools/
├── registry.py              # ToolRegistry 单例 + tool_registry + ensure_tools_registered
├── tool_types.py            # ToolCategory 枚举 / ToolMetadata
├── tool_constants.py        # CATEGORY_MODULES（分类→模块/注册函数映射）
├── tool_aliases.py          # 工具别名映射
├── tool_loader.py           # 工具按 category 加载（per-agent 集合）
├── toolhelper/              # 工具辅助（hint_* 错误提示 / 重试工具）
├── validate/                # 校验层（路径/URL/超时/注册表，非对外工具）
├── security/                # 安全守卫（path_safe_check/temp_auth/safety_result，非对外工具）
├── file/                    # 文件操作（14）
├── shell/                   # 命令查找 which（1）
├── network/                 # 网络通信（5）
├── system/                 # 系统计划任务/事件日志（4）
├── desktop/                # 桌面操作（11）
├── document/               # 文档处理（8）
├── dataanalysis/            # 数据分析（6）
├── fundamental/             # 基础能力（5，含 Shell 命令执行 + shell_engine + 提示词模板）
├── win_registry/            # 注册表（3）
└── timer/                   # 定时器 + 时间计算（6）
```

每个分类目录结构（`{category}_register.py` 为注册入口，`{category}_tools.py` 为具体实现）：
```
{category}/
├── __init__.py              # 导入触发注册
├── {category}_schema.py     # Pydantic 参数模型
├── {category}_register.py   # 注册点（_register_{category}_tools）
└── {category}_tools.py      # 具体实现
```

> v0.19.14 说明：安全守卫 `path_safe_check`/`temp_auth`/`SafetyResult` 已由 `app/safety` 迁入 `app/tools/security`（A1），为独立安全守卫层，不计入对外工具数；工具门面 `tool_facade` 位于 `app/services/tool/`（A4）——日常对话主链路（`action_handler → tool_executor`）**不经过它**，它仅为 API 层合法暴露工具能力（`/tool/list` 随时可用；`/tool/execute` 仅测试用，生产开关默认关闭），详见 2.4.3。


---

## 四、Agent体系

### 4.1 当前架构（BaseAgent + 单一 UniversalAgent）

```
BaseAgent(ABC)                 ← 抽象基类，含 run_react_cycle 编排钩子
    ↓ 继承
UniversalAgent(BaseAgent)      ← 唯一实现类，配置驱动（模型/系统提示词/工具集由配置决定，无意图分发）
```

> 代码实际（`backend/app/services/agent/`）：`base_agent.py` 的 `BaseAgent(ABC)` + `universal_agent.py` 的 `UniversalAgent(BaseAgent)` 为核心，无 `AgentFactory` 分发、无意图识别/分发机制（CRSS 已移除）。请求经 `api/v1` 薄壳路由 → 编排层 `stream_orchestrator.chat_stream_orchestrator` → `agent_runner.run_agent_in_background` → 直接构造 `UniversalAgent` 调用 `run_react_cycle`。系统提示词由 `PromptBuilder.build_full_system_prompt` 统一构建，工具集由 `tool_loader` 按 Agent 预加载分类加载（`_loaded_categories`），均与意图无关；`intent` 仅作为 task DB 的 TEXT 字段记录，无调度语义。其余模块为 ReAct 循环与编排支撑：`react_cycle.py`（ReAct 循环核心）、`tool_executor.py`、`handlers/`（action/answer）、`steps/`（Thought/Tool/Final 等 Step）+ `llm_stream`/`message_builder`/`observation_formatter`/`status_table`/`tool_cache_manager`/`initialize_run_state`/`chunk_buffer`/`step_emitter` 等。

### 4.2 安全体系（v0.19.14）

| 层 | 模块 | 职责 |
|---|------|------|
| L0 | config.yaml security.enabled | 全局开关，关闭后跳过所有安全检查 |
| L1 | 工具安全级别（字符串枚举：read_only/safe/destructive/dangerous） | 工具声明式安全级别，由工具经 `SafetyResult(safety_level=...)` 返回 |
| L2 | ToolSafetyChecker._check_known_risks | 运行时已知风险检测：路径越权/写入污染/代码注入/删除安全判定(delete_safety R1-R6) |
| L3 | app/safety.operation_record.execute_with_safety | DB事务编排：操作记录写入→状态追踪→备份→文件hash→审计 |
| L3 | app/safety.operation_record.record_operation | 操作记录持久化(operations.db)，支持回滚 |
| hooks | app/tools/security + security_hooks + context | A1 安全 hooks 协议：`get_current_hooks()`/ContextVar 注入（`tools/context.py`），工具可调用 record_operation/execute_with_safety，NoOpHooks 兜底防 NPE |

> **v0.19.14 架构演进**：
> - **L3 顶层化**（A1/A2）：`app/services/safety/` 整目录提升为顶层 **`app/safety`**（`operation_record`/`operation_backup`/`operation_rollback`/`operation_maintenance`/`delete_safety`/`hash_helper`/`tool_safety_checker`/`default_hooks`/`models`），消除 tools→services 越层
> - **职责更名**：原 `operation_cleanup.py` 更名为 **`operation_maintenance.py`**（负责过期备份+回收站超限清理）
> - **安全守卫下沉**：`path_safe_check`/`temp_auth`/`SafetyResult` 迁入 **`app/tools/security/`**（A1），`security_hooks` 协议与 `context._current_hooks` ContextVar 提供工具层安全能力
> - **hooks 兜底**（BUG-3）：新增 `get_current_hooks_or_noop()` 返回 `NoOpHooks`，消除入口未注入时 `get_current_hooks()` NPE
> 
> L3 层在 v0.15.9 从空壳 stub（仅生成 UUID）重构为真实 file_safety 委托，恢复完整的 DB 事务编排和回滚能力；并新增删除确认策略矩阵 R1-R6 与系统盘符动态化（`get_existing_drives`）。

### 4.3 Agent 2.0（规划中）

| 模块 | 状态 | 说明 |
|------|------|------|
| SemanticRouter | 规划中 | 基于 LLM Function Calling 的工具子集推荐器（取代旧的 CRSS 正则意图分类；**当前代码未实现**，仅存于 `doc-5月优化/doc-5月agent2.0/` 设计文档） |
| ToolSafetyLayer | 规划中 | 工具声明式安全分级（部分能力已由现有安全级别字符串 read_only/safe/destructive/dangerous 承载，见 4.2 L1） |
| ToolObserver | 规划中 | 全量审计日志 + 异常检测 |
| HITL | 已实现 | DANGEROUS 工具人机协同确认已落地（`action_handler.authorization_required` + `wait_for_confirmation_result` + `hitl_confirmation.py`） |

> 统一Agent（BaseAgent → UniversalAgent）已在 v0.14.0 完成，方案设计见 `doc-5月优化/doc-5月agent2.0/`。HITL 确认机制在 v0.18.x 已接入。Agent 2.0 的语义路由为**历史规划**，当前 v0.19.14 代码**未实现任何意图/语义路由**。

---

## 五、项目结构

```
OmniAgentAs-desk/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 薄壳路由（chat/task/execution/health/messages/sessions/model/tool/task-queries/metrics）
│   │   ├── db/                 # 数据库（原生 sqlite3 连接：database.py / db_initializer.py / operation_queries.py）
│   │   ├── logger/             # 日志配置
│   │   ├── safety/             # 安全体系（顶层，A1/A2 提升）：operation_record/operation_backup/operation_rollback/operation_maintenance/delete_safety/hash_helper/tool_safety_checker/default_hooks/models
│   │   ├── tools/              # 工具函数（10分类63工具，含 security 安全守卫 + validate 校验层 + toolhelper）
│   │   ├── services/
│   │   │   ├── agent/          # Agent体系（base_agent + universal_agent + agent_runner + react_cycle + tool_loader + handlers + steps）
│   │   │   ├── chat/           # 对话编排（stream_orchestrator 编排 + stream + handlers + storage + session/message_service + migrate_steps）
│   │   │   ├── lifecycle/      # 生命周期管理
│   │   │   ├── llm/            # LLM 客户端（httpx 多Provider）
│   │   │   ├── model/          # 模型解析/持久化
│   │   │   ├── monitoring/     # 监控（middleware / collector）
│   │   │   ├── prompts/        # 系统提示词适配
│   │   │   ├── task/           # 任务追踪（TaskTracker + task_db/task_state/task_registry/task_runtime，暂停/取消/恢复 / hitl_confirmation）
│   │   │   ├── tool/           # 工具门面（tool_facade，A4）
│   │   │   └── visualization/  # 可视化报告（mermaid/html/tree 等）
│   │   └── utils/
│   ├── e2etests/               # 端到端测试（P0/P1/P2 全链路）
│   ├── logs/                   # 运行日志
│   ├── migrations/             # DB 迁移
│   ├── scripts/                # 辅助脚本
│   ├── tests/                  # 后端测试（pytest）
│   └── requirements.txt
├── frontend/                   # React + TypeScript 前端（Web App，非桌面/移动端）
│   ├── src/
│   │   ├── components/         # UI 组件（Chat / Security / Layout 等）
│   │   ├── contexts/           # React Context（AppContext / SecurityContext）
│   │   ├── pages/              # 页面
│   │   ├── services/           # API 服务
│   │   ├── hooks/              # 聊天流/任务控制等 Hook
│   │   ├── types/              # TS 类型定义
│   │   └── utils/              # 工具函数（SSE 处理等）
│   ├── tests/                  # 前端测试（Vitest / Playwright）
│   └── package.json
├── config/                     # 配置文件
├── doc-5月优化/                # 5月优化（含 doc-5月agent2.0 架构设计文档，旧称 doc-agent2.0）
├── doc-*/                      # 各月优化/专题设计文档目录
├── doc/                        # 系统设计文档
├── notes/                      # 调试笔记
├── version.txt                 # 版本变更记录（append-only）
└── AGENTS.md                   # 开发规范
```

---

## 六、快速开始

### 6.1 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 测试用 3.13 |
| Node.js | ≥ 18.x | — |
| npm | ≥ 9.0 | — |

> **虚拟环境说明**：Python 后端强烈建议使用虚拟环境，原因：
> 1. **隔离依赖** — 不同项目用不同版本的包，互不冲突（如项目A用pydantic 2.5、项目B用pydantic 2.13）
> 2. **干净卸载** — 不要了直接删 `.venv` 目录，不影响全局 Python
> 3. **环境可复现** — `requirements.txt` 一键装完，新同事 clone 下来就能跑

### 6.2 初次安装（新人从零开始）

> **前提**：已下载项目代码，打开命令行（PowerShell / cmd），`cd` 到项目文件夹（如 `cd D:\OmniAgentAs-desk`）。

后端和前端需要**同时运行**，所以要开**两个命令行窗口**。

---

#### 窗口 1 — 后端（选一种方式）

先进入后端目录：

```bash
cd backend
```

**方式 A（推荐）：虚拟环境**

```bash
# ① 创建虚拟环境（仅第一次需要）
python -m venv .venv

# ② 安装依赖（仅第一次需要）
.venv\Scripts\pip install -r requirements.txt

# ③ 启动后端服务
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

> 启动 uvicorn 后这个窗口**不要关闭**，它要一直运行。

**方式 B：全局 Python（不用虚拟环境）**

```bash
# ① 安装依赖（仅第一次需要）
pip install -r requirements.txt

# ② 启动后端服务
python -m uvicorn app.main:app --reload --port 8000
```

> 方式 B 的包装到全局，不同项目依赖版本不同时可能冲突。
> 启动后这个窗口**同样不要关闭**。

---

#### 窗口 2 — 前端（两种方式一样）

再开一个命令行窗口，同样先 `cd` 到项目文件夹，然后：

```bash
cd frontend

# ① 安装依赖（仅第一次需要）
npm install

# ② 启动前端开发服务器
npm run dev
```

> 这个窗口启动后**也不要关闭**。

---

#### 打开浏览器访问

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 前端页面 |
| http://127.0.0.1:8000 | 后端 API |
| http://127.0.0.1:8000/docs | API 交互式文档 |

---

### 6.2a 日常运行（第二次及以后）

不用再装依赖了，直接启动就行。同样开**两个命令行窗口**，先 `cd` 到项目文件夹。

#### 窗口 1 — 后端

```bash
cd backend
```

**虚拟环境方式：**

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

**全局 Python 方式：**

```bash
python -m uvicorn app.main:app --reload --port 8000
```

> 启动后窗口 1 不要关闭。

#### 窗口 2 — 前端

```bash
cd frontend
npm run dev
```

> 启动后窗口 2 不要关闭。

### 6.3 可选依赖（二级工具）

这些包大部分已包含在 `requirements.txt` 中。如需单独安装：

<details>
<summary><b>虚拟环境</b></summary>

```bash
cd backend
.venv\Scripts\pip install pandas matplotlib
.venv\Scripts\pip install pdfplumber python-docx openpyxl
.venv\Scripts\pip install pyautogui pywin32 pytesseract Pillow
.venv\Scripts\pip install mss imageio numpy
```
</details>

<details>
<summary><b>全局 Python</b></summary>

```bash
cd backend
pip install pandas matplotlib
pip install pdfplumber python-docx openpyxl
pip install pyautogui pywin32 pytesseract Pillow
pip install mss imageio numpy
```
</details>

---

## 七、开发命令

### 后端

<details>
<summary><b>虚拟环境（推荐）</b></summary>

激活后命令直接敲，无需前缀：

```bash
cd backend
.venv\Scripts\activate
```

| 命令 | 说明 |
|------|------|
| `uvicorn app.main:app --reload` | 启动开发服务器 |
| `pytest` | 运行全部测试 |
| `pytest tests/test_xxx.py -v` | 运行指定测试文件 |
| `pytest -k test_name -v` | 按名称匹配运行测试 |
| `pytest --cov=app` | 测试并生成覆盖率 |
| `pytest --runxfail` | 运行所有测试（含标记为xfail的） |
| `pytest tests/test_e2e_full_link.py -k "f01 or f03" -v --runxfail` | 指定E2E测试运行 |
</details>

不激活时，每条命令加 `.venv\Scripts\` 前缀：

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload
.venv\Scripts\pytest -k test_name -v
```
</details>

<details>
<summary><b>全局 Python</b></summary>

| 命令 | 说明 |
|------|------|
| `python -m uvicorn app.main:app --reload` | 启动开发服务器 |
| `pytest` | 运行全部测试 |
| `pytest tests/test_xxx.py -v` | 运行指定测试文件 |
| `pytest -k test_name -v` | 按名称匹配运行测试 |
| `pytest --cov=app` | 测试并生成覆盖率 |
| `pytest --runxfail` | 运行所有测试（含标记为xfail的） |
| `pytest tests/test_e2e_full_link.py -k "f01 or f03" -v --runxfail` | 指定E2E测试运行 |
</details>

### 前端

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 生产构建 |
| `npm run test` | 运行单元测试 |
| `npm run test:coverage` | 测试覆盖率 |
| `npm run lint` | ESLint 检查 |
| `npm run lint:fix` | 自动修复 ESLint 问题 |
| `npm run format` | Prettier 格式化 |
| `npm run test:e2e` | Playwright E2E 测试 |

---

## 八、数据库

| 数据库 | 路径 | 用途 |
|--------|------|------|
| 聊天历史 | `~/.omniagent/chat_history.db` | 会话与消息 |
| 操作记录 | `~/.omniagent/operations.db` | 文件操作记录/回滚（L3） |
| 任务追踪 | `~/.omniagent/task_tracker.db` | 任务状态与暂停/取消/恢复 |

---

## 九、版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **v0.19.14** | 2026-08-13 | A1-A7 架构分层重构完成 + 35 项核查修复全部落地：safety 提升顶层 app/safety + tools/security hooks 协议、api/v1 薄壳化（CRUD 下沉 service）、stream_orchestrator 编排、tool_facade 门面、tool_loader/tool_retry_engine 归位；操作并发竞态修复（cleanup 加锁幂等）；全量测试通过 - 小欧/小沈-2026-08-13 |
| **v0.19.13** | 2026-08-12 | 架构分层违规方案落地（A1 安全 hooks/迁移、A2 回滚统计下沉、A3 retry_engine 归位、A5 error_hints 拆分、A7 编排下沉）；僵尸常量清理（ERR_* 239→102） - 小欧/小沈-2026-08-12 |
| **v0.19.6** | 2026-08-12 | 架构分层违规问题分析（7 项）+ 修复实施方案（A1-A7 分阶段）；SSRF 重定向拦截统一；e2e_helpers 记录误判修复 - 小欧-2026-08-12 |
| **v0.19.3** | 2026-08-04 | 修复工程全量对齐 final：L0基础层/L1工具链/L2 agent/L3 API 分批同步；migrate_steps 恢复；delete_safety R1-R6 删除安全判定+系统盘符动态化；死代码清理 |
| **v0.19.0** | 2026-08-03 | 基于 final_backend_app 的修复工程批次0-4完成：services 40+文件/constants/工具链恢复至 repair-code 并应用 live backend，恢复 syntax_validator 语法护栏与全部工具注册 |
| **v0.18.39** | 2026-07-30 | 后端卡死根因修复（CMD管道超时+DB休眠不阻塞+SSE cond超时）；shell_engine Singleton→ShellPoolManager 分池并发；desktop schema 坐标/参数整改 |
| **v0.18.35** | 2026-07-28 | Shell 命令执行自 SHELL 迁入 FUNDAMENTAL（SHELL 仅保留 which）；timeadd/timediff/calendar 迁入 TIMER；系统级常量收敛至 app.constants |
| **v0.18.31** | 2026-07-25 | operation_executor/recorder 三段式改造彻底解决并行 delete database is locked；工具输出截断归一化(OUTLIMIT_*)；URL 非ASCII自动转码 |
| **v0.18.30** | 2026-07-23 | 工具输出截断治理（grep/xlsx/shell）；accumulated_usage 累积消耗报告；前端 WarningBox 渲染 warning 字段 |
| **v0.18.14** | 2026-07-12 | README架构章节据代码现状重写：63工具10分类、UniversalAgent单一实现(移除AgentFactory)、架构图与现状偏差(2.3)如实标注(无独立网关/认证/RBAC/限流/任务队列/Redis/桌面移动端)、项目结构路径修正 - 小欧-2026-07-12 |
| **v0.15.9** | 2026-06-12 | CRSS关键词修复(txt/md/json→FILE)、write_text_file参数text→content统一、JSON混合提取容错、safety stub→真实file_safety委托(禁止向后兼容+复用优先)、validate_config SLAP/DRY修复、version.txt空行跳过、P1 E2E测试 14/14通过(xfail清零)、README全面内容更新 |
| **v0.15.8** | 2026-06-11 | 四层安全体系修复（P0平行调用丢失+P1字段重复+P2 fc_context共用） |
| v0.13.46 | 2026-05-25 | feature/prompt-optimization 全量变更合并 |
| v0.13.11 | 2026-05-20 | Agent架构重构设计文档；README全面更新 |
| v0.13.0 | 2026-05-18 | ToolCategory从13类精简为7类 |
| v0.9.0 | 2026-03 | ReAct架构正式上线 |

详细变更记录见 `version.txt`

---

## 十、故障排除

| 问题 | 解决方案 |
|------|---------|
| 后端启动失败 | 检查 Python ≥ 3.11，端口8000是否被占用 |
| 前端启动失败 | 检查 Node.js ≥ 18，清除 node_modules 后重装 |
| API连接失败 | 检查 config.yaml 中的 API 密钥是否有效 |
| 二级工具不可用 | 安装对应依赖库（见6.3节可选依赖） |

---

## 十一、团队成员

| 角色 | 名称 | 职责 |
|------|------|------|
| 产品负责人 | 北京老陈 | 需求决策、质量把控 |
| 后端开发 | 小沈 | 架构设计、后端实现、工具开发 |
| 后端审查 | 小健 | 代码审查、测试、风险分析 |
| 前端开发 | 小强 | 前端实现、UI/UE设计 |
| 前端审查 | 小资 | 前端代码检查、测试 |
| 风险分析 | 老杨 | 安全审查、疑难诊断 |
| 需求分析 | 小许 | 需求文档、规格说明 |

---

**许可**: 内部项目 | **最后更新**: 2026-08-13 16:53:24 | **版本**: v0.19.14
