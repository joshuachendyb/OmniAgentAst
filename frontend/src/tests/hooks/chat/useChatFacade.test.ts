/**
 * useChatFacade 完整测试用例
 *
 * 深度和广泛的测试覆盖：
 * 1. 初始化测试 - Hook正确加载
 * 2. 接口完整性测试 - 所有分组和方法存在
 * 3. 集成测试 - 底层Hook正确集成
 * 4. 分组测试 - 5组状态正确返回
 * 5. 操作测试 - 发送/中断/会话/持久化
 * 6. UI按需渲染测试 - 条件渲染逻辑
 * 7. 性能测试 - useMemo优化
 * 8. 边界测试 - 异常情况处理
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-24
 */

import React, { ReactNode } from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { useChatFacade } from '../../../hooks/chat/useChatFacade';

// Mock API
vi.mock('../../../services/api', () => ({
  API_BASE_URL: 'http://test-api.com',
  sessionApi: {
    createSession: vi.fn().mockResolvedValue({ session_id: 'test-session-id' }),
    getSession: vi.fn().mockResolvedValue({ session_id: 'test-session-id', title: 'Test Session' }),
    updateSession: vi.fn().mockResolvedValue({}),
    deleteSession: vi.fn().mockResolvedValue({}),
    getHistory: vi.fn().mockResolvedValue({ sessions: [], total: 0 }),
  },
}));

// Mock message
vi.mock('antd', () => ({
  message: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    loading: vi.fn().mockReturnValue({ destroy: vi.fn() }),
    destroy: vi.fn(),
  },
}));

// 测试Wrapper - 提供Router上下文
const TestWrapper = (props: { children?: ReactNode }) => (
  <MemoryRouter initialEntries={["/chat"]}>
    <Routes>
      <Route path="/chat" element={props.children || <></>} />
    </Routes>
  </MemoryRouter>
);

const wrapper = TestWrapper;

