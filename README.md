# OmniAgentAs-desk

> 基于 ReAct 架构的 AI 桌面智能体全栈 Web 应用（React + FastAPI），提供 Windows 桌面自动化能力（非独立桌面客户端）

**版本**: v0.19.40.12 | **更新时间**: 2026-09-13 08:16:15 | **作者**: 北京老陈团队 | **更新人**: 小欧-2026-09-13

---

## 一、项目概述

基于 **ReAct（Reasoning + Acting）** 架构的 AI 桌面智能体：

| 能力 | 说明 |
|------|------|
| 工具函数 | 63 个，覆盖 file / shell / network / system / desktop / document / dataanalysis / fundamental / win_registry / timer 共 10 类 |
| 推理引擎 | thought → action → observation 循环推理 |
| Agent | 单一 UniversalAgent（BaseAgent 子类，配置驱动） |
| AI Provider | 多模型适配：OpenCode、智谱AI、DeepSeek、Kimi 等 OpenAI 兼容 API |
| 响应方式 | SSE 流式推送，推理过程实时可见 |
| 会话管理 | 历史记录、搜索、标题自动生成、跨会话切换 |
| 安全防护 | 四层体系：全局开关 → 工具安全级别 → 已知风险检测 → 数据库事务编排 |

## 二、技术架构

### 2.1 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 后端 | Python / FastAPI / Uvicorn | 3.13 / ≥0.109.0 / ≥0.27.0 |
| 前端 | React / TypeScript / Vite / Ant Design | 18 / 5 / — / 5 |
| LLM 集成 | 多 Provider 适配层（OpenAI 兼容 API） | — |
| 数据库 | SQLite 原生 `sqlite3`，3 个库：chat_history.db / operations.db / task_tracker.db | — |
| 任务执行 | 请求内流式（SSE），`run_react_cycle` 单请求驱动，无独立任务队列/Redis | — |
| 测试 | pytest / Vitest / Playwright | — |

### 2.2 架构总览

```
前端（React + Vite）：Chat / Settings / Session / Security Alert
        │  SSE 流式 / REST
        ▼
后端 API 薄壳层（FastAPI，单进程，无独立网关）
        │  api/v1：chat / task / execution / health / messages / sessions
        │          config / tool / task-queries / metrics / token-usage
        ▼
编排层（services/chat/stream_orchestrator → run_react_cycle）
        │
        ├── Agent：agent_runner → UniversalAgent + tool_loader
        ├── Tool：tool_executor（统一执行入口），ToolRegistry 10 类 63 工具
        └── LLM 客户端（app/llm，httpx 多 Provider）
        ▼
安全层（app/safety）L0-L3：全局开关 → 安全级别 → 已知风险 → DB 事务编排
        ▼
数据层：SQLite 3 库（chat_history / operations / task_tracker）
```

技术要点：

- FastAPI 直接对外提供 REST/SSE，未独立网关层（认证/权限/限流）
- 任务在单次请求内流式执行，无独立任务队列

### 2.3 依赖分层

backend/app 采用六层单向依赖，上层只依赖下层，禁止反向、双向、环形：

```
api/v1 ──> services ──> safety ──> tools ──> utils / db / logger / config / constants
```

由守护测试 `tests/test_architecture_boundaries.py`（3 条规则）持续强制。

### 2.4 与初始设计蓝图的差距

初始蓝图（`doc-系统初建/OmniAgentAst_系统设计方案.md`）规划了微服务化、网关层、Redis 任务队列、多端接入等形态；当前实现为**单进程紧凑架构**，未落地分布式组件：

| 维度 | 当前实现 | 蓝图规划 | 取舍说明 |
|------|---------|---------|---------|
| 接入端 | 仅 Web（React + FastAPI） | Web/桌面/移动多端 | 暂仅 Web，桌面能力由工具层提供 |
| API 网关 | 无独立 Gateway | 独立网关（JWT+OAuth2+限流） | 单机直接暴露，未拆分微服务 |
| 用户认证 | 仅 HITL 确认 + 敏感字段脱敏 | JWT + OAuth2 登录体系 | 未落地用户体系 |
| 权限 | 工具/文件路径级校验 | 用户级 RBAC | 保留工具级 |
| 限流 | 仅 LLM 429 检测 | 请求级/IP 限流 | 未做请求级 |
| 任务队列 | 无，请求内流式执行 | Celery + Redis | 未引入 Redis |
| 缓存 | 无 | Redis | 未引入 |
| 数据存储 | SQLite 3 库 | PostgreSQL + Redis + MinIO + ES | 单机 SQLite |

以上取舍基于单机/单用户场景，属有意的范围收敛，而非技术债。

---

## 三、工具体系（63个）

### 3.1 工具分类（10 类 63 工具）

