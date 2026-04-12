# CONVENTIONS.md - Coding Conventions

## Frontend Conventions

### Naming

| Type | Convention | Example |
|------|-----------|---------|
| Components | PascalCase | `ChatContainer`, `MessageItem` |
| Functions | camelCase | `getMessages`, `userName` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |
| Files | kebab-case | `my-component.tsx` |

### Imports

- Order: external → internal → relative
- Use absolute imports from `@/` alias
- No default exports for components

### TypeScript

- Always use explicit types for function parameters and return values
- Avoid `any`, use `unknown` if needed
- Use interfaces for object shapes

### React

- Use functional components with hooks
- Use `useCallback`/`useMemo` for optimization
- Never mutate state directly
- Add keys to lists

### Formatting

- Prettier: 2 spaces, single quotes
- ESLint will catch most issues

## Backend Conventions

### Naming

| Type | Convention | Example |
|------|-----------|---------|
| Functions/variables | snake_case | `get_messages`, `user_name` |
| Classes | PascalCase | `MessageHandler`, `AgentService` |
| Constants | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT` |

### Imports

- Order: stdlib → third-party → local
- Use absolute imports within package

### Type Hints

- Always use type hints for function parameters and returns
- Use `Optional[X]` instead of `X | None`

### Error Handling

- Use custom exceptions for business logic
- Always log errors with appropriate level
- Return meaningful error messages to API callers

## Git Commit Format

```
type: description - 签名-YYYY-MM-DD
```

- Types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`

Example:
```
feat: add session management API - 小沈-2026-03-13
```

---

**Created**: 2026-04-12
**Focus**: quality