/**
 * MessageItem Component Tests
 * 
 * @author 小新
 * @description Unit tests for MessageItem component
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import MessageItem from '../../components/Chat/MessageItem';
import type { ChatMessage } from '../../services/api';

describe('MessageItem Component', () => {
  const baseMessage: ChatMessage & { id: string; timestamp: Date } = {
    id: '1',
    role: 'user',
    content: 'Hello, AI!',
    timestamp: new Date('2026-02-17T10:00:00'),
  };

  it('should render user message correctly', () => {
    render(<MessageItem message={baseMessage} />);
    
    expect(screen.getByText('Hello, AI!')).toBeInTheDocument();
    expect(screen.getByText('用户')).toBeInTheDocument();
  });

  it('should render assistant message correctly', () => {
    const assistantMessage = {
      ...baseMessage,
      role: 'assistant' as const,
      content: 'Hello! How can I help you?',
    };
    
    render(<MessageItem message={assistantMessage} />);
    
    expect(screen.getByText('Hello! How can I help you?')).toBeInTheDocument();
    expect(screen.getByText('AI助手')).toBeInTheDocument();
  });

  it('should render system message correctly', () => {
    const systemMessage = {
      ...baseMessage,
      role: 'system' as const,
      content: 'System notification',
    };
    
    render(<MessageItem message={systemMessage} />);
    
    expect(screen.getByText('System notification')).toBeInTheDocument();
    expect(screen.getByText('系统')).toBeInTheDocument();
  });

  it('should display timestamp in correct format', () => {
    render(<MessageItem message={baseMessage} />);
    
    const timeString = baseMessage.timestamp.toLocaleTimeString();
    expect(screen.getByText(timeString)).toBeInTheDocument();
  });

  it('should show copy button on hover', async () => {
    render(<MessageItem message={baseMessage} />);
    
    const messageElement = screen.getByText('Hello, AI!');
    fireEvent.mouseEnter(messageElement.closest('div')!);
    
    // Copy button should be visible after hover
    const copyButton = screen.getByRole('button', { name: /复制/i });
    expect(copyButton).toBeInTheDocument();
  });

  it('should copy content to clipboard when copy button clicked', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: writeTextMock },
      writable: true,
    });

    render(<MessageItem message={baseMessage} />);
    
    // Hover to show copy button
    const messageElement = screen.getByText('Hello, AI!');
    fireEvent.mouseEnter(messageElement.closest('div')!);
    
    // Click copy button
    const copyButton = screen.getByRole('button', { name: /复制/i });
    fireEvent.click(copyButton);

    // Verify clipboard was called
    expect(writeTextMock).toHaveBeenCalledWith('Hello, AI!');
  });

  it('should apply different styles for different roles', () => {
    const { container: userContainer } = render(
      <MessageItem message={baseMessage} />
    );
    
    // User message should have blue gradient indicator
    expect(userContainer.querySelector('.ant-avatar')).toHaveStyle({
      background: expect.stringContaining('linear-gradient'),
    });

    // Cleanup
    userContainer.remove();

    const assistantMessage = {
      ...baseMessage,
      role: 'assistant' as const,
    };
    
    const { container: assistantContainer } = render(
      <MessageItem message={assistantMessage} />
    );
    
    // Assistant message should have green gradient indicator
    expect(assistantContainer.querySelector('.ant-avatar')).toHaveStyle({
      background: expect.stringContaining('linear-gradient'),
    });
  });

  it('should render markdown content when provided', () => {
    const markdownMessage = {
      ...baseMessage,
      content: '# Heading\n\n**Bold text**',
    };
    
    render(<MessageItem message={markdownMessage} />);
    
    expect(screen.getByText('Heading')).toBeInTheDocument();
    expect(screen.getByText('Bold text')).toBeInTheDocument();
  });

  it('should handle code blocks in content', () => {
    const codeMessage = {
      ...baseMessage,
      content: '```javascript\nconst x = 1;\n```',
    };
    
    render(<MessageItem message={codeMessage} />);
    
    // Code block should be rendered
    expect(screen.getByText(/const x = 1;/)).toBeInTheDocument();
  });

  it('should display execution steps when provided', () => {
    const messageWithSteps = {
      ...baseMessage,
      role: 'assistant' as const,
      executionSteps: [
        {
          type: 'thought' as const,
          content: 'I need to think about this',
          timestamp: Date.now(),
        },
        {
          type: 'action' as const,
          tool: 'read_file',
          timestamp: Date.now(),
        },
      ],
    };
    
    render(<MessageItem message={messageWithSteps} showExecution={true} />);
    
    expect(screen.getByText('I need to think about this')).toBeInTheDocument();
    expect(screen.getByText(/read_file/)).toBeInTheDocument();
  });

  it('should not display execution steps when showExecution is false', () => {
    const messageWithSteps = {
      ...baseMessage,
      role: 'assistant' as const,
      executionSteps: [
        {
          type: 'thought' as const,
          content: 'I need to think about this',
          timestamp: Date.now(),
        },
      ],
    };
    
    render(<MessageItem message={messageWithSteps} showExecution={false} />);
    
    expect(screen.queryByText('I need to think about this')).not.toBeInTheDocument();
  });

  it('should handle long content with proper formatting', () => {
    const longMessage = {
      ...baseMessage,
      content: 'Line 1\nLine 2\nLine 3\n\nLine 4 after empty line',
    };
    
    render(<MessageItem message={longMessage} />);
    
    expect(screen.getByText('Line 1')).toBeInTheDocument();
    expect(screen.getByText('Line 4 after empty line')).toBeInTheDocument();
  });

  it('should handle empty content gracefully', () => {
    const emptyMessage = {
      ...baseMessage,
      content: '',
    };
    
    const { container } = render(<MessageItem message={emptyMessage} />);
    
    // Should render without errors
    expect(container.querySelector('.ant-list-item')).toBeInTheDocument();
  });
});
