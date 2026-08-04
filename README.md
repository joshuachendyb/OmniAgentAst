# OmniAgentAs-desk

> 基于 ReAct 架构的 AI 桌面智能体全栈 Web 应用（React + FastAPI），提供 Windows 桌面自动化能力（非独立桌面客户端）

**版本**: v0.19.3 | **更新时间**: 2026-08-04 20:47:37 | **作者**: 北京老陈团队 | **更新人**: 小欧-2026-08-04

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
| **数据库** | SQLite（aiosqlite + SQLAlchemy，默认）；支持 PostgreSQL/MySQL 连接类型抽象 | — |
| **任务执行** | 请求内流式（SSE），`run_react_cycle` 单请求驱动；无独立任务队列/Redis | — |
| **测试** | pytest / Vitest / Playwright | — |

### 2.2 当前架构图（代码实际，v0.19.3）

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
│              后端 (FastAPI，单进程，无独立网关)            │
│  ┌─────────────┐  ┌──────────────────────────────────┐  │
│  │ ChatRouter  │  │  UniversalAgent (BaseAgent 子类)  │  │
│  │  /api/v1/   │  │   └─ run_react_cycle (ReAct 循环) │  │
│  └──────┬──────┘  └──────────────┬───────────────────┘  │
│         │                        │                      │
│  ┌──────┴────────────────────────┴───────────────────┐  │
│  │  ToolRegistry(单例) ── 10分类63工具               │  │
│  │  Safety 四层：开关→安全级→已知风险→safety    │  │
│  │  LLM 客户端(httpx, 多Provider)                    │  │
│  └────────────────────────────────────────────────────┘  │
│  数据层：SQLite(chat_history.db/operations.db)+多库抽象    │
└─────────────────────────────────────────────────────────┘
```

> 说明：FastAPI 直接对外提供 REST/SSE，未独立出「网关层（认证/权限/限流）」微服务；任务在单次请求内由 `run_react_cycle` 流式执行，无独立任务队列。详见 2.3。


---

### 2.3 架构现状与常见目标架构的偏差

> 下表基于 v0.19.3 代码实际核查（grep + 运行时 registry 加载），如实标注与「网关认证/权限/限流 + 任务队列 + Redis + 多端接入」理想架构的差异。

| 维度 | 现状（代码实际） | 与理想架构差异 |
|------|----------------|---------------|
| 接入端 | 仅 React Web App（`frontend/`）+ FastAPI REST API（`api/v1/`） | ❌ 无独立桌面客户端、无移动端 |
| API 网关 | FastAPI 直接对外，无独立 Gateway 微服务 | ❌ 未独立成层 |
| 用户认证 | 仅 HITL 人工确认（`action_handler.authorization_required`）+ 敏感字段脱敏 | ❌ 无用户登录/鉴权体系 |
| 权限 | 工具/文件路径级校验（`file_path_checker`/`registry_path_checker`） | ❌ 无用户级 RBAC |
| 限流 | 仅 LLM 429 限流检测（`SystemErrorClassifier` 识别 HTTP 429） | ❌ 无请求级/IP 限流 |
| 日志 | 有（`app/logger/`） | ✅ |
| 任务队列 | 无 Redis/Celery/RQ；任务在单次请求内流式执行（`chat/stream.py`→`run_react_cycle`），由 `task_tracker` 做暂停/取消/恢复 | ❌ 无独立任务队列服务 |
| 缓存 | 无 | ❌ 无 Redis 缓存 |
| Agent 执行 | `UniversalAgent` + `run_react_cycle`（ReAct 循环） | ✅ |
| 工具注册 | `ToolRegistry` 单例 + `ensure_tools_registered()`，10 分类 63 工具 | ✅ |
| 数据存储 | SQLite（`chat_history.db`/`operations.db`），支持 PostgreSQL/MySQL 连接抽象 | ✅（默认 SQLite） |

**结论**：系统为「单进程 FastAPI + React Web + ReAct Agent + 工具注册表 + SQLite」的紧凑架构，并非带独立网关、任务队列、Redis 的多层分布式架构。

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

> **注**：分类与数量以 `backend/app/tools/tool_constants.py` 的 `CATEGORY_MODULES` + 运行时 `ensure_tools_registered()` 为准（上述为 v0.19.3 实际加载值）。v0.18.35 起 Shell 命令执行迁入 FUNDAMENTAL（`execute_shell_command` 注册为 `shell` 工具），SHELL 分类仅保留 `which`；timeadd/timediff/calendar 自 FUNDAMENTAL 迁入 TIMER。`validate/` 为校验层（路径/URL/超时/注册表），不计入对外工具。

### 3.2 工具注册架构

```
backend/app/tools/
├── registry.py              # ToolRegistry 单例 + 装饰器 register_tool
├── tool_types.py            # ToolCategory 枚举 / ToolMetadata
├── tool_constants.py        # CATEGORY_MODULES（分类→模块/注册函数映射）
├── tool_aliases.py          # 工具别名映射
├── toolhelper/              # 工具辅助
├── validate/                # 校验层（路径/URL/超时/注册表，非对外工具）
├── file/                    # 文件操作（14）
├── shell/                   # 命令查找 which（1）
├── network/                 # 网络通信（5）
├── system/                 # 系统计划任务/事件日志（4）
├── desktop/                # 桌面操作（11）
├── document/               # 文档处理（8）
├── dataanalysis/            # 数据分析（6）
├── fundamental/             # 基础能力（5，含 Shell 命令执行）
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


