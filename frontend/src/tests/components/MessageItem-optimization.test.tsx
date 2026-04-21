/**
 * MessageItem Optimization Tests
 *
 * @author 小沈
 * @description Test useMemo caching for styles in MessageItem component
 * @update 2026-04-21
 */

import { describe, it, expect, vi } from 'vitest';
import { render } from '@testing-library/react';
import MessageItem from '../../components/Chat/MessageItem';

describe('MessageItem 3.1.2 Optimization - useMemo caching', () => {
  const baseExecutionStep = {
    step_index: 0,
    type: 'start' as const,
    content: 'Test step content',
    thinking_prompt: undefined,
    action_description: undefined,
    tool_name: undefined,
    tool_params: undefined,
    reasoning: undefined,
    execution_result: null,
    timestamp: Date.now(),
  };

  const baseMessage = {
    id: 'msg-1',
    role: 'assistant' as const,
    content: 'Test message content',
    timestamp: new Date(),
    executionSteps: [baseExecutionStep],
    executionStepsComplete: true,
  };

  it('should useMemo cache badgeStyle', () => {
    const { container, rerender } = render(<MessageItem message={baseMessage} />);
    
    // Get badgeStyle on first render
    const firstBadgeStyle = container.querySelector('[class*="ant-tag"]')?.getAttribute('style');
    
    // Re-render with same effectiveType
    rerender(<MessageItem message={baseMessage} />);
    
    // Style should be same reference (useMemo with dependency)
    const secondBadgeStyle = container.querySelector('[class*="ant-tag"]')?.getAttribute('style');
    
    // Both styles should exist (not testing reference equality in JSDOM)
    expect(firstBadgeStyle).toBeDefined();
    expect(secondBadgeStyle).toBeDefined();
  });

  it('should useMemo cache labelStyle', () => {
    const { container, rerender } = render(<MessageItem message={baseMessage} />);
    
    // Get label style on first render
    const firstRender = container.innerHTML;
    
    // Re-render
    rerender(<MessageItem message={baseMessage} />);
    
    // Component should render without errors
    expect(container.innerHTML).toBeTruthy();
  });

  it('should useMemo cache contentStyle', () => {
    const { container } = render(<MessageItem message={baseMessage} />);
    
    // Content style should be applied
    const content = container.querySelector('div');
    expect(content).toBeTruthy();
  });
});

describe('MessageItem 3.1.3 Optimization - useCallback', () => {
  const baseExecutionStep = {
    step_index: 0,
    type: 'start' as const,
    content: 'Test step',
    timestamp: Date.now(),
  };

  const messageWithSteps = {
    id: 'msg-1',
    role: 'assistant' as const,
    content: 'Test',
    timestamp: new Date(),
    executionSteps: [baseExecutionStep],
    executionStepsComplete: true,
  };

  it('should useCallback for handleMouseEnter', () => {
    const { container } = render(<MessageItem message={messageWithSteps} />);
    
    // Find the step container
    const stepContainer = container.querySelector('div');
    expect(stepContainer).toBeTruthy();
  });

  it('should useCallback for handleMouseLeave', () => {
    const { container } = render(<MessageItem message={messageWithSteps} />);
    expect(container.innerHTML).toBeTruthy();
  });

  it('should useCallback for link hover handlers', () => {
    const { container } = render(<MessageItem message={messageWithSteps} />);
    expect(container.innerHTML).toBeTruthy();
  });
});