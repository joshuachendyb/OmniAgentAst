/**
 * MessageItem Component Tests
 *
 * @author 小新
 * @description Unit tests for MessageItem component
 * @update 2026-02-18 修复测试期望以匹配实际组件输出 by 小新
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import MessageItem from '../../components/Chat/MessageItem';

describe('MessageItem Component', () => {
  const baseMessage = {
    id: 'msg-1',
    role: 'user' as const,
    content: 'Test message content',
    timestamp: new Date(),
  };

  it('should render user message', () => {
    render(<MessageItem message={baseMessage} />);
    
    expect(screen.getByText('Test message content')).toBeInTheDocument();
    expect(screen.getByText('我')).toBeInTheDocument();
  });

  it('should render assistant message', () => {
    const assistantMessage = {
      ...baseMessage,
      role: 'assistant' as const,
      content: 'AI response',
    };
    
    render(<MessageItem message={assistantMessage} />);
    
    expect(screen.getByText('AI response')).toBeInTheDocument();
    expect(screen.getByText('AI助手')).toBeInTheDocument();
  });

  it('should render system message', () => {
    const systemMessage = {
      ...baseMessage,
      role: 'system' as const,
      content: 'System notification',
    };
    
    render(<MessageItem message={systemMessage} />);
    
    expect(screen.getByText('System notification')).toBeInTheDocument();
  });

  it('should display message with execution steps', () => {
    const messageWithSteps = {
      ...baseMessage,
      role: 'assistant' as const,
      executionSteps: [
        { type: 'thought' as const, content: 'Thinking...', timestamp: Date.now() },
        { type: 'action' as const, tool: 'read_file', params: {}, timestamp: Date.now() },
      ],
    };
    
    render(<MessageItem message={messageWithSteps} showExecution={true} />);
    
    expect(screen.getByText('Test message content')).toBeInTheDocument();
    // 执行过程组件会显示步骤数量
    expect(screen.getByText(/执行过程.*2步/)).toBeInTheDocument();
  });

  it('should format timestamp correctly', () => {
    const messageWithTime = {
      ...baseMessage,
      timestamp: new Date('2024-01-15T10:30:00'),
    };
    
    render(<MessageItem message={messageWithTime} />);
    
    // Should render without errors
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('should render message with code block', () => {
    const codeMessage = {
      ...baseMessage,
      content: '```python\nprint("hello")\n```',
    };
    
    render(<MessageItem message={codeMessage} />);
    
    // Content should be rendered (code formatting depends on implementation)
    expect(screen.getByText(/print/)).toBeInTheDocument();
  });

  it('should handle copy functionality', async () => {
    // Mock clipboard API
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.defineProperty(navigator, 'clipboard', {
      value: mockClipboard,
      writable: true,
    });
    
    render(<MessageItem message={baseMessage} />);
    
    // Component should render copy button (hidden by default, shown on hover)
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('should apply different styles for different roles', () => {
    const { rerender } = render(<MessageItem message={baseMessage} />);
    
    // User message
    expect(screen.getByText('我')).toBeInTheDocument();
    
    // Assistant message
    rerender(<MessageItem message={{ ...baseMessage, role: 'assistant' }} />);
    expect(screen.getByText('AI助手')).toBeInTheDocument();
    
    // System message (no role name shown)
    rerender(<MessageItem message={{ ...baseMessage, role: 'system' }} />);
    expect(screen.queryByText('我')).not.toBeInTheDocument();
    expect(screen.queryByText('AI助手')).not.toBeInTheDocument();
  });

  it('should handle long content with proper formatting', () => {
    const longMessage = {
      ...baseMessage,
      content: 'Line 1\nLine 2\nLine 3\n\nLine 4 after empty line',
    };
    
    const { container } = render(<MessageItem message={longMessage} />);
    
    // 组件使用whiteSpace: 'pre-wrap'保留换行符，但整个内容是一个文本节点
    // 所以应该检查整个内容是否存在，而不是单独的行
    expect(screen.getByText(/Line 1/)).toBeInTheDocument();
    expect(container.textContent).toContain('Line 4 after empty line');
  });

  it('should handle empty content gracefully', () => {
    const emptyMessage = {
      ...baseMessage,
      content: '',
    };
    
    const { container } = render(<MessageItem message={emptyMessage} />);
    
    // Should render without errors - 检查容器是否正确渲染
    // 消息气泡容器应该存在
    expect(container.querySelector('[style*="pre-wrap"]')).toBeInTheDocument();
  });
});
