# AGENTS.md - OmniAgentAs-desk

> Global rules (roles, timestamps, commit format, versioning, doc style) are in `C:\Users\chend\.config\opencode\AGENTS.md` (auto-loaded).
> This file contains **project-specific** info only.

---

## 1. 编码铁规（必须遵守）

###  1.1 八大原则 — 日常5 + 重构再加3

**日常编码必须遵守以下 5 条**：

| 原则 | 说明 | 违反后果 |
|------|------|---------|
| **SRP** — 单一职责 | 一个类/模块/函数只做一件事 | 改了 A 影响 B |
| **DRY** — 不重复 | 相同逻辑只写一次，抽取共用 | 改了 A 漏了 B |
| **KISS** — 保持简单 | 能简单不复杂，不提前引入抽象 | 代码绕来绕去看不懂 |
| **SLAP** — 同一抽象层 | 一个函数不混搭高层编排和底层细节 | 读代码像读天书 |
| **YAGNI** — 不要过度设计 | 不加用不上的接口/模式/抽象 | 废弃代码越积越多 |

**代码重构/框架设计时，在上述 5 条基础上再遵守以下 3 条**：

| 原则 | 说明 | 适用场景 |
|------|------|---------|
| **OCP** — 开闭原则 | 对扩展开放，对修改封闭 | 库/框架/公共组件设计 |
| **LSP** — 里氏替换 | 子类不违反父类约定 | 继承体系 |
| **ISP** — 接口隔离 | 接口职责单一，不塞入不相关方法 | 多实现/插件系统 |

### 1.2 违反后果
上述原则是必须遵守的编码纪律。违反者代码被打回重写，直到符合原则为止。

### 1.3制度性防护

| # | 措施 | 目的 |
|---|------|------|
|1 | **禁止SKIPPED测试累积** — 任何重构必须同步更新测试，不得标记skip后搁置 | 防止测试腐烂 |
|2 | **重构checklist** — 每次重构前必须：①grep所有调用方 ②检查返回格式一致性 ③检查导入路径 | 防止引入断裂点 |
|3 | **格式铁律** — 所有工具函数返回统一用 `build_success()` / `build_error()`，旧格式函数加`@deprecated`装饰器 | 防止格式分裂 |
|4 | **集成冒烟测试** — 每次提交前运行 `test_execution_chain.py`（chat_router完整链路 + 1个真实工具调用） | 防止验收时崩盘 |
---


## 2 System & Platform