| 分类 | 数量 | 说明 |
|------|------|------|
| FILE | 14 | 文件读写、搜索、编辑、归档、树、校验 |
| SHELL | 1 | 命令查找（which） |
| NETWORK | 5 | HTTP 请求、下载、网页抓取、网络诊断、搜索 |
| SYSTEM | 4 | 系统计划任务、事件日志 |
| DESKTOP | 11 | 窗口管理、截屏、剪贴板、键鼠、通知 |
| DOCUMENT | 8 | PDF/Word/Excel/PPT 读写 |
| DATAANALYSIS | 6 | SQL 查询/执行、图表生成、数据筛选/分析 |
| FUNDAMENTAL | 5 | Shell 命令执行、系统信息、时间日期、通知、工具搜索 |
| WIN_REGISTRY | 3 | 注册表读/写/删 |
| TIMER | 6 | 定时器设置/列出/清除、时间计算 |
| 合计 | 63 | |

### 3.2 工具注册架构

```
backend/app/tools/
├── registry.py              # ToolRegistry 单例 + ensure_tools_registered
├── tool_types.py            # ToolCategory 枚举 / ToolMetadata
├── tool_constants.py        # CATEGORY_MODULES（分类→模块映射）
├── tool_aliases.py          # 工具别名映射
├── tool_loader.py           # 按 category 加载（per-agent 集合）
├── toolhelper/              # 工具辅助（错误提示/重试）
├── validate/                # 校验层（路径/URL/超时/注册表，非对外工具）
├── security/                # 安全守卫（非对外工具）
├── file/ shell/ network/ system/ desktop/ document/
├── dataanalysis/ fundamental/ win_registry/ timer/   # 10 个工具分类目录
└── {category}_schema.py     # Pydantic 参数模型（每个分类）
   {category}_register.py    # 注册入口
   {category}_tools.py       # 具体实现
```

## 四、Agent 体系

### 4.1 当前架构

```
BaseAgent(ABC)            ← 抽象基类，含 run_react_cycle 编排钩子
    ↓ 继承
UniversalAgent(BaseAgent) ← 唯一实现类，配置驱动（模型/系统提示词/工具集）
```

请求链路：`api/v1` → `stream_orchestrator.chat_stream_orchestrator` → `agent_runner.run_agent_in_background` → `UniversalAgent.run_react_cycle`。

### 4.2 安全体系

| 层 | 职责 |
|----|------|
| L0 | config.yaml `security.enabled` 全局开关 |
| L1 | 工具安全级别（read_only / safe / destructive / dangerous） |
| L2 | 已知风险检测：路径越权 / 写入污染 / 代码注入 / 删除安全（delete_safety R1-R6） |
| L3 | DB 事务编排：操作记录 → 状态追踪 → 备份 → 文件 hash → 审计（operations.db，支持回滚） |
| hooks | 安全 hooks 协议（ContextVar 注入，NoOpHooks 兜底） |

### 4.3 Agent 2.0（规划中）

| 模块 | 状态 | 说明 |
|------|------|------|
| SemanticRouter | 规划中 | 工具子集推荐器 |
| ToolSafetyLayer | 规划中 | 工具声明式安全分级 |
| ToolObserver | 规划中 | 全量审计日志 + 异常检测 |
| HITL | 已实现 | DANGEROUS 工具人机协同确认 |

---

## 五、项目结构

