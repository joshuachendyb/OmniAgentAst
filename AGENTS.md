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
pytest --ignore=tests/test_score_intents.py --ignore=tests/test_search_tool_only.py --ignore=tests/test_chat.py --ignore=tests/test_agent.py  # skip known failures
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

**Request flow**: `chat_router.py` → CRSS regex + LLM fallback intent detection → `AgentFactory.create(intent_type)` → 9 Agent subclasses → ReAct loop → SSE

**Agent system** (`backend/app/services/agent/`):
- `base_react.py` — `BaseAgent(ABC)` + `ReactAgentMixin` (1100+ lines, ReAct loop core)
- **9 subclasses**: `FileReactAgent`, `TimeReactAgent` (substantially different), `ShellReactAgent`, `NetworkReactAgent`, `DesktopReactAgent`, `SystemReactAgent`, `DocumentReactAgent`, `DatabaseReactAgent`, `CodeExecutionReactAgent` (last 7 are homogeneous — only differ in Prompt + Category)
- `agent_factory.py` — intent_type → Agent class mapping
- `react_output_parser.py` — LLM response parsing chain (`_HANDLERS`, `_process_tool_params`)
- `parsers/` — **@deprecated** (2026-04-19 strategy pattern, unused). All 7 files marked deprecated. Use `react_output_parser.py` instead.
- `strategy_selector.py` — LLM strategy: `text` / `response_format` / `tools`

**Tool registry** (`backend/app/services/tools/`):
- `registry.py` — `ToolRegistry` singleton, `ToolCategory` enum (**7 categories**, not 12)
- `__init__.py` — `ensure_tools_registered()` loads all **59 tools** across 7 categories
- 7 category dirs: `file` (11), `shell` (5), `network` (5), `system` (10), `desktop` (10), `document` (9), `meta` (9)
- Merged categories: TIME→META, ENVIRONMENT→SYSTEM, DATABASE→DOCUMENT, CODE_EXECUTION→SHELL
- Each `{category}/` has: `{category}_register.py`, `{category}_tools.py`, `{category}_schema.py`

**Safety**: `command_security.py` — blacklist-based command safety check

**Prompt logging**: `backend/logs/prompt-logs/prompt_{round}+{timestamp}.json`

### Frontend: `frontend/src/main.tsx` → Vite+React

- `src/pages/` — page components
- `src/stores/` — zustand stores
- `src/services/` — API layer (axios)
- `src/utils/` — formatters, step rendering

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
│   │   │   ├── agent/          # 9 Agent subclasses, base_react, mixins/, types/
│   │   │   ├── tools/          # 7 categories, 59 tools
│   │   │   ├── preprocessing/  # Intent classifier
│   │   │   ├── intents/        # Intent definitions
│   │   │   ├── safety/         # Safety checks
│   │   │   └── llm_core.py     # LLM client
│   │   └── utils/
│   ├── tests/                  # pytest
│   ├── tools/                  # test/debug scripts
│   └── chat_app.db             # SQLite
├── frontend/
│   ├── src/
│   └── package.json
├── config/                     # YAML configs
├── doc-agent2.0/               # Agent 2.0 redesign docs (方案A/B/C)
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
| | Ant Design 5, Axios, React Router, Zustand | |
| | Vitest, Playwright, ESLint, Prettier | |

**Server URLs**: Backend `http://127.0.0.1:8000` | API docs `http://127.0.0.1:8000/docs` | Frontend `http://localhost:5173`

---

## Known Pitfalls

| Pitfall | Detail |
|---------|--------|
| **httpx version lock** | `httpx==0.26.0` + `httpcore==1.0.1` required. Don't upgrade. |
| **Duplicate `__all__`** | Register files may have 2 `__all__` defs (second overwrites first). Check `data_analysis_register.py` pattern. |
| **`parsers/` is deprecated** | All files in `agent/parsers/` marked @deprecated. Use `react_output_parser.py` chain instead. |
| **Tool impl vs registration** | Functions in `{cat}_tools.py`, registration in `{cat}_register.py`. Don't confuse them. |
| **`_loaded_categories`** | Per-agent set for tool loading. Initialized to `{current_category, support_tool}`. All 59 tools registered at once via `ensure_tools_registered()`. |
| **Test name collision** | `tests/unit/test_data_format_tools.py` and `tests/data_format/test_data_format_tools.py` share module name → pytest `.pyc` cache collision. |
| **Tool count is 59, not 135** | Old docs may say 135 tools / 12 categories. Current: 59 tools / 7 categories (since v0.13.0). |
| **`check_date` renamed to `query_calendar`** | Function and all references renamed in v0.13.11. Old name no longer exists. |

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
