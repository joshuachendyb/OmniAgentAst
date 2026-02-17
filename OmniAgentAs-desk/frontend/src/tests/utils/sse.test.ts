/**
 * SSE Utility Tests
 * 
 * @author 小新
 * @description Unit tests for SSE streaming utilities
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { 
  useSSE, 
  createSSEConnection, 
  formatExecutionStep,
  type ExecutionStep,
} from '../../utils/sse';
import { renderHook, act } from '@testing-library/react';

describe('SSE Utilities', () => {
  describe('formatExecutionStep', () => {
    it('should format thought step correctly', () => {
      const step: ExecutionStep = {
        type: 'thought',
        content: 'I need to analyze this',
        timestamp: Date.now(),
      };
      expect(formatExecutionStep(step)).toBe('I need to analyze this');
    });

    it('should format thought step with default text when no content', () => {
      const step: ExecutionStep = {
        type: 'thought',
        timestamp: Date.now(),
      };
      expect(formatExecutionStep(step)).toBe('思考中...');
    });

    it('should format action step with tool correctly', () => {
      const step: ExecutionStep = {
        type: 'action',
        tool: 'read_file',
        params: { path: '/test.txt' },
        timestamp: Date.now(),
      };
      expect(formatExecutionStep(step)).toContain('read_file');
      expect(formatExecutionStep(step)).toContain('path');
    });

    it('should format action step without tool correctly', () => {
      const step: ExecutionStep = {
        type: 'action',
        content: 'Executing command',
        timestamp: Date.now(),
      };
      expect(formatExecutionStep(step)).toBe('Executing command');
    });

    it('should format observation step with result correctly', () => {
      const step: ExecutionStep = {
        type: 'observation',
        result: { data: 'test' },
        timestamp: Date.now(),
      };
      expect(formatExecutionStep(step)).toContain('观察结果');
      expect(formatExecutionStep(step)).toContain('test');
    });

    it('should format final step correctly', () => {
      const step: ExecutionStep = {
        type: 'final',
        content: 'Task completed successfully',
        timestamp: Date.now(),
      };
      expect(formatExecutionStep(step)).toBe('Task completed successfully');
    });

    it('should format error step correctly', () => {
      const step: ExecutionStep = {
        type: 'error',
        content: 'Something went wrong',
        timestamp: Date.now(),
      };
      expect(formatExecutionStep(step)).toContain('错误');
      expect(formatExecutionStep(step)).toContain('Something went wrong');
    });
  });

  describe('useSSE Hook', () => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('should initialize with correct default values', () => {
      const { result } = renderHook(() =>
        useSSE({
          baseURL: 'http://localhost:8000',
          sessionId: 'test-session',
        })
      );

      expect(result.current.isConnected).toBe(false);
      expect(result.current.isReceiving).toBe(false);
      expect(result.current.executionSteps).toEqual([]);
      expect(result.current.currentResponse).toBe('');
    });

    it('should clear steps when clearSteps is called', () => {
      const { result } = renderHook(() =>
        useSSE({
          baseURL: 'http://localhost:8000',
          sessionId: 'test-session',
        })
      );

      act(() => {
        result.current.clearSteps();
      });

      expect(result.current.executionSteps).toEqual([]);
      expect(result.current.currentResponse).toBe('');
    });

    it('should disconnect when disconnect is called', () => {
      const { result } = renderHook(() =>
        useSSE({
          baseURL: 'http://localhost:8000',
          sessionId: 'test-session',
        })
      );

      act(() => {
        result.current.disconnect();
      });

      expect(result.current.isConnected).toBe(false);
      expect(result.current.isReceiving).toBe(false);
    });
  });

  describe('createSSEConnection', () => {
    it('should create EventSource with correct URL', () => {
      const mockHandlers = {
        onOpen: vi.fn(),
        onStep: vi.fn(),
        onChunk: vi.fn(),
        onComplete: vi.fn(),
        onError: vi.fn(),
        onClose: vi.fn(),
      };

      const eventSource = createSSEConnection(
        'http://localhost:8000/stream',
        mockHandlers
      );

      expect(eventSource).toBeInstanceOf(EventSource);
      expect(eventSource.url).toBe('http://localhost:8000/stream');
    });

    it('should call onOpen when connection opens', () => {
      const mockHandlers = {
        onOpen: vi.fn(),
      };

      const eventSource = createSSEConnection(
        'http://localhost:8000/stream',
        mockHandlers
      );

      // Simulate connection open
      if (eventSource.onopen) {
        eventSource.onopen(new Event('open'));
      }

      expect(mockHandlers.onOpen).toHaveBeenCalled();
    });

    it('should call onStep when receiving step message', () => {
      const mockHandlers = {
        onStep: vi.fn(),
      };

      const eventSource = createSSEConnection(
        'http://localhost:8000/stream',
        mockHandlers
      );

      const stepMessage = {
        type: 'step',
        data: {
          type: 'thought',
          content: 'Analyzing...',
          timestamp: Date.now(),
        },
      };

      // Simulate receiving message
      if (eventSource.onmessage) {
        eventSource.onmessage(new MessageEvent('message', {
          data: JSON.stringify(stepMessage),
        }));
      }

      expect(mockHandlers.onStep).toHaveBeenCalled();
    });

    it('should call onComplete when receiving complete message', () => {
      const mockHandlers = {
        onComplete: vi.fn(),
        onClose: vi.fn(),
      };

      const eventSource = createSSEConnection(
        'http://localhost:8000/stream',
        mockHandlers
      );

      const completeMessage = {
        type: 'complete',
      };

      // Simulate receiving complete message
      if (eventSource.onmessage) {
        eventSource.onmessage(new MessageEvent('message', {
          data: JSON.stringify(completeMessage),
        }));
      }

      expect(mockHandlers.onComplete).toHaveBeenCalled();
      expect(mockHandlers.onClose).toHaveBeenCalled();
    });

    it('should call onError when receiving error message', () => {
      const mockHandlers = {
        onError: vi.fn(),
        onClose: vi.fn(),
      };

      const eventSource = createSSEConnection(
        'http://localhost:8000/stream',
        mockHandlers
      );

      const errorMessage = {
        type: 'error',
        error: 'Connection failed',
      };

      // Simulate receiving error message
      if (eventSource.onmessage) {
        eventSource.onmessage(new MessageEvent('message', {
          data: JSON.stringify(errorMessage),
        }));
      }

      expect(mockHandlers.onError).toHaveBeenCalledWith('Connection failed');
      expect(mockHandlers.onClose).toHaveBeenCalled();
    });

    it('should handle connection errors', () => {
      const mockHandlers = {
        onError: vi.fn(),
        onClose: vi.fn(),
      };

      const eventSource = createSSEConnection(
        'http://localhost:8000/stream',
        mockHandlers
      );

      // Simulate connection error
      if (eventSource.onerror) {
        eventSource.onerror(new Event('error'));
      }

      expect(mockHandlers.onError).toHaveBeenCalledWith('连接错误');
      expect(mockHandlers.onClose).toHaveBeenCalled();
    });
  });
});
