/**
 * Test Setup File
 *
 * @author 小新
 * @description Vitest test environment setup
 * @update 2026-02-18 修复类型定义 by 小新
 */

import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock IntersectionObserver
Object.defineProperty(window, 'IntersectionObserver', {
  writable: true,
  value: class MockIntersectionObserver {
    constructor() {}
    disconnect() {}
    observe() {}
    unobserve() {}
    takeRecords() { return []; }
  },
});

// Mock EventSource
Object.defineProperty(window, 'EventSource', {
  writable: true,
  value: class MockEventSource {
    onopen: ((this: EventSource, ev: Event) => any) | null = null;
    onmessage: ((this: EventSource, ev: MessageEvent) => any) | null = null;
    onerror: ((this: EventSource, ev: Event) => any) | null = null;
    readyState: number = 0;
    url: string = '';
    withCredentials: boolean = false;
    CONNECTING: number = 0;
    OPEN: number = 1;
    CLOSED: number = 2;

    constructor(url: string | URL, _eventSourceInitDict?: EventSourceInit) {
      this.url = url.toString();
      this.readyState = 0;
    }

    close() {
      this.readyState = 2;
    }

    addEventListener() {}
    removeEventListener() {}
    dispatchEvent() { return true; }
  },
});

// Mock clipboard
Object.defineProperty(navigator, 'clipboard', {
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(''),
  },
  writable: true,
});

// Mock window.scrollTo
Object.defineProperty(window, 'scrollTo', {
  writable: true,
  value: vi.fn(),
});

// Mock ResizeObserver
Object.defineProperty(window, 'ResizeObserver', {
  writable: true,
  value: class MockResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
});