```
OmniAgentAs-desk/
├── backend/                    # Python FastAPI 后端
│   ├── app/
│   │   ├── api/v1/             # API 薄壳路由（config/chat/task/execution/health/messages/sessions/tool/task-queries/metrics/token-usage）
│   │   ├── db/                 # 数据库（原生 sqlite3 连接：database.py / db_initializer.py / operation_queries.py）
│   │   ├── logger/             # 日志配置
│   │   ├── safety/             # 安全体系（顶层）：operation_record/operation_backup/operation_rollback/operation_maintenance/delete_safety/hash_helper/tool_safety_checker/default_hooks/models
│   │   ├── tools/              # 工具函数（10分类63工具，含 security 安全守卫 + validate 校验层 + toolhelper）
│   │   ├── llm/                # LLM 客户端（httpx 多Provider，顶层能力层）
│   │   ├── monitoring/         # 监控（collector / middleware，顶层能力层）
│   │   ├── services/
│   │   │   ├── agent/          # Agent体系（base_agent + universal_agent + agent_runner + react_loop(react_inference/react_dispatch/react_step) + tool_loader + handlers + steps + compaction）
│   │   │   ├── chat/           # 对话编排（stream_orchestrator 编排 + sse_events + storage + session/message_service + history_loader + migrate_steps）
│   │   │   ├── lifecycle/      # 生命周期管理
│   │   │   ├── model/          # 模型/配置解析（config_service + config_helpers）
│   │   │   ├── prompts/        # 系统提示词适配
│   │   │   ├── task/           # 任务追踪（TaskTracker + task_db/task_state/task_registry/task_runtime，暂停/取消/恢复 / hitl_confirmation）
│   │   │   ├── tool/           # 工具门面（tool_facade）
│   │   │   └── visualization/  # 可视化报告（mermaid/html/tree 等）
│   │   └── utils/
│   ├── config.yaml.example     # 配置模板（复制到 config/config.yaml 后填写）
│   ├── e2etests/               # 端到端测试（P0/P1/P2 全链路）
│   ├── logs/                   # 运行日志
│   ├── migrations/             # DB 迁移
│   ├── scripts/                # 辅助脚本
│   ├── tests/                  # 后端测试（pytest）
│   └── requirements.txt
├── frontend/                   # React + TypeScript 前端（Web App，非桌面/移动端）
│   ├── src/
│   │   ├── features/           # 特性域（chat 全链路 + settings 配置）
│   │   │   ├── chat/           # 聊天特性域（components/hooks/services/sseParser）
│   │   │   └── settings/       # 设置特性域（ProviderSettings/SecuritySettings/GlobalConfigArea 等）
│   │   ├── components/         # 通用 UI 组件（AuthorizationModal / Layout / SecurityAlert 等）
│   │   ├── contexts/           # React Context（AppContext / SecurityContext）
│   │   ├── hooks/              # 顶层 Hook（useSSE / useStateWithRef / useBeforeUnload 等）
│   │   ├── lib/                # 库桥接（antd bridge）
│   │   ├── pages/              # 页面（ChatPage）
│   │   ├── services/           # API 层（api/*.api.ts + error/handler）
│   │   ├── theme/              # 视觉令牌（tokens.ts）
│   │   ├── types/              # TS 类型定义
│   │   ├── constants/          # 前端常量
│   │   └── utils/              # 工具函数（time / stepStyles / sse 处理等）
│   ├── src/tests/              # 前端单元测试（Vitest）
│   ├── tests/                  # Playwright E2E / 性能测量脚本
│   └── package.json
├── config/                     # 配置文件（config.yaml 主配置，已被 Git 忽略）
├── doc-5月优化/                # 5月优化（含 doc-5月agent2.0 架构设计文档，旧称 doc-agent2.0）
├── doc-*/                      # 各月优化/专题设计文档目录
├── doc/                        # 系统设计文档
├── notes/                      # 调试笔记
├── version.txt                 # 版本变更记录（append-only）
└── AGENTS.md                   # 开发规范
```

---

## 六、配置文件说明

### 6.1 配置文件位置

| 文件 | 说明 |
|------|------|
| `config/config.yaml` | 系统主配置（已被 Git 忽略，不含密钥入库） |
| `backend/config.yaml.example` | 配置模板，首次使用时复制到 `config/config.yaml` 后填写 |

默认加载路径为代码库根下 `config/config.yaml`，可用环境变量 `OMNIAGENT_CONFIG_PATH` 覆盖。配置文件缺失时后端会报错并提示手动创建该文件（也可在前端设置页生成）。

### 6.2 配置节总览

| 配置节 | 作用 |
|--------|------|
| `ai` | AI 模型与 Provider（多厂商 OpenAI 兼容 API） |
| `app` | 应用参数（迭代上限、项目根、授权目录、主题等） |
| `logging` | 日志级别与轮转 |
| `security` | 安全开关与过滤策略（L0） |
| `sandbox` | 沙箱预检（工具执行前资源约束） |

### 6.3 `ai` — 模型与 Provider

顶层键：

| 键 | 说明 |
|----|------|
| `ai.provider` | 当前选中的 Provider 名（如 `agnes`） |
| `ai.model` | 全局默认模型 |

每个 Provider 以键名（如 `opencode`、`qiniu`、`zhipuai`）作为一级键，可配置任意多个：

| 键 | 说明 |
|----|------|
| `api_base` | OpenAI 兼容 API 地址 |
| `api_key` | API 密钥 |
| `models` | 可用模型列表 |
| `model_params` | 按模型的补充参数（如 `reasoning_effort`、`context_limit`） |
| `timeout` | 请求超时（秒） |
| `max_retries` | 失败重试次数 |

### 6.4 `app` — 应用配置

| 键 | 说明 |
|----|------|
| `app.debug` | 调试模式（true/false） |
| `app.language` | 界面语言（`zh-CN` / `en-US`） |
| `app.theme` | 主题（`light` / `dark`） |
| `app.max_rounds` | 对话历史保留的轮数上限（默认 100） |
| `app.max_steps` | Agent 单次任务最大迭代步数（默认 10000） |
| `app.max_context_tokens` | LLM 上下文上限（tokens） |
| `app.max_history_length` | 历史消息条数上限 |
| `app.project_root` | 项目根 = tool 工作区；留空回退用户主目录 |
| `app.allowed_dirs` | 项目根之外额外授权的工作目录列表；禁止指向代码库根或其父/子级 |

