# AGENTS.md - OmniAgentAs-desk

**Version**: v0.13.11 | **Project**: Full-stack (React+FastAPI) AI agent desktop

> Global rules (roles, timestamps, commit format, versioning, doc style) are in `C:\Users\chend\.config\opencode\AGENTS.md` (auto-loaded).
> This file contains **project-specific** info only.

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
│   └── chat_app.db             # SQLite
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
| Backend | FastAPI, Uvicorn, SQLAlchemy, aiosqlite | SQLite `chat_app.db` |
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

---

## Code Conventions

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
