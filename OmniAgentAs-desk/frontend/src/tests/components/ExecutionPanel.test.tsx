/**
 * ExecutionPanel Component Tests
 * 
 * @author 小新
 * @description Unit tests for ExecutionPanel component
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ExecutionPanel from '../../components/Chat/ExecutionPanel';
import type { ExecutionStep } from '../../utils/sse';

describe('ExecutionPanel Component', () => {
  const mockSteps: ExecutionStep[] = [
    {
      type: 'thought',
      content: 'I need to analyze the file',
      timestamp: Date.now() - 3000,
    },
    {
      type: 'action',
      tool: 'read_file',
      params: { path: '/test.txt' },
      timestamp: Date.now() - 2000,
    },
    {
      type: 'observation',
      result: { content: 'File contents here' },
      timestamp: Date.now() - 1000,
    },
    {
      type: 'final',
      content: 'Task completed',
      timestamp: Date.now(),
    },
  ];

  it('should render empty state when no steps provided', () => {
    render(<ExecutionPanel steps={[]} isActive={false} />);
    
    // 组件显示"执行详情"或"执行详情 (0步)"
    expect(screen.getByText(/执行详情/)).toBeInTheDocument();
  });

  it('should render all execution steps', () => {
    render(<ExecutionPanel steps={mockSteps} isActive={false} />);
    
    expect(screen.getByText('I need to analyze the file')).toBeInTheDocument();
    expect(screen.getByText(/read_file/)).toBeInTheDocument();
    expect(screen.getByText('Task completed')).toBeInTheDocument();
  });

  it('should show loading indicator when active', () => {
    render(<ExecutionPanel steps={mockSteps} isActive={true} />);

    // 组件在头部显示"正在执行 (X步)"，在时间线末尾显示"执行中..."
    // 使用更具体的选择器来匹配头部文本
    expect(screen.getByText(/正在执行.*\(\d+步\)/)).toBeInTheDocument();
  });

  it('should not show loading indicator when inactive', () => {
    render(<ExecutionPanel steps={mockSteps} isActive={false} />);
    
    // Should not show processing indicator
    expect(screen.queryByText(/执行中/)).not.toBeInTheDocument();
  });

  it('should display step count in header', () => {
    render(<ExecutionPanel steps={mockSteps} isActive={false} />);
    
    // 组件在标题中显示步骤数，如"执行详情 (4步)"
    expect(screen.getByText(/执行详情.*4步/)).toBeInTheDocument();
  });

  it('should format tool action step correctly', () => {
    const actionStep: ExecutionStep[] = [
      {
        type: 'action',
        tool: 'write_file',
        params: { path: '/output.txt', content: 'data' },
        timestamp: Date.now(),
      },
    ];
    
    render(<ExecutionPanel steps={actionStep} isActive={false} />);
    
    expect(screen.getByText(/write_file/)).toBeInTheDocument();
    expect(screen.getByText(/path/)).toBeInTheDocument();
  });

  it('should format observation with result correctly', () => {
    const observationStep: ExecutionStep[] = [
      {
        type: 'observation',
        result: { status: 'success', data: [1, 2, 3] },
        timestamp: Date.now(),
      },
    ];
    
    render(<ExecutionPanel steps={observationStep} isActive={false} />);
    
    expect(screen.getByText(/success/)).toBeInTheDocument();
  });

  it('should handle error step correctly', () => {
    const errorStep: ExecutionStep[] = [
      {
        type: 'error',
        content: 'Failed to read file',
        timestamp: Date.now(),
      },
    ];
    
    render(<ExecutionPanel steps={errorStep} isActive={false} />);
    
    expect(screen.getByText(/Failed to read file/)).toBeInTheDocument();
  });

  it('should display step type labels for each step', () => {
    render(<ExecutionPanel steps={mockSteps} isActive={false} />);

    // Each step should have a type label (思考, 行动, 观察, 完成)
    // 注意：组件使用"行动"标签来表示action类型步骤，不是"工具"
    expect(screen.getByText('思考')).toBeInTheDocument();
    expect(screen.getByText('行动')).toBeInTheDocument();
    expect(screen.getByText('观察')).toBeInTheDocument();
    expect(screen.getByText('完成')).toBeInTheDocument();
  });

  it('should handle steps without optional fields', () => {
    const minimalSteps: ExecutionStep[] = [
      {
        type: 'thought',
        timestamp: Date.now(),
      },
      {
        type: 'action',
        timestamp: Date.now(),
      },
    ];
    
    const { container } = render(
      <ExecutionPanel steps={minimalSteps} isActive={false} />
    );
    
    // Should render without errors even without optional fields
    expect(container.querySelector('.ant-timeline')).toBeInTheDocument();
  });

  it('should handle long content in steps', () => {
    const longContentStep: ExecutionStep[] = [
      {
        type: 'thought',
        content: 'This is a very long thought that might need to be truncated or wrapped properly in the UI to ensure good user experience',
        timestamp: Date.now(),
      },
    ];
    
    render(<ExecutionPanel steps={longContentStep} isActive={false} />);
    
    expect(screen.getByText(longContentStep[0].content!)).toBeInTheDocument();
  });

  it('should update when steps change', () => {
    const { rerender } = render(
      <ExecutionPanel steps={[mockSteps[0]]} isActive={true} />
    );
    
    expect(screen.getByText('I need to analyze the file')).toBeInTheDocument();
    
    // Add more steps
    rerender(<ExecutionPanel steps={mockSteps} isActive={true} />);
    
    expect(screen.getByText('Task completed')).toBeInTheDocument();
  });
});