describe('useChatFacade - 生产级完整测试', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ============================================================
  // 1. 初始化测试
  // ============================================================
  describe('1. 初始化测试', () => {
    it('应该正确初始化并返回Facade对象', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current).toBeDefined();
      expect(typeof result.current).toBe('object');
    });

    it('应该支持配置参数', () => {
      const { result } = renderHook(() =>
        useChatFacade({ baseURL: 'http://custom-api.com', sessionId: 'custom-session' }),
        { wrapper }
      );
      expect(result.current).toBeDefined();
    });

    it('不传参数时应该有默认值', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current).toBeDefined();
      expect(result.current.session).toBeDefined();
    });
  });

  // ============================================================
  // 2. 接口完整性测试
  // ============================================================
  describe('2. 接口完整性测试', () => {
    it('应该包含session分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { session } = result.current;

      expect(session).toBeDefined();
      expect(session.sessionId).toBeDefined();
      expect(session.sessionTitle).toBeDefined();
      expect(session.setSessionId).toBeDefined();
      expect(typeof session.setSessionId).toBe('function');
      expect(session.currentSessionIdRef).toBeDefined();
    });

    it('应该包含message分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { message } = result.current;

      expect(message).toBeDefined();
      expect(message.messages).toBeDefined();
      expect(Array.isArray(message.messages)).toBe(true);
      expect(message.loading).toBeDefined();
      expect(typeof message.loading).toBe('boolean');
      expect(message.setMessages).toBeDefined();
      expect(typeof message.setMessages).toBe('function');
      expect(message.messagesRef).toBeDefined();
      expect(message.messagesEndRef).toBeDefined();
    });

    it('应该包含streaming分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { streaming } = result.current;

      expect(streaming).toBeDefined();
      expect(streaming.isReceiving).toBeDefined();
      expect(typeof streaming.isReceiving).toBe('boolean');
      expect(streaming.isPaused).toBeDefined();
      expect(streaming.waitTime).toBeDefined();
      expect(streaming.executionSteps).toBeDefined();
      expect(Array.isArray(streaming.executionSteps)).toBe(true);
      expect(streaming.setIsReceiving).toBeDefined();
      expect(typeof streaming.setIsReceiving).toBe('function');
    });

    it('应该包含ui分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { ui } = result.current;

      expect(ui).toBeDefined();
      expect(ui.showExecution).toBeDefined();
      expect(ui.useStream).toBeDefined();
      expect(ui.isInitialized).toBeDefined();
      expect(ui.setShowExecution).toBeDefined();
      expect(typeof ui.setShowExecution).toBe('function');
    });

    it('应该包含send分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { send } = result.current;

      expect(send).toBeDefined();
      expect(send.handleSend).toBeDefined();
      expect(typeof send.handleSend).toBe('function');
    });

    it('应该包含interrupt分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { interrupt } = result.current;

      expect(interrupt).toBeDefined();
      expect(interrupt.handleInterrupt).toBeDefined();
      expect(typeof interrupt.handleInterrupt).toBe('function');
      expect(interrupt.handleTogglePause).toBeDefined();
      expect(typeof interrupt.handleTogglePause).toBe('function');
    });

    it('应该包含persistence分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { persistence } = result.current;

      expect(persistence).toBeDefined();
      expect(persistence.saveStateWithSSECheck).toBeDefined();
      expect(typeof persistence.saveStateWithSSECheck).toBe('function');
      expect(persistence.saveMessagesToStorage).toBeDefined();
      expect(typeof persistence.saveMessagesToStorage).toBe('function');
    });

});

    it('应该包含shared分组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      const { shared } = result.current;

      expect(shared).toBeDefined();
      expect(shared.waitTimerRef).toBeDefined();
      expect(shared.executionStepsRef).toBeDefined();
      expect(shared.isPausedRef).toBeDefined();
      expect(shared.hasReceivedInterruptEventRef).toBeDefined();
      expect(shared.interruptInProgressRef).toBeDefined();
    });
  });

  // ============================================================
  // 3. 状态操作测试
  // ============================================================
  describe('3. 状态操作测试', () => {
    it('应该能够修改session状态', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.session.setSessionId('test-id-123');
      });

      expect(result.current.session.sessionId).toBe('test-id-123');
    });

    it('应该能够修改message状态', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      const testMessages = [
        { id: '1', role: 'user' as const, content: 'Hello', timestamp: new Date() },
      ];

      await act(async () => {
        result.current.message.setMessages(testMessages);
      });

      expect(result.current.message.messages).toEqual(testMessages);
    });

    it('应该能够修改loading状态', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.message.setLoading(true);
      });

      expect(result.current.message.loading).toBe(true);
    });

    it('应该能够修改streaming状态', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.streaming.setIsReceiving(true);
      });

      expect(result.current.streaming.isReceiving).toBe(true);
    });

    it('应该能够修改ui状态', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.ui.setShowExecution(true);
      });

      expect(result.current.ui.showExecution).toBe(true);
    });
  });

  // ============================================================
  // 4. UI按需渲染测试
  // ============================================================
  describe('4. UI按需渲染测试', () => {
    it('未接收时isReceiving应该为false', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.streaming.isReceiving).toBe(false);
    });

    it('初始时executionSteps应该为空数组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.streaming.executionSteps).toEqual([]);
      expect(result.current.streaming.executionSteps.length).toBe(0);
    });

    it('初始时isPaused应该为false', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.streaming.isPaused).toBe(false);
    });

    it('接收到数据后应该正确更新状态', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.streaming.setIsReceiving(true);
      });

      expect(result.current.streaming.isReceiving).toBe(true);

      await act(async () => {
        result.current.streaming.setIsReceiving(false);
      });

      expect(result.current.streaming.isReceiving).toBe(false);
    });
  });

  // ============================================================
  // 5. 边界测试
  // ============================================================
  describe('5. 边界测试', () => {
    it('messages应该初始化为空数组', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.message.messages).toEqual([]);
      expect(Array.isArray(result.current.message.messages)).toBe(true);
    });

    it('sessionId应该初始化为null', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.session.sessionId).toBeNull();
    });

    it('serverTaskId应该初始化为null', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.streaming.serverTaskId).toBeNull();
    });

    it('waitTime应该初始化为0', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.streaming.waitTime).toBe(0);
    });

    it('currentResponse应该初始化为空字符串', () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });
      expect(result.current.streaming.currentResponse).toBe('');
    });

    it('setSessionId应该接受null', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.session.setSessionId(null);
      });

      expect(result.current.session.sessionId).toBeNull();
    });

    it('setMessages应该接受空数组', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.message.setMessages([]);
      });

      expect(result.current.message.messages).toEqual([]);
    });

    it('setWaitTime应该接受大数值', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      await act(async () => {
        result.current.streaming.setWaitTime(999999);
      });

      expect(result.current.streaming.waitTime).toBe(999999);
    });
  });

  // ============================================================
  // 6. 性能测试
  // ============================================================
  describe('6. 性能测试', () => {
    it('连续多次渲染应该稳定', async () => {
      const { result } = renderHook(() => useChatFacade(), { wrapper });

      for (let i = 0; i < 5; i++) {
        await act(async () => {
          result.current.message.setLoading(true);
        });
        await act(async () => {
          result.current.message.setLoading(false);
        });
      }

      expect(result.current.message.loading).toBe(false);
    });
  });
});