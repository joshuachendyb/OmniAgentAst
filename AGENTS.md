# AGENTS.md - OmniAgentAs-desk


### 1.1 头条铁规：分析问题、写文档、注释、commit规则，升级tag
**系统**：本机是Windows系统，必须使用Windows系统命令。杜绝使用Linux命令
**写文档签名规则**：（1）文档名称 +签名+时间； （2）内容签名： 编写人 或者 更新人 + 签名  （3）编辑型文档， 禁止删除历史版本。
**代码注释规则**：必须 加署名+日期
**commit标题的规则**:   commit标题必须加：文件名+ 签名+日期

**升级tag**：1..在version.txt文件头部插入从上一个tag以来的所有commit的变更信息，2.打 tag


**严禁** 用PowerShell 来操作代码编辑\替换,否则导致代码编码错误
---

## 编码铁规（必须遵守）--10大原则 — 日常6条 + 重构再加4条

**适用范围**: 所有代码文件

**日常编码必须遵守以下 6 条**：

| 原则 | 说明 | 违反后果 |
|------|------|---------|
| **SRP** — 单一职责 | 一个类/模块/函数只做一件事 | 改了 A 影响 B |
| **DRY** — 不重复 | 相同逻辑只写一次，抽取共用 | 改了 A 漏了 B |
| **KISS-DIRECT** — 简单直接 | 设计简单 + 逻辑直线，不提前引入抽象，不七绕八绕 | 代码绕来绕去看不懂、数据流混乱 |
| **SLAP** — 同一抽象层 | 一个函数不混搭高层编排和底层细节 | 读代码像读天书 |
| **YAGNI** — 不要过度设计 | 不加用不上的接口/模式/抽象 | 废弃代码越积越多 |
| **禁止backward** | 所有代码修改/更新/重构坚决杜绝向后兼容做法 | 新旧混杂、代码混乱 |

**KISS-DIRECT（简单直接原则）详细说明**：

| 要求 | 反例（七绕八绕） | 正例（直线） |
|------|-----------------|-------------|
| 设计简单 | 为了"可扩展"引入注册表，实际只有2个entry | if/elif直接分派 |
| 逻辑直线 | A→B→C→D→E，中间B/C/D只透传 | A→E直接传递 |
| 调用链直接 | `a().b().c().d().e()` 5层链式调用 | 直接调用核心函数 |
| 无中间变量 | `x=f(); y=g(x); z=h(y); return z` | `return h(g(f()))` |
| 无跳来跳去 | A调B，B调C，C回调A | 单向调用，无循环依赖 |
| 无双重解析 | dict→JSON字符串→parse→dict | 直接用dict |
| 无透传函数 | `def f(x): return g(x)` 只调一个函数 | 内联，直接调g |
| 无中间层 | 3层函数每层只调下一层 | 合并为1层 |
| 无注册表滥用 | 2-entry的OrderedDict注册表 | if/elif直接分派 |

**代码重构/框架设计时，在上述 6 条基础上再遵守以下 4 条**：

| 原则 | 说明 | 适用场景 |
|------|------|---------|
| **OCP** — 开闭原则 | 对扩展开放，对修改封闭 | 库/框架/公共组件设计 |
| **LSP** — 里氏替换 | 子类不违反父类约定 | 继承体系 |
| **ISP** — 接口隔离 | 接口职责单一，不塞入不相关方法 | 多实现/插件系统 |
| **复用优先** | 有公用则复用，能够公用的则新建并入库 | 新增函数前必须先查FUNCTIONS.md，禁止局部重造轮子 |

### 违反后果
上述原则是必须遵守的编码纪律。违反者代码被打回重写，直到符合原则为止。

### 公用函数规范（必须遵守）

| 规则 | 说明 |
|------|------|
| **先查后建** | 写代码前先查`app/utils/FUNCTIONS.md`清单，有则复用，无则新建 |
| **分层存放** | 全局层`app/utils/`、Agent层`agent_utils/`、工具层`toolhelper/` |
| **禁止重复** | 相同逻辑禁止重复实现，必须使用已有公用函数 |
| **及时更新** | 新建公用函数后必须添加到FUNCTIONS.md清单 |

### 拆分\重构代码方法**规范（必须遵守）
**核心心原则**：能复制就复制，不重写
**拆分大文件/函数时** 最安全的做法是**复制原代码逻辑，只改导入路径，不改业务逻辑**。重写会引入新错误，复制能保证行为不变。
---

## System & Platform