### 6.5 `logging` — 日志配置

| 键 | 说明 |
|----|------|
| `logging.level` | 日志级别（DEBUG / INFO / WARNING / ERROR） |
| `logging.max_file_size` | 单日志文件大小上限（字节） |
| `logging.backup_count` | 轮转保留文件数 |

### 6.6 `security` — 安全配置

| 键 | 说明 |
|----|------|
| `security.enabled` | 全局安全开关（L0；false=关闭） |
| `security.contentFilterEnabled` / `contentFilterLevel` | 输入内容敏感词过滤，级别 `low` / `medium` / `high` |
| `security.whitelistEnabled` / `commandWhitelist` / `commandBlacklist` | Shell 命令白/黑名单（每行一个命令） |
| `security.confirmDangerousOps` | 危险操作二次确认（HITL） |
| `security.maxFileSize` | 最大文件操作大小（MB） |
| `security.auto_confirm_delay` | 自动确认等待秒数 |
| `security.hitl_timeout` | HITL 确认超时（秒） |
| `security.strict_mode` | 严格模式（true/false） |

### 6.7 `sandbox` — 沙箱预检

| 键 | 说明 |
|----|------|
| `sandbox.enabled` | 总开关；false=完全关闭预检 |
| `sandbox.backend` | 后端实现键（当前唯一 `job_object`） |
| `sandbox.max_concurrent_sandboxes` | 并发预检上限 |
| `sandbox.max_workspace_mb` | 工作区大小上限，超限转 HITL 强确认 |
| `sandbox.max_shadow_mb` | 影子副本单文件上限 |
| `sandbox.process_memory_limit_mb` | Job Object 进程树内存上限 |
| `sandbox.default_timeout_sec` | 预检默认超时（秒） |
| `sandbox.max_timeout_sec` | 预检硬上限（秒） |

### 6.8 环境变量覆盖

| 环境变量 | 覆盖项 |
|----------|--------|
| `{PROVIDER}_API_KEY`（如 `AGNES_API_KEY`） | `ai.<provider>.api_key` |
| `AI_PROVIDER` | `ai.provider` |
| `LOG_LEVEL` | `logging.level` |
| `OMNIAGENT_CONFIG_PATH` | 配置文件路径 |

### 6.9 修改生效方式

保存 `config.yaml` 后立即生效，**无需重启**：`get_config()` 每次调用按文件 mtime 检测，文件变化自动重读，下一工具/LLM 调用即用新值。也可在前端设置页修改（写回 config.yaml 并自动重载）。

---

## 七、快速开始

### 7.1 环境要求

| 依赖 | 版本 | 说明 |
|------|------|------|
| Python | ≥ 3.11 | 测试用 3.13 |
| Node.js | ≥ 18.x | — |
| npm | ≥ 9.0 | — |

> **虚拟环境建议**：Python 后端用虚拟环境隔离依赖，方便清理与复现（推荐）。

### 7.2 安装与启动

后端和前端需**同时运行**，开**两个命令行窗口**。

**窗口 1 — 后端**（`cd backend`）：

```bash
# 方式 A（推荐）：虚拟环境
python -m venv .venv                        # 仅第一次
.venv\Scripts\pip install -r requirements.txt  # 仅第一次
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# 方式 B：全局 Python
pip install -r requirements.txt             # 仅第一次
python -m uvicorn app.main:app --reload --port 8000
```

> 窗口 1 保持运行，不要关闭。

**窗口 2 — 前端**（`cd frontend`）：

```bash
npm install        # 仅第一次
npm run dev
```

> 窗口 2 保持运行，不要关闭。

**浏览器访问**：

| 地址 | 说明 |
|------|------|
| http://localhost:5173 | 前端页面 |
| http://127.0.0.1:8000 | 后端 API |
| http://127.0.0.1:8000/docs | API 交互式文档 |

### 7.3 可选依赖（二级工具）

多数已含于 `requirements.txt`，如需单独安装：

```bash
pip install pandas matplotlib
pip install pdfplumber python-docx openpyxl
pip install pyautogui pywin32 pytesseract Pillow
pip install mss imageio numpy
```

---

## 八、开发命令

### 后端（在 backend/ 目录，虚拟环境需先 `.venv\Scripts\activate`）

| 命令 | 说明 |
|------|------|
| `python -m uvicorn app.main:app --reload` | 启动开发服务器 |
| `pytest` | 运行全部测试 |
| `pytest tests/test_xxx.py -v` | 运行指定测试文件 |
| `pytest -k test_name -v` | 按名称匹配运行测试 |
| `pytest --cov=app` | 测试并生成覆盖率 |
| `pytest --runxfail` | 运行所有测试（含标记为 xfail 的） |
| `pytest tests/test_e2e_full_link.py -k "f01 or f03" -v --runxfail` | 指定 E2E 测试运行 |