- **OS**: Windows only. Use PowerShell. No Linux/macOS commands.
- **Shell**: PowerShell 7+. Use `Select-String` instead of `grep`.
- **Python**: 3.13 at `E:\Appsw\python31311\`

---

## 3 Commands

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

## 4 Architecture (Current)

### Backend: `backend/app/main.py` → FastAPI

**Request flow**: `chat_router.py` → CRSS regex scoring (stage 1) → LLM classifier fallback (stage 2) → `AgentFactory.create(intent_type)` → Agent subclasses → ReAct loop → SSE

**Agent system** (`backend/app/services/agent/`):
- `base_react.py` — `BaseAgent(ABC)` (ReAct loop core)
- `mixins/react_agent_mixin.py` — `ReactAgentMixin` (tool loading, step management)
- **Agent subclasses**: inherit `ReactAgentMixin, BaseAgent`; each differs in Prompt + Category
- `agent_factory.py` — intent_type → Agent class mapping
- `react_output_parser.py` — LLM response parsing chain
- `parsers/` — **@deprecated**. Use `react_output_parser.py` instead.
- `strategy_selector.py` — LLM strategy: `text` / `response_format` / `tools`

**Tool registry** (`backend/app/services/tools/`):
- `registry.py` — `ToolRegistry` singleton, `ToolCategory` enum
- `__init__.py` — `ensure_tools_registered()` loads all tools
- Categories: `file`, `shell`, `network`, `system`, `desktop`, `document`, `meta`
- Merged categories: TIME→META, ENVIRONMENT→SYSTEM, DATABASE→DOCUMENT, CODE_EXECUTION→SHELL
- Each `{category}/` has: `{category}_register.py`, `{category}_tools.py`, `{category}_schema.py` (+ optional extras)

**Safety**: `command_security.py` (at `services/`, not `safety/`) — blacklist-based command safety check

**Prompt logging**: `backend/logs/prompt-logs/`

### Frontend: `frontend/src/main.tsx` → Vite+React

- `src/pages/` — page components
- `src/stores/` — state stores
- `src/services/` — API layer
- `src/utils/` — formatters, step rendering, SSE handling

---

## 5 Project Structure

```
OmniAgentAs-desk/
├── backend/
│   ├── app/
│   │   ├── api/v1/             # REST endpoints
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── config.py           # YAML+env config loader
│   │   ├── models/             # SQLAlchemy + Pydantic
│   │   ├── services/
│   │   │   ├── agent/          # Agent subclasses, base_react, mixins/, types/
│   │   │   ├── tools/          # Tool categories
│   │   │   ├── preprocessing/  # Intent classifier
│   │   │   ├── intents/        # Intent definitions + CRSS scorer
│   │   │   ├── safety/         # Safety checks (placeholder)
│   │   │   └── llm_core.py     # LLM client
│   │   └── utils/
│   ├── tests/                  # pytest
│   ├── tools/                  # test/debug scripts
│   └── ~/.omniagent/           # SQLite DBs (chat_history.db, operations.db)
├── frontend/
│   ├── src/
│   └── package.json
├── config/                     # YAML configs
├── doc-agent2.0/               # Agent 2.0 redesign docs
├── doc/                        # system design docs
├── notes/                      # debug notes
├── version.txt                 # append-only version history
└── AGENTS.md
```

---

## 6 Key Dependencies

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

## 7  Known Pitfalls

| Pitfall | Detail |
|---------|--------|
| **httpx version lock** | `httpx==0.26.0` + `httpcore==1.0.1` required. Don't upgrade. |
| **Duplicate `__all__`** | Register files may have 2 `__all__` defs (second overwrites first). |
| **Tool impl vs registration** | Functions in `{cat}_tools.py`, registration in `{cat}_register.py`. Don't confuse them. |
| **`_loaded_categories`** | Per-agent set for tool loading. Initialized to `{current_category, support_tool}`. |
| **常量/枚举分散定义** | `ToolCategory` 值、Error Code 前缀等硬编码在多个文件，改分类名漏改一处就崩。集中定义在枚举/常量文件中，不要在各处写 magic string。 |
| **模块迁移后测试引用旧路径** | 重构迁移方法/类后，测试文件仍 import 旧模块路径（如 `_tools_to_schema_text` → `MessageBuilder.build_schema_text`）。重构后必须 `grep` 所有引用并同步更新测试。 |
| **构造器新增参数漏改调用方** | `FileTools(task_id=...)` 等构造器新增必需参数后，所有调用方（尤其测试中 ~69 处）都要改。变更签名前先 `grep` 定位全部调用方。 |
| **`datetime.replace(hour=N)` 跨夜崩溃** | 凌晨运行时 `hour-N<0` 抛 `ValueError`。一律用 `timedelta`（如 `base_time - timedelta(hours=1)`）做相对时间运算。 |
| **`finally` 中访问未绑定变量** | `try` 内 `raise` 后变量才赋值（如 `conn = get_connection()`），`finally` 访问导致 `UnboundLocalError`。在 `try` 前先 `conn = None` 初始化。 |
| **工具函数返回 key 不统一** | 部分代码用 `{"status":...,"summary":...}`，有的用 `{"code":...,"message":...}`。已有铁规要求统一用 `build_success()/build_error()`，检查时重点核对。 |

---

## 8 Git Workflow

```bash
# Commit format: <type>: <description> - <签名>-<日期>
# types: feat/fix/refactor/perf/test/docs

# Tag (PATCH only without asking):
# 1. Insert commit summary into version.txt (project root, append at top)
# 2. git tag v{major}.{minor}.{patch+1}
```

`version.txt` is append-only, oldest at bottom.

---##  9 Code Conventions

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