- **OS**: Windows only. Use PowerShell. No Linux/macOS commands.
- **Shell**: PowerShell 7+. Use `Select-String` instead of `grep`.
- **Python**: 3.13 at `E:\Appsw\python31311\`

---

## Commands

### Backend (workdir=`backend/`)

```bash
python -m uvicorn app.main:app --reload          # dev server (port 8000)
pytest                                            # all tests
pytest -x --tb=short                              # fast fail
pytest -k test_name                               # match by name
```

### Frontend (workdir=`frontend/`)

```bash
npm run dev          # Vite dev server (port 5173)
npm run test         # Vitest
npm run test -- --run <name>  # single test
npm run lint         # ESLint
npm run format:check # Prettier
npm run check        # lint + format:check (run before commit)
npm run test:e2e     # Playwright
```

---

## Architecture (Current)

### Backend: `backend/app/main.py` → FastAPI

**Request flow**: `chat_router.py` → CRSS regex scoring → `AgentFactory.create(intent_type)` → Agent subclasses → ReAct loop → SSE

**Agent system** (`backend/app/services/agent/`):
- `core_agent/` — `react_cycle.py`(循环调度), `handlers/`(action/answer处理), `initialize_run_state.py`
- `agent_utils/` — Agent层公共函数(message_utils, fc_message_types)
- `steps/` — Step类型定义(ThoughtStep, ToolStep, FinalStep等)
- `types/` — AgentStatus枚举, ObservationContext等

**Tool registry** (`backend/app/services/tools/`):
- `registry.py` — `ToolRegistry` singleton, `ToolCategory` enum
- `__init__.py` — `ensure_tools_registered()` loads all tools
- Categories: `file`, `shell`, `network`, `system`, `desktop`, `document`, `meta`, `win_registry`
- Each `{category}/` has: `{category}_register.py`, `{category}_tools.py`, `{category}_schema.py` (+ optional extras)

**LLM client** (`backend/app/services/llm/`):
- `client_sdk.py` — LLMClient(httpx封装)
- `core.py` — BaseAIService(基类)
- `stream_parser.py` — 流式响应解析

**Safety** (`backend/app/services/safety/`):
- `tool_safety_checker.py` — 工具执行前安全检查
- `file_safety/` — 文件操作安全(备份/回滚/查询)

**Prompt logging**: `backend/logs/prompt-logs/`

### Frontend: `frontend/src/main.tsx` → Vite+React

- `src/pages/` — page components
- `src/stores/` — state stores
- `src/services/` — API layer
- `src/utils/` — formatters, step rendering, SSE handling

---

## Project Structure

```
OmniAgentAs-desk/
├── backend/
│   ├── app/
│   │   ├── api/v1/             # REST endpoints
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── config.py           # YAML+env config loader
│   │   ├── db/models/          # SQLAlchemy + Pydantic
│   │   ├── services/
│   │   │   ├── agent/          # core_agent/, agent_utils/, steps/, types/
│   │   │   ├── tools/          # Tool categories (file/shell/network/...)
│   │   │   ├── llm/            # LLM client (client_sdk.py, core.py, stream_parser.py)
│   │   │   ├── safety/         # file_safety/, tool_safety_checker.py
│   │   │   ├── task/           # task_tracker.py, task_control.py
│   │   │   └── react_sse_wrapper/  # run_sse_stream.py, chat_stream.py
│   │   └── utils/              # 公共工具函数
│   ├── tests/                  # pytest
│   └── ~/.omniagent/           # SQLite DBs (chat_history.db, operations.db)
├── frontend/
│   ├── src/
│   └── package.json
├── config/                     # YAML configs
├── doc/                        # design docs
├── notes/                      # debug notes
├── version.txt                 # append-only version history
└── AGENTS.md
```

---

## Key Dependencies

| Layer | Tech | Notes |
|-------|------|-------|
| Backend | FastAPI, Uvicorn, SQLAlchemy, aiosqlite | SQLite `~/.omniagent/chat_history.db` |
| | **httpx==0.26.0, httpcore==1.0.1** | **LOCKED** — 0.28.1 breaks TLS |
| | Pydantic v2 | Tool schemas |
| Frontend | React 18, TypeScript 5, Vite | |
| | Ant Design 5, Axios, React Router | |
| | Vitest, Playwright, ESLint, Prettier | |

**Server URLs**: Backend `http://127.0.0.1:8000` | API docs `http://127.0.0.1:8000/docs` | Frontend `http://localhost:5173`

---

## Known Pitfalls

| Pitfall | Detail |
|---------|--------|
| **httpx version lock** | `httpx==0.26.0` + `httpcore==1.0.1` required. Don't upgrade. |
| **Duplicate `__all__`** | Register files may have 2 `__all__` defs (second overwrites first). |
| **`parsers/` is deprecated** | All files in `agent/parsers/` marked @deprecated. Use `react_output_parser.py` chain instead. |
| **Tool impl vs registration** | Functions in `{cat}_tools.py`, registration in `{cat}_register.py`. Don't confuse them. |
| **`_loaded_categories`** | Per-agent set for tool loading. Initialized to `{current_category, support_tool}`. |
| **`check_date` renamed to `query_calendar`** | Old name no longer exists. |

---

## Git Workflow

```bash
# Commit format: <type>: <description> - <签名>-<日期>
# types: feat/fix/refactor/perf/test/docs

# Tag (PATCH only without asking):
# 1. Insert commit summary into version.txt (project root, append at top)
# 2. git tag v{major}.{minor}.{patch+1}
```

`version.txt` is append-only, oldest at bottom.

---## Code Conventions

### Python
- snake_case functions/vars, PascalCase classes, UPPER_SNAKE_CASE constants
- Type hints required; use `Optional[X]` (not `X | None`)
- Tools return `{code, data, message}` structured responses
- Comments: must include author + date

### TypeScript/React
- PascalCase components, camelCase functions/vars
- kebab-case filenames (`my-component.tsx`)
- No default exports for components
- Use `@/` alias for absolute imports
- Run `npm run check` before commit
