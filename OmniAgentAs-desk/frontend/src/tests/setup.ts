/**
 * Test Setup File
 * 
 * @author 小新
 * @description Vitest test environment setup
 */

import '@testing-library/jest-dom';
import { vi } from 'vitest';

// Mock matchMedia
global.matchMedia = global.matchMedia || function() {
  return {
    matches: false,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  };
};

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
  takeRecords() { return []; }
};

// Mock EventSource
global.EventSource = class EventSource {
  onopen: ((this: EventSource, ev: Event) => any) | null = null;
  onmessage: ((this: EventSource, ev: MessageEvent) => any) | null = null;
  onerror: ((this: EventSource, ev: Event) => any) | null = null;
  readyState: number = 0;
  url: string = '';
  withCredentials: boolean = false;

  constructor(url: string | URL, eventSourceInitDict?: EventSourceInit) {
    this.url = url.toString();
    this.readyState = 0;
  }

  close() {
    this.readyState = 2;
  }

  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return true; }
};

// Mock clipboard
Object.defineProperty(global.navigator, 'clipboard', {
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(''),
  },
  writable: true,
});

// Mock window.scrollTo
window.scrollTo = vi.fn();

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
