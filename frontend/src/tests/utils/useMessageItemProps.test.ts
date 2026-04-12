/**
 * useMessageItemProps Hook Tests
 *
 * 测试 areMessageItemPropsEqual 比较函数的正确性
 * Phase 2 P1级优化 - MessageItem React.memo
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-12
 */

import { describe, it, expect } from 'vitest';
import { areMessageItemPropsEqual } from '../../hooks/useMessageItemProps';
import type { ChatMessage } from '../../services/api';

describe('useMessageItemProps - areMessageItemPropsEqual', () => {
  const createMockProps = (overrides = {}) => ({
    message: {
      id: 'msg-1',
      role: 'user' as const,
      content: 'Test content',
      timestamp: '2024-01-15T10:30:00Z',
      ...overrides.message,
    },
    showExecution: true,
    sessionId: 'session-1',
    sessionTitle: 'Test Session',
  });

  it('应该返回true当所有props相等时', () => {
    const prev = createMockProps();
    const next = createMockProps();
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(true);
  });

  it('应该返回false当message.content不同时', () => {
    const prev = createMockProps({ message: { content: 'Old content' } });
    const next = createMockProps({ message: { content: 'New content' } });
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(false);
  });

  it('应该返回false当message.role不同时', () => {
    const prev = createMockProps({ message: { role: 'user' as const } });
    const next = createMockProps({ message: { role: 'assistant' as const } });
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(false);
  });

  it('应该返回false当message.timestamp不同时', () => {
    const prev = createMockProps({ message: { timestamp: '2024-01-15T10:30:00Z' } });
    const next = createMockProps({ message: { timestamp: '2024-01-15T11:30:00Z' } });
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(false);
  });

  it('应该返回false当showExecution不同时', () => {
    const prev = createMockProps();
    const next = { ...prev, showExecution: false };
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(false);
  });

  it('应该返回false当sessionId不同时', () => {
    const prev = createMockProps();
    const next = { ...prev, sessionId: 'session-2' };
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(false);
  });

  it('应该返回false当sessionTitle不同时', () => {
    const prev = createMockProps();
    const next = { ...prev, sessionTitle: 'Different Session' };
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(false);
  });

  it('应该正确处理assistant角色消息', () => {
    const prev = createMockProps({ message: { role: 'assistant' as const, content: 'AI response' } });
    const next = createMockProps({ message: { role: 'assistant' as const, content: 'AI response' } });
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(true);
  });

  it('应该正确处理system角色消息', () => {
    const prev = createMockProps({ message: { role: 'system' as const, content: 'System message' } });
    const next = createMockProps({ message: { role: 'system' as const, content: 'System message' } });
    
    expect(areMessageItemPropsEqual(prev, next)).toBe(true);
  });

  it('应该处理executionSteps属性变化', () => {
    const prev = createMockProps({ 
      message: { 
        executionSteps: [
          { type: 'thought', content: 'Thinking', timestamp: Date.now() }
        ] as any
      } 
    });
    const next = createMockProps({ 
      message: { 
        executionSteps: [
          { type: 'thought', content: 'Thinking', timestamp: Date.now() },
          { type: 'final', content: 'Done', timestamp: Date.now() }
        ] as any
      } 
    });
    
    // executionSteps不在比较范围内，content相同应该返回true
    expect(areMessageItemPropsEqual(prev, next)).toBe(true);
  });
});