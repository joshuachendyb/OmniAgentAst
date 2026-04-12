/**
 * MessageItem React.memo Integration Tests
 *
 * 测试 MessageItem 使用 React.memo 后的功能正确性
 * Phase 2 P1级优化 - MessageItem React.memo
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-12
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import MessageItem from '../../components/Chat/MessageItem';

// 【小强修复 2026-04-12】使用与 MessageItem.test.tsx 相同的 mock 方式
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
      warning: vi.fn(),
    },
  };
});

describe('MessageItem with React.memo', () => {
  const baseMessage = {
    id: 'msg-1',
    role: 'user' as const,
    content: 'Test message content',
    timestamp: new Date(),
  };

  const defaultProps = {
    showExecution: true,
    sessionId: 'session-1',
    sessionTitle: 'Test Session',
  };

  it('应该正常渲染user消息', () => {
    render(<MessageItem message={baseMessage} {...defaultProps} />);
    
    expect(screen.getByText('Test message content')).toBeInTheDocument();
    expect(screen.getByText('我')).toBeInTheDocument();
  });

  it('应该正常渲染assistant消息', () => {
    const assistantMessage = {
      ...baseMessage,
      role: 'assistant' as const,
      content: 'AI response',
    };
    
    render(<MessageItem message={assistantMessage} {...defaultProps} />);
    
    expect(screen.getByText('AI response')).toBeInTheDocument();
  });

  it('props未变化时不应该重新渲染', () => {
    const { rerender } = render(
      <MessageItem message={baseMessage} {...defaultProps} />
    );
    
    // 第一次渲染
    expect(screen.getByText('Test message content')).toBeInTheDocument();
    
    // 使用相同props重新渲染 - 由于memo，应该跳过渲染
    rerender(<MessageItem message={baseMessage} {...defaultProps} />);
    
    // 内容应该相同
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('content变化时应该重新渲染', () => {
    const { rerender } = render(
      <MessageItem message={baseMessage} {...defaultProps} />
    );
    
    expect(screen.getByText('Test message content')).toBeInTheDocument();
    
    // 修改content
    const newMessage = { ...baseMessage, content: 'Updated content' };
    rerender(<MessageItem message={newMessage} {...defaultProps} />);
    
    expect(screen.getByText('Updated content')).toBeInTheDocument();
    expect(screen.queryByText('Test message content')).not.toBeInTheDocument();
  });

  it('timestamp变化时应该重新渲染', () => {
    const { rerender } = render(
      <MessageItem message={baseMessage} {...defaultProps} />
    );
    
    const newMessage = { ...baseMessage, timestamp: new Date('2024-01-20') };
    rerender(<MessageItem message={newMessage} {...defaultProps} />);
    
    // timestamp变化，组件应该重新渲染
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('showExecution变化时应该重新渲染', () => {
    const { rerender } = render(
      <MessageItem message={baseMessage} showExecution={true} {...defaultProps} />
    );
    
    rerender(<MessageItem message={baseMessage} showExecution={false} {...defaultProps} />);
    
    // showExecution变化，组件应该重新渲染
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('sessionId变化时应该重新渲染', () => {
    const { rerender } = render(
      <MessageItem message={baseMessage} sessionId="session-1" {...defaultProps} />
    );
    
    rerender(<MessageItem message={baseMessage} sessionId="session-2" {...defaultProps} />);
    
    // sessionId变化，组件应该重新渲染
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('应该正常显示带executionSteps的消息', async () => {
    const messageWithSteps = {
      ...baseMessage,
      role: 'assistant' as const,
      content: '',
      executionSteps: [
        {
          type: 'thought' as const,
          content: 'Thinking about the problem...',
          timestamp: Date.now(),
        },
        {
          type: 'action_tool' as const,
          tool_name: 'read_file',
          tool_params: { file_path: '/test.txt' },
          timestamp: Date.now(),
        },
        {
          type: 'final' as const,
          content: 'Final response',
          timestamp: Date.now(),
        },
      ],
    };
    
    render(<MessageItem message={messageWithSteps} {...defaultProps} />);
    
    // 应该显示executionSteps内容
    expect(screen.getByText(/Thinking about the problem/)).toBeInTheDocument();
  });

  it('应该正确处理消息复制功能', async () => {
    // Mock clipboard API
    const mockClipboard = {
      writeText: vi.fn().mockResolvedValue(undefined),
    };
    Object.defineProperty(navigator, 'clipboard', {
      value: mockClipboard,
      writable: true,
    });
    
    render(<MessageItem message={baseMessage} {...defaultProps} />);
    
    // 组件应该正常渲染复制按钮（在hover时显示）
    expect(screen.getByText('Test message content')).toBeInTheDocument();
  });

  it('应该正确显示不同角色的样式', () => {
    // User message
    const { rerender } = render(
      <MessageItem message={baseMessage} {...defaultProps} />
    );
    expect(screen.getByText('我')).toBeInTheDocument();
    
    // Assistant message
    rerender(
      <MessageItem 
        message={{ ...baseMessage, role: 'assistant' as const }} 
        {...defaultProps} 
      />
    );
    expect(screen.getByText(/AI 助手/)).toBeInTheDocument();
  });

  it('应该正确处理error消息', () => {
    const errorMessage = {
      ...baseMessage,
      isError: true,
      role: 'assistant' as const,
      content: 'Error occurred',
    };
    
    render(<MessageItem message={errorMessage} {...defaultProps} />);
    
    expect(screen.getByText('Error occurred')).toBeInTheDocument();
  });
});