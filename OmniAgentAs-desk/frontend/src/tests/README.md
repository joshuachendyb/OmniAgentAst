/**
 * Testing README
 * 
 * @author 小新
 * @description Testing documentation and guide
 */

# Frontend Testing Guide

## Testing Stack

| Type | Tool | Purpose |
|------|------|---------|
| Unit Testing | Vitest | Component and utility unit tests |
| Integration Testing | Vitest + MSW | API integration tests |
| E2E Testing | Playwright | End-to-end user flow tests |
| Coverage | @vitest/coverage-v8 | Code coverage reporting |

## Directory Structure

```
frontend/
├── src/tests/
│   ├── setup.ts                 # Test environment setup
│   ├── utils/
│   │   ├── sse.test.ts         # SSE utility tests
│   │   └── testUtils.ts        # Test utilities
│   ├── components/
│   │   ├── MessageItem.test.tsx
│   │   └── ExecutionPanel.test.tsx
│   └── integration/
│       └── api.integration.test.ts
├── e2e/
│   ├── chat.spec.ts            # Chat E2E tests
│   └── settings.spec.ts        # Settings E2E tests
├── vitest.config.ts            # Vitest configuration
└── playwright.config.ts        # Playwright configuration
```

## Running Tests

### Unit Tests

```bash
# Run all unit tests
npm test

# Run in watch mode
npm run test:watch

# Run with coverage
npm run test:coverage
```

### E2E Tests

```bash
# Run all E2E tests
npm run test:e2e

# Run with UI mode
npm run test:e2e:ui

# Run in debug mode
npm run test:e2e:debug
```

## Coverage Goals

- **Lines**: >= 80%
- **Functions**: >= 80%
- **Branches**: >= 80%
- **Statements**: >= 80%

## Test Categories

### 1. Unit Tests

Test individual components and utilities in isolation:

```typescript
// Example: Component test
describe('MessageItem', () => {
  it('should render user message', () => {
    render(<MessageItem message={mockUserMessage} />);
    expect(screen.getByText('Test message')).toBeInTheDocument();
  });
});
```

### 2. Integration Tests

Test API calls and service integrations:

```typescript
// Example: API integration test
describe('Chat API', () => {
  it('should send message', async () => {
    const result = await chatApi.sendMessage({ message: 'Hello' });
    expect(result.response).toBeDefined();
  });
});
```

### 3. E2E Tests

Test complete user flows:

```typescript
// Example: E2E test
test('should send message and receive response', async ({ page }) => {
  await page.goto('/');
  await page.fill('[placeholder="输入消息..."]', 'Hello');
  await page.click('text=发送消息');
  await expect(page.locator('text=Hello')).toBeVisible();
});
```

## Mocking

### Mocking EventSource

```typescript
import { MockEventSource } from './utils/testUtils';

global.EventSource = MockEventSource;
```

### Mocking Fetch/Axios

```typescript
import { mockFetch } from './utils/testUtils';

mockFetch({ data: 'mock response' }, 200);
```

### Mocking LocalStorage

```typescript
import { mockLocalStorage } from './utils/testUtils';

const localStorageMock = mockLocalStorage();
Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});
```

## Test Utilities

### Creating Mock Data

```typescript
import {
  createMockMessage,
  createMockExecutionStep,
  createMockModelConfig,
} from './utils/testUtils';

const message = createMockMessage({ role: 'assistant' });
const step = createMockExecutionStep({ type: 'thought' });
const config = createMockModelConfig({ provider: 'opencode' });
```

### Async Testing

```typescript
import { wait, createDeferred } from './utils/testUtils';

// Wait for async operations
await wait(100);

// Use deferred for complex async scenarios
const deferred = createDeferred<string>();
setTimeout(() => deferred.resolve('done'), 100);
const result = await deferred.promise;
```

## Best Practices

1. **Test Behavior, Not Implementation**
   - Test what the user sees and interacts with
   - Avoid testing internal state

2. **Use Meaningful Test Names**
   - Describe the behavior being tested
   - Format: "should [expected behavior] when [condition]"

3. **Keep Tests Independent**
   - Each test should set up its own state
   - Don't rely on tests running in order

4. **Use Test Utilities**
   - Reuse mock factories
   - Use helper functions for common operations

5. **Mock External Dependencies**
   - API calls
   - Browser APIs (EventSource, clipboard, etc.)
   - Third-party libraries

## Debugging Tests

### Unit Tests

```bash
# Run specific test file
npx vitest run src/tests/components/MessageItem.test.tsx

# Run with UI
npx vitest --ui
```

### E2E Tests

```bash
# Run in headed mode
npx playwright test --headed

# Run specific test
npx playwright test chat.spec.ts

# Debug mode
npx playwright test --debug
```

## Continuous Integration

Tests are configured to run on CI with:

- Coverage thresholds enforced
- Screenshots on E2E failure
- HTML reports generated

## Troubleshooting

### Common Issues

1. **EventSource not defined**
   - Import MockEventSource from testUtils
   - Set up in test setup file

2. **act() warnings**
   - Use waitFor from testing-library
   - Wrap async operations properly

3. **Mock not working**
   - Ensure mock is set up before import
   - Check for hoisting issues

4. **Coverage not accurate**
   - Check vitest.config.ts exclude patterns
   - Ensure source maps are enabled

## Contributing

When adding new tests:

1. Follow existing naming conventions
2. Use test utilities for consistency
3. Add tests for both success and error cases
4. Update this README if adding new patterns
