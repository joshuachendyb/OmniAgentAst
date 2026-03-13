# AGENTS.md - OmniAgentAs-desk Development Guide

**Project**: OmniAgentAs-desk  
**Type**: Full-stack web application (React + FastAPI)  
**Version**: v0.5.4

---

## 1. Project Structure

```
OmniAgentAs-desk/
├── backend/           # Python FastAPI backend
│   ├── app/          # Application code
│   │   ├── api/v1/   # API endpoints
│   │   ├── services/  # Business logic
│   │   └── utils/    # Utilities
│   ├── tests/        # Backend tests (pytest)
│   └── requirements.txt
├── frontend/         # React + TypeScript frontend
│   ├── src/         # Source code
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── utils/
│   ├── tests/        # Frontend tests
│   └── package.json
└── config/           # Configuration files
```

---

## 2. Commands

### Frontend (TypeScript/React)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server |
| `npm run build` | Build for production |
| `npm run test` | Run unit tests (Vitest) |
| `npm run test:watch` | Run tests in watch mode |
| `npm run test:coverage` | Run tests with coverage |
| `npm run lint` | Run ESLint |
| `npm run lint:fix` | Auto-fix ESLint issues |
| `npm run format` | Format code with Prettier |
| `npm run format:check` | Check code formatting |
| `npm run test:e2e` | Run Playwright E2E tests |
| `npm run test:e2e:ui` | Run E2E tests with UI |

**Run a single test**:
```bash
npm run test -- --run <test-name>
# Example: npm run test -- --run MessageItem
```

### Backend (Python/FastAPI)

| Command | Description |
|---------|-------------|
| `python -m uvicorn app.main:app --reload` | Start dev server |
| `pytest` | Run all tests |
| `pytest -v` | Run tests verbose |
| `pytest tests/test_adapter.py` | Run specific test file |
| `pytest -k test_name` | Run tests matching pattern |
| `pytest --cov=app` | Run with coverage |

**Run a single test**:
```bash
pytest tests/test_adapter.py::test_function_name -v
```

---

## 3. Code Style Guidelines

### TypeScript/React (Frontend)

**Naming Conventions**:
- Components: PascalCase (`ChatContainer`, `MessageItem`)
- Functions/variables: camelCase (`getMessages`, `userName`)
- Constants: UPPER_SNAKE_CASE
- Files: kebab-case (`my-component.tsx`)

**Imports**:
- Order: external → internal → relative
- Use absolute imports from `@/` alias
- No default exports for components

**TypeScript**:
- Always use explicit types for function parameters and return values
- Avoid `any`, use `unknown` if needed
- Use interfaces for object shapes

**React**:
- Use functional components with hooks
- Use `useCallback`/`useMemo` for optimization
- Never mutate state directly
- Add keys to lists

**Formatting**:
- Use Prettier (2 spaces, single quotes)
- ESLint will catch most issues

### Python (Backend)

**Naming**:
- Functions/variables: snake_case (`get_messages`, `user_name`)
- Classes: PascalCase (`MessageHandler`, `AgentService`)
- Constants: UPPER_SNAKE_CASE

**Imports**:
- Order: stdlib → third-party → local
- Use absolute imports within package

**Type Hints**:
- Always use type hints for function parameters and returns
- Use `Optional[X]` instead of `X | None`

**Error Handling**:
- Use custom exceptions for business logic
- Always log errors with appropriate level
- Return meaningful error messages to API callers

---

## 4. Git Commit Rules

**Format**: `type: description`

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `test`: Test changes
- `docs`: Documentation

**Example**:
```
feat: add session management API - 小沈-2026-03-13
fix: resolve message display issue - 小新-2026-03-13
```

---

## 5. Key Dependencies

### Frontend
- React 18, TypeScript 5
- Ant Design 5, Axios, React Router 7
- Vitest, Playwright (testing)
- ESLint, Prettier

### Backend
- FastAPI, Uvicorn
- SQLAlchemy, aiosqlite
- Pydantic, httpx
- pytest (testing)

---

## 6. Notes

- Backend runs on `http://127.0.0.1:8000`
- Frontend runs on `http://localhost:5173`
- API docs at `http://127.0.0.1:8000/docs`
- Database: SQLite (`backend/chat_app.db`)
- Use `npm run check` before committing
