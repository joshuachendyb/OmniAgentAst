/**
 * Test Utilities
 * 
 * @author 小新
 * @description Test utilities and helpers for frontend tests
 */

import { vi, expect, beforeAll, afterAll } from 'vitest';
import type { ChatMessage, Config, Session, ExecutionStep } from '../../services/api';

/**
 * Create a mock chat message
 */
export const createMockMessage = (
  overrides: Partial<ChatMessage & { id: string; timestamp: Date }> = {}
): ChatMessage & { id: string; timestamp: Date } => ({
  id: `msg-${Date.now()}`,
  role: 'user',
  content: 'Test message',
  timestamp: new Date(),
  ...overrides,
});

/**
 * Create a mock execution step
 */
export const createMockExecutionStep = (
  overrides: Partial<ExecutionStep> = {}
): ExecutionStep => ({
  type: 'thought',
  content: 'Test thought',
  timestamp: Date.now(),
  ...overrides,
});

/**
 * Create a mock config
 * @author 小新
 */
export const createMockConfig = (
  overrides: Partial<Config> = {}
): Config => ({
  ai_provider: 'zhipuai',
  ai_model: 'glm-4-flash',
  api_key_configured: true,
  theme: 'light',
  language: 'zh-CN',
  ...overrides,
});

/**
 * Create a mock session
 * @author 小新
 */
export const createMockSession = (
  overrides: Partial<Session> = {}
): Session => ({
  session_id: `session-${Date.now()}`,
  title: 'Test Session',
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
  message_count: 10,
  ...overrides,
});

/**
 * Mock EventSource for testing
 */
/**
 * Mock EventSource for testing
 * @author 小新
 */
export class MockEventSource {
  onopen: ((ev: Event) => any) | null = null;
  onmessage: ((ev: MessageEvent) => any) | null = null;
  onerror: ((ev: Event) => any) | null = null;
  readyState: number = 0;
  url: string;
  withCredentials: boolean = false;
  CONNECTING: number = 0;
  OPEN: number = 1;
  CLOSED: number = 2;

  constructor(url: string | URL) {
    this.url = url.toString();
    this.readyState = 0;

    // Simulate connection opening
    setTimeout(() => {
      this.readyState = 1;
      if (this.onopen) {
        this.onopen(new Event('open'));
      }
    }, 10);
  }

  close() {
    this.readyState = 2;
  }

  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }

  /**
   * Simulate receiving a message
   */
  simulateMessage(data: unknown) {
    if (this.onmessage) {
      this.onmessage(new MessageEvent('message', {
        data: JSON.stringify(data),
      }));
    }
  }

  /**
   * Simulate an error
   */
  simulateError() {
    if (this.onerror) {
      this.onerror(new Event('error'));
    }
  }
}

/**
 * Setup mock for EventSource
 * @author 小新
 */
export const setupEventSourceMock = () => {
  Object.defineProperty(window, 'EventSource', {
    value: MockEventSource,
    writable: true,
  });
};

/**
 * Wait for a specified time
 */
export const wait = (ms: number): Promise<void> => 
  new Promise(resolve => setTimeout(resolve, ms));

/**
 * Create a deferred promise for async testing
 */
export function createDeferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: Error) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  
  return { promise, resolve, reject };
}

/**
 * Mock console methods to suppress output during tests
 */
export const suppressConsole = () => {
  const originalConsole = {
    log: console.log,
    error: console.error,
    warn: console.warn,
  };

  beforeAll(() => {
    console.log = vi.fn();
    console.error = vi.fn();
    console.warn = vi.fn();
  });

  afterAll(() => {
    console.log = originalConsole.log;
    console.error = originalConsole.error;
    console.warn = originalConsole.warn;
  });
};

/**
 * Generate an array of mock items
 */
export const generateMocks = <T>(
  factory: (index: number) => T,
  count: number
): T[] => {
  return Array.from({ length: count }, (_, i) => factory(i));
};

/**
 * Mock localStorage
 */
export const mockLocalStorage = () => {
  const store: Record<string, string> = {};
  
  return {
    getItem: vi.fn((key: string) => store[key] || null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      Object.keys(store).forEach(key => delete store[key]);
    }),
    getStore: () => ({ ...store }),
  };
};

/**
 * Mock fetch API
 * @author 小新
 */
export const mockFetch = (response: unknown, status = 200) => {
  Object.defineProperty(window, 'fetch', {
    value: vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: vi.fn().mockResolvedValue(response),
      text: vi.fn().mockResolvedValue(JSON.stringify(response)),
    } as unknown as Response),
    writable: true,
  });
};

/**
 * Assert that an element has the expected text content
 */
export const expectToHaveText = (
  element: HTMLElement | null,
  text: string | RegExp
) => {
  if (!element) {
    throw new Error('Element is null');
  }
  
  if (typeof text === 'string') {
    expect(element.textContent).toContain(text);
  } else {
    expect(element.textContent).toMatch(text);
  }
};

/**
 * Simulate typing in an input element
 */
export const simulateTyping = async (
  element: HTMLElement,
  text: string,
  delay = 0
) => {
  for (const char of text) {
    element.dispatchEvent(new KeyboardEvent('keydown', { key: char }));
    element.dispatchEvent(new KeyboardEvent('keypress', { key: char }));
    element.dispatchEvent(new KeyboardEvent('keyup', { key: char }));
    
    if (delay > 0) {
      await wait(delay);
    }
  }
};
