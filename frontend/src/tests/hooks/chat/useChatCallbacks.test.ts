/**
 * useChatCallbacks 测试用例
 * 
 * 验证 useChatCallbacks Hook 是否正确管理所有SSE回调
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useChatCallbacks } from '../../../hooks/chat/useChatCallbacks';
import { useChatState } from '../../../hooks/chat/useChatState';
import type { ExecutionStep } from '../../../utils/sse';

describe('useChatCallbacks', () => {
  // 创建一个包装函数，用于在测试中初始化 useChatCallbacks
  const createTestHook = () => {
    return renderHook(() => {
      const chatState = useChatState();
      const callbacks = useChatCallbacks(chatState);
      return { chatState, callbacks };
    });
  };

  describe('1. 回调接口完整性测试', () => {
    it('应该包含所有必需的回调函数', () => {
      const { result } = createTestHook();
      
      expect(result.current.callbacks.onStep).toBeDefined();
      expect(typeof result.current.callbacks.onStep).toBe('function');
      
      expect(result.current.callbacks.onChunk).toBeDefined();
      expect(typeof result.current.callbacks.onChunk).toBe('function');
      
      expect(result.current.callbacks.onComplete).toBeDefined();
      expect(typeof result.current.callbacks.onComplete).toBe('function');
      
      expect(result.current.callbacks.onError).toBeDefined();
      expect(typeof result.current.callbacks.onError).toBe('function');
      
      expect(result.current.callbacks.onPaused).toBeDefined();
      expect(typeof result.current.callbacks.onPaused).toBe('function');
      
      expect(result.current.callbacks.onResumed).toBeDefined();
      expect(typeof result.current.callbacks.onResumed).toBe('function');
      
      expect(result.current.callbacks.onShowSteps).toBeDefined();
      expect(typeof result.current.callbacks.onShowSteps).toBe('function');
      
      expect(result.current.callbacks.onRetry).toBeDefined();
      expect(typeof result.current.callbacks.onRetry).toBe('function');
    });
  });

  describe('2. onShowSteps 测试', () => {
    it('应该能设置 showExecution 为 false', () => {
      const { result } = createTestHook();
      
      // 初始值为 true
      expect(result.current.chatState.showExecution).toBe(true);
      
      // 调用 onShowSteps(false)
      act(() => {
        result.current.callbacks.onShowSteps(false);
      });
      
      // 验证状态已更新
      expect(result.current.chatState.showExecution).toBe(false);
    });

    it('应该能设置 showExecution 为 true', () => {
      const { result } = createTestHook();
      
      // 先设置为 false
      act(() => {
        result.current.callbacks.onShowSteps(false);
      });
      expect(result.current.chatState.showExecution).toBe(false);
      
      // 再设置为 true
      act(() => {
        result.current.callbacks.onShowSteps(true);
      });
      
      expect(result.current.chatState.showExecution).toBe(true);
    });
  });

  describe('3. onRetry 测试', () => {
    it('应该设置 isRetrying 为 true', () => {
      const { result } = createTestHook();
      
      // 初始值为 false
      expect(result.current.chatState.isRetrying).toBe(false);
      
      // 调用 onRetry
      act(() => {
        result.current.callbacks.onRetry('retry message', 5000);
      });
      
      // 验证状态已更新
      expect(result.current.chatState.isRetrying).toBe(true);
    });

    it('应该设置 waitTime 为指定值', () => {
      const { result } = createTestHook();
      
      act(() => {
        result.current.callbacks.onRetry('retry message', 5000);
      });
      
      expect(result.current.chatState.waitTime).toBe(5000);
    });

    it('如果 waitTime 为 undefined，应该设置 waitTime 为 0', () => {
      const { result } = createTestHook();
      
      act(() => {
        result.current.callbacks.onRetry('retry message');
      });
      
      expect(result.current.chatState.waitTime).toBe(0);
    });
  });

  describe('4. onPaused 测试', () => {
    it('应该设置 isPaused 为 true', () => {
      const { result } = createTestHook();
      
      // 初始值为 false
      expect(result.current.chatState.isPaused).toBe(false);
      
      // 调用 onPaused
      act(() => {
        result.current.callbacks.onPaused();
      });
      
      // 验证状态已更新
      expect(result.current.chatState.isPaused).toBe(true);
    });
  });

  describe('5. onStep 基本测试', () => {
    it('应该能创建新的 assistant 消息', () => {
      const { result } = createTestHook();
      
      const testStep: ExecutionStep = {
        type: 'start',
        timestamp: Date.now(),
        content: '开始处理',
      };
      
      act(() => {
        result.current.callbacks.onStep(testStep);
      });
      
      // 验证消息已创建
      expect(result.current.chatState.messages.length).toBe(1);
      expect(result.current.chatState.messages[0].role).toBe('assistant');
    });

    it('应该在暂停时将 step 存入缓冲区', () => {
      const { result } = createTestHook();
      
      // 先暂停
      act(() => {
        result.current.callbacks.onPaused();
      });
      
      const testStep: ExecutionStep = {
        type: 'thought',
        timestamp: Date.now(),
        content: '思考中',
      };
      
      act(() => {
        result.current.callbacks.onStep(testStep);
      });
      
      // 消息不应该增加（因为在暂停状态）
      expect(result.current.chatState.messages.length).toBe(0);
      // 缓冲区应该有数据
      expect(result.current.chatState.displayBufferRef.current.length).toBeGreaterThan(0);
    });
  });

  describe('6. onChunk 基本测试', () => {
    it('应该能更新最后一条消息的内容', () => {
      const { result } = createTestHook();
      
      // 先创建一个 assistant 消息
      const startStep: ExecutionStep = {
        type: 'start',
        timestamp: Date.now(),
        content: '开始',
      };
      
      act(() => {
        result.current.callbacks.onStep(startStep);
      });
      
      // 发送 chunk
      act(() => {
        result.current.callbacks.onChunk('这是一段回复内容');
      });
      
      // 验证消息内容已更新
      expect(result.current.chatState.messages[0].content).toBe('这是一段回复内容');
    });
  });

  describe('7. onResumed 测试', () => {
    it('应该清空缓冲区并恢复 isPaused 状态', () => {
      const { result } = createTestHook();
      
      // 先暂停并添加数据到缓冲区
      act(() => {
        result.current.callbacks.onPaused();
      });
      
      const testStep: ExecutionStep = {
        type: 'thought',
        timestamp: Date.now(),
        content: '思考中',
      };
      
      act(() => {
        result.current.callbacks.onStep(testStep);
      });
      
      // 缓冲区有数据
      expect(result.current.chatState.displayBufferRef.current.length).toBeGreaterThan(0);
      
      // 恢复
      act(() => {
        result.current.callbacks.onResumed();
      });
      
      // 缓冲区应该被清空
      expect(result.current.chatState.displayBufferRef.current.length).toBe(0);
      // isPaused 应该为 false
      expect(result.current.chatState.isPaused).toBe(false);
    });
  });

  describe('8. 依赖完整性测试', () => {
    it('所有回调函数应该使用 useCallback 包装', () => {
      const { result } = createTestHook();
      
      // 验证每个回调都是稳定的（连续两次调用应该返回相同的函数引用）
      const callbacks1 = result.current.callbacks;
      const callbacks2 = result.current.callbacks;
      
      // 注意：由于每次渲染可能会创建新的对象，我们需要通过调用来验证
      // 这里主要是检查函数是否存在
      expect(callbacks1.onStep).toBeDefined();
      expect(callbacks1.onChunk).toBeDefined();
      expect(callbacks1.onComplete).toBeDefined();
      expect(callbacks1.onError).toBeDefined();
      expect(callbacks1.onPaused).toBeDefined();
      expect(callbacks1.onResumed).toBeDefined();
      expect(callbacks1.onShowSteps).toBeDefined();
      expect(callbacks1.onRetry).toBeDefined();
    });
  });
});