### 前端（在 frontend/ 目录）

| 命令 | 说明 |
|------|------|
| `npm run dev` | 启动开发服务器 |
| `npm run build` | 生产构建（tsc + vite build） |
| `npm run test` | 运行单元测试（Vitest） |
| `npm run test:watch` | Vitest 监听模式 |
| `npm run test:coverage` | 测试覆盖率 |
| `npm run test:e2e` | Playwright E2E 测试（先跑 lint + format 检查） |
| `npm run lint` | ESLint 检查 |
| `npm run lint:fix` | 自动修复 ESLint 问题 |
| `npm run format` | Prettier 格式化全部 |
| `npm run format:check` | Prettier 格式检查 |
| `npm run check` | 提交前检查（lint + format:check） |

---

## 九、数据库

| 数据库 | 路径 | 用途 |
|--------|------|------|
| 聊天历史 | `~/.omniagent/chat_history.db` | 会话与消息 |
| 操作记录 | `~/.omniagent/operations.db` | 文件操作记录/回滚（L3） |
| 任务追踪 | `~/.omniagent/task_tracker.db` | 任务状态与暂停/取消/恢复 |

---

## 十、版本变更记录

> 版本变更明细见 `version.txt`（append-only）。

---

## 十一、故障排除

| 问题 | 解决方案 |
|------|---------|
| 后端启动失败 | 检查 Python ≥ 3.11，端口8000是否被占用 |
| 前端启动失败 | 检查 Node.js ≥ 18，清除 node_modules 后重装 |
| API连接失败 | 检查 config/config.yaml 中的 API 密钥是否有效 |
| 二级工具不可用 | 安装对应依赖库（见7.3节可选依赖） |

---

## 十二、团队成员

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

## 十三、E2E 测试

E2E（端到端）用**真实环境**模拟真实用户操作，验证系统全链路：真实后端 + 真实 LLM + 真实工具 + 真实 SQLite + 真实浏览器。目的不是"跑通脚本"，而是**发现问题**。

配套文档与仓库：

| 资产 | 位置 |
|------|------|
| 后端执行手册（用例/铁律/数据结构，v2.11） | `backend/e2etests/全链路E2E测试手册-小健-2026-05-23.md` |
| 后端核心 helper（所有通用逻辑） | `backend/e2etests/e2emodel/e2e_helpers.py` |
| 后端 case 模板（四类） | `backend/e2etests/e2emodel/model-test_e2e_0*.py` |
| 前端 E2E 公共库（POM/进程/诊断） | `frontend/e2e_front_lib/` |
| 前端 UI 全链路用例（断线重连） | `frontend/tests/e2e/reconnect-ui.spec.ts` |

### 13.1 总则与铁律

| 铁律 | 说明 |
|------|------|
| 禁止 Mock | 一律真实后端 + 真实 LLM + 真实工具 + 真实 SQLite，能看到什么测什么 |
| 一次只跑一个 | 写完一个跑通验证后再写下一个；执行时一次一个 case，严禁批量 |
| 测试代码不入提交 | 严禁 commit 任何测试相关的代码文件（按仓库提交规范） |
| 通用逻辑只进公共库 | 逻辑严禁散落 case 脚本（详见 13.3.1） |
| 失败不得跳过 | 任何 FAIL 都要闭环：定位 → 修复 → 复测，禁止跳过 |

### 13.2 后端 E2E：环境与执行流程（4 步）

**第 1 步：重启后端（每次测试前必做）**：

| 操作 | 命令 |
|------|------|
| 杀 8000 旧进程 | `netstat -ano` 查 `:8000` 的 PID → `taskkill /F /PID <PID>` |
| 独立窗口启动 | `Start-Process powershell -ArgumentList "-NoExit","-Command","cd 'backend'; python -m uvicorn app.main:app --reload --reload-dir app --host 0.0.0.0 --port 8000" -WindowStyle Normal` |
| 验证就绪 | `Invoke-RestMethod http://127.0.0.1:8000/api/v1/health` 返回 `healthy` |

后端必须用**独立 PowerShell 窗口**启动（不走 OpenCode 的 bash 工具，避免日志混扰）；必须 `--reload`，修 Bug 后热重载免重启。

**第 2 步：编写用例**：一次只写一个（编写规范见 13.3）。

**第 3 步：执行脚本**：真实 LLM 单次调用常超 120s，**必须 `subprocess.Popen` 后台跑**（命令行直接 pytest 会被 bash 工具 120s 强杀整棵进程树，pytest 自身 timeout=3000 来不及生效）：

