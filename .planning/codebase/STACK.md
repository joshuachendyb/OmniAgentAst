# STACK.md - Technology Stack

## Languages & Runtime

| Component | Version | Notes |
|-----------|---------|-------|
| Python | >=3.11 | Backend runtime |
| Node.js | 18+ | Frontend build |
| TypeScript | 5.2.2 | Frontend language |

## Frontend Stack

| Library | Version | Purpose |
|---------|---------|---------|
| React | 18.2.0 | UI framework |
| Ant Design | 5.12.0 | UI component library |
| Vite | 5.0.8 | Build tool |
| React Router | 7.13.0 | Routing |
| Axios | 1.6.0 | HTTP client |
| Day.js | 1.11.19 | Date handling |
| KaTeX | 0.16.38 | Math rendering |

### Frontend Dev Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Vitest | 1.1.0 | Unit testing |
| Playwright | 1.40.0 | E2E testing |
| ESLint | 8.57.0 | Linting |
| Prettier | 3.8.1 | Formatting |

### Frontend Entry Points

- `frontend/src/main.tsx` - Application entry
- `frontend/src/App.tsx` - Root component

### Frontend Key Files

- `frontend/vite.config.ts` - Vite configuration
- `frontend/tsconfig.json` - TypeScript config

## Backend Stack

| Library | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.109.0 | Web framework |
| Uvicorn | 0.27.0 | ASGI server |
| SQLAlchemy | 2.0.25 | ORM |
| aiosqlite | 0.19.0 | SQLite async driver |
| Pydantic | 2.5.3 | Data validation |
| httpx | 0.26.0 | HTTP client |

### Backend Entry Points

- `backend/app/main.py` - Application entry

### Backend API Structure

```
backend/app/
├── api/v1/           # API routes
│   ├── sessions.py
│   ├── execution.py
│   ├── config.py
│   └── metrics.py
├── services/        # Business logic
│   ├── agent/       # Agent logic
│   ├── tools/      # Tool implementations
│   ├── safety/     # Security checks
│   └── preprocessing/  # Input preprocessing
├── chat_stream/     # SSE streaming
└── models/         # Data models
```

## Build & Test Commands

### Frontend

```bash
npm run dev          # Dev server (port 5173)
npm run build       # Production build
npm run test        # Unit tests
npm run test:e2e   # E2E tests (requires backend)
npm run lint       # ESLint check
npm run check      # lint + format check
```

### Backend

```bash
python -m uvicorn app.main:app --reload  # Dev server (port 8000)
pytest                              # Run tests
```

## Database

- **Location**: `C:\Users\40968\.omniagent\chat_history.db`
- **Type**: SQLite

---

**Created**: 2026-04-12
**Focus**: tech