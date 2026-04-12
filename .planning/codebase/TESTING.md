# TESTING.md - Testing Practices

## Frontend Testing

### Test Framework

- **Unit**: Vitest 1.1.0
- **E2E**: Playwright 1.40.0
- **Assertion**: React Testing Library

### Test Structure

```
frontend/tests/
├── unit/           # Unit tests
│   ├── utils/
│   └── components/
└── e2e/         # E2E tests
```

### Running Tests

```bash
# Unit tests
npm run test

# Single test
npm run test -- --run <test-name>

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage

# E2E tests (requires backend on port 8000)
npm run test:e2e

# E2E with UI
npm run test:e2e:ui
```

### Key Test Files

- `tests/components/MessageItem.test.tsx` - Message display
- `tests/components/ExecutionPanel.test.tsx` - Execution panel
- `tests/utils/formatTimestamp.test.ts` - Timestamp formatting
- `tests/integration/api.integration.test.ts` - API integration

### Test Setup

- Config: `tests/setup.ts`
- DOM: jsdom environment

## Backend Testing

### Test Framework

- **Framework**: pytest

### Running Tests

```bash
pytest              # Run all tests
pytest -v           # Verbose
pytest tests/       # Specific directory
pytest -k <pattern> # Match pattern
```

---

**Created**: 2026-04-12
**Focus**: quality