```
python -c "import subprocess; p=subprocess.Popen(['python','-m','pytest','tests/XXX.py','-x','--tb=long','-v','--timeout=2900','--junitxml=tests/output/YYY_result.xml'],stdout=open('tests/output/YYY_stdout.txt','w'),stderr=open('tests/output/YYY_stderr.txt','w'),cwd='backend'); print('PID:',p.pid)"
```

此后：轮询 Popen 的 PID 是否存活 → 读 `YYY_stdout.txt` / `YYY_stderr.txt` → 查 `YYY_result.xml`。**严禁再给启动脚本另设超时**。

**第 4 步：手动检查（3 项全过才算完成，检查结果追加到测试记录尾部才进下一个 case）**：

| 验证项 | 检查内容 |
|--------|---------|
| ① 代码错误/异常（最高优先级） | 日志 traceback/ERROR、SSE error 事件 → 有则立即停，走修复 |
| ② 调用链分析 | 工具选择/顺序、LLM 调用次数是否合理，输出 `[CALL CHAIN]` |
| ③ 参数正确性 | tool_params 中路径/关键词是否正确 |

### 13.3 后端 E2E：case 编写（重点）

#### 13.3.1 职责分层（核心原则）

| 层 | 文件 | 职责 |
|----|------|------|
| 核心脚本 | `e2e_helpers.py` | 全部通用逻辑：计时、SSE 流接收与解析、DB 校验、日志检查、测试记录写入、PASS/FAIL 判定 |
| case 脚本 | `backend/tests/test_e2e_*.py` | 只做三件事：① 组装参数（用户输入/断言条件）② 调用核心函数 ③ 断言验证 |

**通用逻辑严禁散落 case 脚本**：历史教训——19 个 case 曾各自复制粘贴"取数块"，协议一变（action_tool→action）全部碎裂；现统一收敛到 `verify_db_tool_usage()` 等公共函数单点维护。

#### 13.3.2 模板选型（backend/e2etests/e2emodel/，复制改场景，不重写框架）

| 模板 | 适用场景 | 验证重点 |
|------|---------|---------|
| A — 无工具调用 | 自我介绍、问答 | 收到 final、无 error、DB 有记录 |
| B — 单工具调用 | 创建/读取文件 | SSE 含 action 事件 + tool_calls |
| C — 多步推理 | 先读文件再回复 | 多 step 记录 + observation 存在 |
| D — 数据持久化 | 目录列表等 | DB 三表完整 + steps 字段完整 |

#### 13.3.3 脚本骨架（结构固定，只改业务）

```
"""用例头注释（手册第4章）：编号/用户输入/前置数据/预期调用链/通过标准/失败标准 + 铁律"""
@pytest.mark.e2e_full_link
@pytest.mark.asyncio
async def test_e2e_p0_xx_xxx():
    test_start = datetime.now()
    passed = False; r = None; sid = None; db = {}; ci = []; si = []; lc = {"errors": [], "tracebacks": []}
    elapsed = 0.0; error_info = None
    user_input = "..."          # 真实用户语句，LLM 看到什么就发什么

    try:
        register_pending_record("E2E-P0-xx", "场景名", user_input, {}, {}, [], [], lc, False)
        assert ensure_backend_ready(), "后端未启动(手册6.1)"
        r = await send_chat(user_input)          # POST /chat/stream → 收 SSE → 解析
        sid = r["session_id"]; elapsed = r["total_time_ms"] / 1000.0

        assert_stream_ended(r)                   # 结束方式: completed/failed/cancelled/error/中断
        assert r["total_steps"] >= 2, "至少 start+final (MUST)"
        assert r["unique_step_numbers"] < 300, f"疑似死循环 (MUST)"

        db = check_db(sid)                       # 三表完整性 + step 字段
        assert db["session_exists"] and db["is_valid"], "(MUST)"
        assert db["has_user_message"] and db["has_assistant_message"], "(MUST)"
        assert len(db["step_field_issues"]) == 0, "(MUST)"

        ci = verify_consistency(r, sid)          # SSE vs DB 一致性
        assert len(ci) == 0, f"(MUST): {ci}"
        si = verify_steps(r, sid)                # 步骤编号递增 + observation
        assert len(si) == 0, f"{si}"

        lc = check_logs(test_start, sid)         # ERROR/traceback 扫描
        assert len(lc["errors"]) == 0, "(MUST)"
        assert len(lc["tracebacks"]) == 0, "(MUST)"

        print_report("E2E-P0-xx", "场景名", r, db, lc, ci, si, True, elapsed,
                     extra={"LLM calls": r["llm_call_count"], "SSE total": r["total_steps"]})
        passed = True
    except Exception as e:
        passed = False; error_info = f"{type(e).__name__}: {e}"; raise
    finally:
        write_test_record("E2E-P0-xx", "场景名", user_input,
                          r or {}, db, ci, si, lc, passed, elapsed, error_info=error_info)
```

