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

---

## 7. 文档操作检查清单（必须遵守）

**触发条件**：修改文档（.md文件）前必须检查

### 7.1 多内容确认

遇到用户问题包含多个内容时：

| 步骤 | 检查项 |
|------|--------|
| 1 | 列出所有内容项 |
| 2 | 确认每项放置位置（现有章节/新建章节） |
| 3 | 确认章节编号 |
| 4 | **等用户确认后再执行** |

**示例**：
```
用户问："这个是不是只适应文件操作的？其他类型的操作能不能适用呢？应该在第9章吧？"

我应该先确认：
1. "v0.7.38/v0.7.39操作记录" → 放在8.10节？
2. "ver1_run_stream()通用性分析" → 新建第9章？

等用户回复后再执行。
```

### 7.2 章节编号确认

| 情况 | 要求 |
|------|------|
| 在现有章节末尾追加 | 确认章节号连续 |
| 新建章节 | 确认章节编号 |
| 不确定放哪 | 先问用户 |

### 7.3 版本历史检查

| 检查项 | 说明 |
|--------|------|
| 版本号连续 | v1.11 → v1.12 |
| 时间戳真实 | 执行命令获取，不估计 |
| 更新内容准确 | 如实描述修改内容 |

### 7.4 禁止行为

| 禁止 | 说明 |
|------|------|
| ❌ 多个内容不确认就执行 | 必须逐项确认 |
| ❌ 章节编号不确认 | 必须问用户 |
| ❌ 估计时间戳 | 必须执行命令获取 |
| ❌ 执行后再说"理解错了" | 执行前确认清楚 |