---

## 四、Agent体系

### 4.1 当前架构（BaseAgent + 单一 UniversalAgent）

```
BaseAgent(ABC)                 ← 抽象基类，含 run_react_cycle 编排钩子
    ↓ 继承
UniversalAgent(BaseAgent)      ← 唯一实现类，配置驱动（意图/模型/工具集由 config 决定）
```

> 代码实际（`backend/app/services/agent/`）：仅 `base_agent.py` 的 `BaseAgent(ABC)` 与 `universal_agent.py` 的 `UniversalAgent(BaseAgent)` 两个类，**无 AgentFactory、无 UniversalReactAgent/DesktopReactAgent 分发**。所有意图类型统一进入 `UniversalAgent.run_react_cycle` 完成 ReAct 循环。
### 4.2 意图分发（现状）

原设计的 `AgentFactory` 多类分发已移除。当前流程：请求经 `ChatRouter` → 意图识别（CRSS 正则 + LLM 兜底）→ 统一构造 `UniversalAgent` 并调用 `run_react_cycle`。意图类型只影响系统 Prompt 与工具集装配，不影响 Agent 类的选择。

### 4.3 安全体系（v0.19.3）

| 层 | 模块 | 职责 |
|---|------|------|
| L0 | config.yaml security.enabled | 全局开关，关闭后跳过所有安全检查 |
| L1 | ToolSafetyLevel(read_only/safe/destructive/dangerous) | 工具声明式安全级别 |
| L2 | ToolSafetyChecker._check_known_risks | 运行时已知风险检测：路径越权/写入污染/代码注入/删除安全判定(delete_safety R1-R6) |
| L3 | safety.operation_record.execute_with_safety | DB事务编排：操作记录写入→状态追踪→备份→文件hash→审计 |
| L3 | safety.operation_record.record_operation | 操作记录持久化(operations.db)，支持回滚 |

> L3 层在 v0.15.9 从空壳 stub（仅生成 UUID）重构为真实 file_safety 委托，恢复完整的 DB 事务编排和回滚能力；v0.19.3 已拍平为 `app/services/safety/`（`operation_record`/`operation_backup`/`operation_rollback`/`operation_cleanup`/`hash_helper`/`delete_safety`/`path_safe_check`），并新增删除确认策略矩阵 R1-R6 与系统盘符动态化（`get_existing_drives`）。

### 4.4 Agent 2.0（规划中）

| 模块 | 状态 | 说明 |
|------|------|------|
| SemanticRouter | 设计中 | LLM语义路由，替代CRSS正则匹配 |
| ToolSafetyLayer | 设计中 | 工具声明式安全分级 |
| ToolObserver | 设计中 | 全量审计日志 + 异常检测 |
| HITL | 已实现 | DANGEROUS 工具人机协同确认已落地（`action_handler.authorization_required` + `wait_for_confirmation_result` + `hitl_confirmation.py`） |

> 统一Agent（BaseAgent → UniversalAgent）已在 v0.14.0 完成，详见 `doc-agent2.0/`。HITL 确认机制在 v0.18.x 已接入。

---

## 五、项目结构

```
OmniAgentAs-desk/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 端点（ChatRouter 等）
│   │   ├── db/                 # SQLAlchemy + Pydantic 模型（chat/operation）
│   │   ├── logger/             # 日志配置
│   │   ├── tools/              # 工具函数（10分类63工具，含 validate 校验层）
│   │   ├── services/
│   │   │   ├── agent/          # Agent体系（base_agent + universal_agent + react_cycle + handlers + steps）
│   │   │   ├── chat/           # 对话编排（stream / handlers / storage / migrate_steps）
│   │   │   ├── lifecycle/      # 生命周期管理
│   │   │   ├── llm/            # LLM 客户端（httpx 多Provider）
│   │   │   ├── model/          # 模型解析/持久化
│   │   │   ├── monitoring/     # 监控（middleware / collector）
│   │   │   ├── prompts/        # 系统提示词适配
│   │   │   ├── safety/         # 安全检查（tool_safety_checker / operation_record 等）
│   │   │   ├── task/           # 任务追踪（task_tracker / pause/cancel/resume / hitl_confirmation）
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
├── doc-agent2.0/               # Agent 2.0架构重构设计文档
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

| 数据库 | 路径 |
|--------|------|
| 聊天历史 | `~/.omniagent/chat_history.db` |

---

## 九、版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
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

**许可**: 内部项目 | **最后更新**: 2026-08-04 20:47:37 | **版本**: v0.19.3
