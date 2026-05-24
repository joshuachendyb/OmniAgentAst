# AGENTS.md - OmniAgentAs-desk

**Version**: v0.13.33 | **Project**: Full-stack (React+FastAPI) AI agent desktop

> Global rules (roles, timestamps, commit format, versioning, doc style) are in `C:\Users\chend\.config\opencode\AGENTS.md` (auto-loaded).
> This file contains **project-specific** info only.

---

## 编码铁规（必须遵守）

**生效时间**: 2026-05-24 18:05:46 | **适用范围**: 所有代码文件
**更新人**: 北京老陈

### DRY — Don't Repeat Yourself
相同的逻辑不得出现两遍。重复代码必须抽取为函数/类/常量/工具方法，一处定义多处引用。

### KISS — Keep It Simple, Stupid
保持简单。能用简单方案不用复杂方案，不提前引入模式/抽象/框架。

### SLAP — Single Level of Abstraction Principle
同一函数内代码的抽象层次必须一致。一个函数只做一件事，不混入高层逻辑和底层实现细节。

### SRP — Single Responsibility Principle
一个类/模块/函数只负责一个职责。职责不同必须拆分，不得混在一起。

### 违反后果
上述铁规是必须遵守的编码纪律。违反者代码被打回重写，直到符合原则为止。

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

## Project Structure

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