#### 13.3.4 send_chat 返回值（写断言前必读）

| 字段 | 含义 | 断言用途 |
|------|------|---------|
| `session_id` | 本次会话 ID | 传给 check_db / verify_consistency |
| `total_steps` | SSE 事件总数（含 chunk） | 至少 start+final |
| `unique_step_numbers` | 唯一步号数 | `<300` 防死循环 |
| `has_error` | SSE 出现 error 事件 | 终态判定辅助 |
| `final_event.outcome` | 终态 completed/failed/cancelled | `assert_stream_ended` 依据（FinalStep 多态，失败不再发 error 事件） |
| `llm_call_count` | 真实 LLM 调用次数 = usage 事件数 | 调用链合理性 |
| `tool_calls` | 工具调用（action.tools[] 规整，**preview 已过滤**） | SSE vs DB 一致性 |
| `response_text` | 最后一轮非推理 chunk 拼接（空则回退 final.response） | 回复语义断言 |
| `total_time_ms` | 全程耗时 | 响应时间 SHOULD |

注意：`llm_call_count` 是 usage 事件数（每次 LLM 完成必带一个），**不是** `len(tool_calls)+1`（历史误区，批量工具会翻倍）；`preview=true` 的 action 是齿轮动画先行、不落库，send_chat 已跳过——防止 SSE=2×DB 一致性误判。

#### 13.3.5 断言分层落地

| 层 | 写法 | 语义 |
|----|------|------|
| MUST | `assert x, "msg (MUST)"` | 必验，失败即 FAIL |
| SHOULD | `if cond: assert ...` | 有偏差但可容忍（如 `session_records_found` 确认性检查） |
| MAY | `if cond: print(...)` | 仅记录，不判定（如回复含错误关键词） |

#### 13.3.6 失败处理闭环

| 类别 | 特征 | 归因路径 |
|------|------|---------|
| A 运行时 | 超时/死循环/SSE 断流丢事件 | 查后端日志 traceback 与 SSE 中断点 |
| B 数据不一致 | session/messages/steps 缺失或顺序错 | SSE vs DB 对比（verify_consistency 输出） |
| C 用例自身 | 断言条件写错/参数不对 | 复盘 USER_INPUT 与断言，修完复测 |

修复按 10 大规范，修复后必须复测同一 case，禁止跳过。

### 13.4 后端 E2E：运行特殊情况

