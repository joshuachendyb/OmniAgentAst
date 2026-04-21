/**
 * useChatState 测试用例
 * 
 * 验证 useChatState Hook 是否正确管理所有状态和Refs
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useChatState } from '../../../hooks/chat/useChatState';

describe('useChatState', () => {
  describe('1. 初始化状态测试', () => {
    it('应该初始化 messages 为空数组', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.messages).toEqual([]);
    });

    it('应该初始化 loading 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.loading).toBe(false);
    });

    it('应该初始化 waitTime 为 0', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.waitTime).toBe(0);
    });

    it('应该初始化 isRetrying 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isRetrying).toBe(false);
    });

    it('应该初始化 isPaused 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isPaused).toBe(false);
    });

    it('应该初始化 sessionId 为 null', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.sessionId).toBeNull();
    });

    it('应该初始化 sessionTitle 为 "新会话"', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.sessionTitle).toBe("新会话");
    });

    it('应该初始化 sessionVersion 为 1', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.sessionVersion).toBe(1);
    });

    it('应该初始化 titleLocked 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.titleLocked).toBe(false);
    });

    it('应该初始化 editingTitle 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.editingTitle).toBe(false);
    });

    it('应该初始化 titleInput 为空字符串', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.titleInput).toBe("");
    });

    it('应该初始化 lastSavedTitle 为空字符串', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.lastSavedTitle).toBe("");
    });

    it('应该初始化 showExecution 为 true', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.showExecution).toBe(true);
    });

    it('应该初始化 useStream 为 true', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.useStream).toBe(true);
    });

    it('应该初始化 isInitialized 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isInitialized).toBe(false);
    });

    it('应该初始化 saveStatus 为 "idle"', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.saveStatus).toBe("idle");
    });

    it('应该初始化 sessionJumpLoading 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.sessionJumpLoading).toBe(false);
    });

    it('应该初始化 isMessageListLoading 为 true', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isMessageListLoading).toBe(true);
    });

    it('应该初始化 retryCount 为空对象', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.retryCount).toEqual({});
    });

    it('应该初始化 isSavingTitle 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isSavingTitle).toBe(false);
    });

    it('应该初始化 lastSaveTime 为 0', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.lastSaveTime).toBe(0);
    });
  });

  describe('2. 状态更新测试', () => {
    it('应该正确更新 messages', () => {
      const { result } = renderHook(() => useChatState());
      const testMessage = { id: '1', role: 'user' as const, content: 'test', timestamp: new Date() };
      
      act(() => {
        result.current.setMessages([testMessage]);
      });
      
      expect(result.current.messages).toEqual([testMessage]);
    });

    it('应该正确更新 loading', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setLoading(true);
      });
      
      expect(result.current.loading).toBe(true);
    });

    it('应该正确更新 isPaused', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setIsPaused(true);
      });
      
      expect(result.current.isPaused).toBe(true);
    });

    it('应该正确更新 sessionId', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setSessionId('test-session-id');
      });
      
      expect(result.current.sessionId).toBe('test-session-id');
    });

    it('应该正确更新 sessionTitle', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setSessionTitle('新标题');
      });
      
      expect(result.current.sessionTitle).toBe('新标题');
    });

    it('应该正确更新 saveStatus', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setSaveStatus('saving');
      });
      
      expect(result.current.saveStatus).toBe('saving');
    });

    it('应该正确更新 retryCount', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setRetryCount({ 'msg-1': 2 });
      });
      
      expect(result.current.retryCount).toEqual({ 'msg-1': 2 });
    });
  });

  describe('3. Refs初始化测试', () => {
    it('应该初始化 waitTimerRef 为 null', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.waitTimerRef.current).toBeNull();
    });

    it('应该初始化 messagesEndRef 为 null', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.messagesEndRef.current).toBeNull();
    });

    it('应该初始化 currentSessionIdRef 为 null', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.currentSessionIdRef.current).toBeNull();
    });

    it('应该初始化 messagesCountRef 为 0', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.messagesCountRef.current).toBe(0);
    });

    it('应该初始化 messagesRef 为空数组', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.messagesRef.current).toEqual([]);
    });

    it('应该初始化 replyUserMessageIdRef 为 null', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.replyUserMessageIdRef.current).toBeNull();
    });

    it('应该初始化 displayBufferRef 为空数组', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.displayBufferRef.current).toEqual([]);
    });

    it('应该初始化 isPausedRef 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isPausedRef.current).toBe(false);
    });

    it('应该初始化 executionStepsRef 为空数组', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.executionStepsRef.current).toEqual([]);
    });

    it('应该初始化 streamingContentRef 为空字符串', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.streamingContentRef.current).toBe('');
    });

    it('应该初始化 streamingStepsRef 为空数组', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.streamingStepsRef.current).toEqual([]);
    });

    it('应该初始化 userScrolledUpRef 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.userScrolledUpRef.current).toBe(false);
    });

    it('应该初始化 lastScrollTimeRef 为 0', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.lastScrollTimeRef.current).toBe(0);
    });

    it('应该初始化 isLoadingHistoryRef 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isLoadingHistoryRef.current).toBe(false);
    });

    it('应该初始化 logFlagsRef 为正确的初始值', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.logFlagsRef.current).toEqual({
        chunkFirstDone: false,
        showStepsFalseDone: false,
        showStepsTrueDone: false,
      });
    });

    it('应该初始化 hasReceivedInterruptEventRef 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.hasReceivedInterruptEventRef.current).toBe(false);
    });

    it('应该初始化 interruptInProgressRef 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.interruptInProgressRef.current).toBe(false);
    });
  });

  describe('4. 状态同步测试', () => {
    it('应该同步 messages 到 messagesRef', () => {
      const { result } = renderHook(() => useChatState());
      const testMessage = { id: '1', role: 'user' as const, content: 'test', timestamp: new Date() };
      
      act(() => {
        result.current.setMessages([testMessage]);
      });
      
      expect(result.current.messagesRef.current).toEqual([testMessage]);
    });

    it('应该同步 sessionId 到 currentSessionIdRef', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setSessionId('sync-test-id');
      });
      
      expect(result.current.currentSessionIdRef.current).toBe('sync-test-id');
    });

    it('应该同步 isPaused 到 isPausedRef', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setIsPaused(true);
      });
      
      expect(result.current.isPausedRef.current).toBe(true);
    });

    it('应该同步 messages.length 到 messagesCountRef', () => {
      const { result } = renderHook(() => useChatState());
      const testMessage = { id: '1', role: 'user' as const, content: 'test', timestamp: new Date() };
      
      act(() => {
        result.current.setMessages([testMessage, testMessage]);
      });
      
      expect(result.current.messagesCountRef.current).toBe(2);
    });
  });

  describe('5. 渲染状态测试', () => {
    it('应该初始化 isRenderingMessages 为 false', () => {
      const { result } = renderHook(() => useChatState());
      expect(result.current.isRenderingMessages).toBe(false);
    });

    it('应该正确更新 isRenderingMessages', () => {
      const { result } = renderHook(() => useChatState());
      
      act(() => {
        result.current.setIsRenderingMessages(true);
      });
      
      expect(result.current.isRenderingMessages).toBe(true);
    });
  });
});
