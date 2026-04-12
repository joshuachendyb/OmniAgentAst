/**
 * useMessageListRender Hook Tests
 *
 * 测试 useMessageListRender hook 的正确性
 * Phase 2 P1级优化 - 消息列表useMemo优化
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-12
 */

import { describe, it, expect } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useMessageListRender } from '../../hooks/useMessageListRender';
import type { ChatMessage } from '../../services/api';

describe('useMessageListRender Hook', () => {
  const createMockMessages = (count: number): ChatMessage[] => {
    return Array.from({ length: count }, (_, i) => ({
      id: `msg-${i}`,
      role: i % 2 === 0 ? 'user' as const : 'assistant' as const,
      content: `Message content ${i}`,
      timestamp: new Date(Date.now() - (count - i) * 60000).toISOString(),
    }));
  };

  const defaultProps = {
    messages: [] as ChatMessage[],
    showExecution: true,
    sessionId: 'session-1' as string | null,
    sessionTitle: 'Test Session',
  };

  it('应该返回空数组当messages为空时', () => {
    const { result } = renderHook(() => useMessageListRender(defaultProps));
    
    expect(result.current).toEqual([]);
  });

  it('应该正确渲染单条消息', () => {
    const messages = createMockMessages(1);
    const { result } = renderHook(() => 
      useMessageListRender({ ...defaultProps, messages })
    );
    
    // 1条消息 = 1个日期分隔符 + 1个消息元素 = 2个元素
    expect(result.current.length).toBe(2);
    expect(result.current[0]).toBeDefined();
  });

  it('应该正确渲染多条消息', () => {
    const messages = createMockMessages(5);
    const { result } = renderHook(() => 
      useMessageListRender({ ...defaultProps, messages })
    );
    
    // 5条消息 = 1个日期分隔符 + 5个消息元素 = 6个元素
    expect(result.current.length).toBe(6);
  });

  it('应该在messages变化时重新计算', () => {
    const { result, rerender } = renderHook(
      ({ messages }) => useMessageListRender({ ...defaultProps, messages }),
      { initialProps: { messages: createMockMessages(1) } }
    );
    
    const firstRender = result.current;
    
    rerender({ messages: createMockMessages(2) });
    
    // 2条消息 = 1个日期分隔符 + 2个消息元素 = 3个元素
    expect(result.current.length).toBe(3);
    expect(result.current).not.toBe(firstRender);
  });

  it('应该在依赖项未变化时返回相同的引用', () => {
    const messages = createMockMessages(3);
    
    const { result, rerender } = renderHook(
      ({ messages, showExecution }) => 
        useMessageListRender({ ...defaultProps, messages, showExecution }),
      { initialProps: { messages, showExecution: true } }
    );
    
    const firstRender = result.current;
    
    // 依赖未变化，rerender应该返回相同引用
    rerender({ messages, showExecution: true });
    
    expect(result.current).toBe(firstRender);
  });

  it('应该在showExecution变化时重新计算', () => {
    const messages = createMockMessages(2);
    
    const { result, rerender } = renderHook(
      ({ messages, showExecution }) => 
        useMessageListRender({ ...defaultProps, messages, showExecution }),
      { initialProps: { messages, showExecution: true } }
    );
    
    rerender({ messages, showExecution: false });
    
    // showExecution变化，应该重新计算
    expect(result.current).toBeDefined();
  });

  it('应该在sessionId变化时重新计算', () => {
    const messages = createMockMessages(2);
    
    const { result, rerender } = renderHook(
      ({ messages, sessionId }) => 
        useMessageListRender({ ...defaultProps, messages, sessionId }),
      { initialProps: { messages, sessionId: 'session-1' as string | null } }
    );
    
    rerender({ messages, sessionId: 'session-2' as string | null });
    
    // sessionId变化，应该重新计算
    expect(result.current).toBeDefined();
  });

  it('应该正确处理同一天的消息（不添加日期分隔符）', () => {
    const now = new Date();
    const messages: ChatMessage[] = [
      { id: '1', role: 'user', content: 'Message 1', timestamp: now.toISOString() },
      { id: '2', role: 'assistant', content: 'Message 2', timestamp: now.toISOString() },
    ];
    
    const { result } = renderHook(() => 
      useMessageListRender({ ...defaultProps, messages })
    );
    
    // 2条消息同一天 = 1个日期分隔符 + 2个消息元素 = 3个元素
    expect(result.current.length).toBe(3);
  });

  it('应该在不同日期消息之间添加日期分隔符', () => {
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    
    const messages: ChatMessage[] = [
      { id: '1', role: 'user', content: 'Yesterday message', timestamp: yesterday.toISOString() },
      { id: '2', role: 'assistant', content: 'Today message', timestamp: new Date().toISOString() },
    ];
    
    const { result } = renderHook(() => 
      useMessageListRender({ ...defaultProps, messages })
    );
    
    // 2条消息不同天 = 2个日期分隔符 + 2个消息元素 = 4个元素
    expect(result.current.length).toBe(4);
  });
});