| 特殊情况 | 说明与对策 |
|----------|-----------|
| bash 工具 120s 强杀进程树 | 见 13.2 第 3 步 `subprocess.Popen` 方案 |
| 数据库未隔离 | 复用系统库 `~/.omniagent/chat_history.db`，污染生产数据；用例不删 DB 记录（保留供复盘） |
| 独立测试配置 | 测试用 `E:\test_dir\test_config\config.yaml`（security.enabled=false），不改系统 `config/config.yaml` |
| 测试数据目录 | 读写统一在 `E:\test_dir\`；用例后清理生成文件（报告/zip/新文档） |
| 记录竞态 | 大任务 SSE 结束后后台仍在大体积写库，check_db 内置重试 8 次×2s，勿手动加 sleep |

### 13.5 前端 E2E：case 编写（重点）

前端 E2E = Playwright **真实浏览器**（chromium）+ 真实后端（:8000）+ 真实 LLM + 真实 SQLite。用例 `frontend/tests/e2e/*.spec.ts`，公共库唯一来源 `frontend/e2e_front_lib/`。

#### 13.5.1 架构与断流原理（认识"进程分离"，写断线类 case 的前提）

| 角色 | 进程 | 职责 |
|------|------|------|
| 页面服务 A | vite dev `:5173`（hmr:false） | 永活服务页面，**全程不杀**（页面永不 reload） |
| 后端代理 B | `tests/e2e/api-proxy.ts :9000→8000` | 页面 API/SSE 直连目标（`VITE_API_BASE_URL=http://localhost:9000/api/v1` 注入） |
| 后端 C | uvicorn `:8000` | 内存任务持有者，断流期间任务存活 |

断线 → 重连剧本：`killPort(9000)` 杀 B → 浏览器↔A(5173) 完好、仅 API 链路断，前端 fetch 收到**真实 TCP RST**（真·断线，页面不 reload）→ C 任务后台存活 → 重启 B → 前端退避 `GET /chat/stream/{task_id}?after_seq=lastSeqRef+1` 断点续传。

**为什么必须杀"浏览器直连的进程"**：若经 vite http-proxy 中转，上游 RST 会被代理静默吞掉挂起，前端无感（已实测断不掉）；杀 B = 浏览器直接 RST，fetch 才感知。

**为什么不用 `context.setOffline`**：只拦截新请求，无法中断已建立的 in-flight SSE 流（已实测无效）。

#### 13.5.2 三件套：POM / 进程 / 诊断（一律从 ../../e2e_front_lib 导入）

**页面对象 ChatPage（chat-page.ts，六方法）**：

| 方法 | 行为 |
|------|------|
| `gotoChat()` | 打开聊天首页 |
| `sendPrompt(text)` | 输入并发送（发送后 isReceiving=true，切"停止"按钮） |
| `waitReceiving(90_000)` | 等"停止"按钮 = 流已启动 |
| `waitGreenDot(90_000)` | 等思考帧绿圈 = 实质开流（非强制，等不到 catch） |
| `waitDone(300_000)` | 等"发送"按钮复现 = 流结束 |
| `getFinalText()` | 取页面终态正文 |

**进程/端口 process.ts**：`killPort(port)` 杀 Listen 进程；`startProxyServer(dir)` 起代理 B；`startDevServer(dir, args, env)` 起 npm dev（隐藏窗口，返回 PID）；`waitPortUp/Down(port)` 轮询就绪/释放。

**SSE 诊断 stream-diag.ts**：`attachStreamDiag(page)` 挂 /chat/stream REQ/RES/FAIL + 全 console + reload 探针，返回 `streamReqs/reconnectLogs/sseErrors/consoleAll/allFailed` 五数组；`printDiag(...)` 无条件打全量证据链；`logBaseOf/readLogSince` 日志基线与"本轮新增"读取；`getTodayLogPath(dir)` 当日后端日志 `app_YYYY-MM-DD.log`；`hasAdjacentDup(text)` run-on 检测。

#### 13.5.3 脚本骨架（SOP，只改业务）

```
test.setTimeout(600_000);
const chat = new ChatPage(page);
const { streamReqs, reconnectLogs, sseErrors, consoleAll, allFailed } = attachStreamDiag(page);

// ① 环境就绪: killPort(9000)→waitPortDown→startProxyServer→waitPortUp; 5173 同理(起 vite.e2e.config)
// ② 本轮日志基线 logBase = logBaseOf(BLOG)   ← 只对账本次新增，防命中历史遗留
// ③ await chat.sendPrompt(真实用户语句)
// ④ await chat.waitReceiving(90_000)（失败先 printDiag 再 throw）
// ⑤ await chat.waitGreenDot(90_000)          // 非强制
// ⑥ 断流: killPort(9000) → waitPortDown      // 真进程断开
// ⑦ 断言前端进入重连: 轮询 reconnectLogs 含 "重连"（失败 printDiag + throw）
// ⑧ 恢复: startProxyServer → waitPortUp
// ⑨ await chat.waitDone(300_000)             // 恢复后流结束
// ⑩ 终态断言: expect(hasAdjacentDup(finalText)).toBe(false) + 正文长度
// ⑪ 后端日志对账: readLogSince(BLOG, logBase) 断言重连端点请求 after_seq>0
// ⑫ printDiag(...) 无条件打印全量诊断（供失败归因，不参与断言）
```

#### 13.5.4 关键机制详解

**① 日志对账防假通过（断线/重连类 case 必须）**：前端 console 出现"重连" ≠ 后端真收到重连。`logBaseOf` 记基线 → `readLogSince` 只读"本轮新增" → 断言补点日志 `重连请求接收...after_seq=(\d+)>0`。只对账本轮，防命中历史轮次遗留重连记录。

**② 真进程断流**：断流 = `killPort(9000)` 产生真实 TCP RST；恢复 = 重启 B + `waitPortUp` 轮询。禁 `setOffline`（无法断 in-flight SSE，已实测）。

**③ run-on 检测**：断点续传若重发事件，正文会二次拼接。`hasAdjacentDup` 逐行检测"行内相邻重复"（6~30 步长 3 的滑动窗口）；同一文本行内无换行的连续重复才是拼接特征，跨行重复（表格线/列表）不算。

**④ 诊断挂满+失败即打**：用例开头必 `attachStreamDiag`；任何一步失败先 `printDiag(streamReqs, reconnectLogs, sseErrors, consoleAll, 日志, allFailed)` 打印全量证据链再 throw。`[DIAG]` 输出不参与断言。

**⑤ 状态轮询禁 sleep**：等端口/按钮/console 就绪一律 `expect.poll`（500ms 间隔），断线感知等用带 deadline 的循环轮询；禁止固定 sleep 凑时序。

#### 13.5.5 运行方式

```
npx playwright test reconnect-ui.spec.ts --headed --reporter=line   # 单 case
npm run test:e2e      # 整组（先 lint + format）
```

环境常量（`BACKEND_DIR/FRONTEND_DIR/BLOG`）收拢在 describe 顶部；Windows 专属——进程控制依赖 PowerShell，后端日志路径按日轮转，跨天运行须用当日路径。

---

**许可**: 内部项目 | **最后更新**: 2026-09-13 08:16:15 | **版本**: v0.19.40.12
