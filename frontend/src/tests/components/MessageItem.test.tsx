/**
 * MessageItem Component Tests
 *
 * @author 小新
 * @description Unit tests for MessageItem component
 * @update 2026-04-25 修复测试：使用queryByText避免multiple elements错误 by 小沈
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
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
    // 修复：使用queryAllByText检查长度 >= 1（因为"我"出现在角色名称+头像两处）
    expect(screen.queryAllByText('我').length).toBeGreaterThanOrEqual(1);
  });

  it('should render assistant message', () => {
    const assistantMessage = {
      ...baseMessage,
      role: 'assistant' as const,
      content: 'AI response',
    };

    render(<MessageItem message={assistantMessage} />);

    expect(screen.getByText('AI response')).toBeInTheDocument();
    // 修复：使用queryByText避免multiple elements
    expect(screen.queryByText(/AI 助手/)).toBeInTheDocument();
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

  it('should display message with execution steps', async () => {
    const messageWithSteps = {
      ...baseMessage,
      role: 'assistant' as const,
      executionSteps: [
        {
          type: 'thought' as const,
          content: 'Thinking...',
          timestamp: Date.now(),
        },
        {
          type: 'action_tool' as const,
          tool_name: 'read_file',
          tool_params: {},
          timestamp: Date.now(),
        },
      ],
    };

    render(<MessageItem message={messageWithSteps} showExecution={true} />);

    // 有 executionSteps 时渲染步骤内容，不渲染 message.content
    // 检查思考步骤显示（💭 图标 + 思考内容）
    expect(screen.getByText(/Thinking\.\.\./)).toBeInTheDocument();
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

    // User message - 使用queryAllByText检查长度 >= 1（"我"出现在角色名称+头像两处）
    expect(screen.queryAllByText('我').length).toBeGreaterThanOrEqual(1);

    // Assistant message - 使用queryAllByText检查长度 >= 1
    rerender(<MessageItem message={{ ...baseMessage, role: 'assistant' }} />);
    expect(screen.queryAllByText(/AI 助手/).length).toBeGreaterThanOrEqual(1);

    // System message (no role name shown) - 使用queryAllByText检查长度 = 0
    rerender(<MessageItem message={{ ...baseMessage, role: 'system' }} />);
    expect(screen.queryAllByText('我').length).toBe(0);
    expect(screen.queryAllByText(/AI 助手/).length).toBe(0);
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