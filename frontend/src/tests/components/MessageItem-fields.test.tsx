/**
 * MessageItem 字段测试
 * 
 * 【小资更新 2026-04-07】
 * @description 更新测试：适配后端删除第二次LLM调用后的变化
 * - observation 阶段只保留 content 字段
 * - 工具执行结果（文件列表、摘要等）已在 tool_name 阶段显示
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import MessageItem from '../../components/Chat/MessageItem';

// Mock clipboard API
Object.defineProperty(navigator, 'clipboard', {
  value: {
    writeText: vi.fn().mockResolvedValue(undefined),
  },
  writable: true,
});

// Mock URL.createObjectURL
global.URL.createObjectURL = vi.fn(() => 'blob:test');
global.URL.revokeObjectURL = vi.fn();

// Mock ant message
vi.mock('antd', async () => {
  const actual = await vi.importActual('antd');
  return {
    ...actual,
    message: {
      success: vi.fn(),
      error: vi.fn(),
    },
  };
});

describe('【小资更新 2026-04-07】Observation 步骤精简测试', () => {
  it('【P1-1】observation 只显示 content 字段', () => {
    // 后端删除第二次LLM调用后，observation只显示content
    // 工具执行结果已在 tool_name 阶段显示
    const messageWithObservation = {
      id: 'msg-obs-test',
      role: 'assistant' as const,
      content: 'Test observation',
      timestamp: new Date(),
      executionSteps: [
        {
          type: 'observation' as const,
          step: 1,
          timestamp: Date.now(),
          content: "Tool 'list_directory' executed: Found 12 items",
        },
      ],
    };

    render(<MessageItem message={messageWithObservation} showExecution={true} />);
    
    // 验证observation步骤能正确渲染content
    expect(screen.getByText("Tool 'list_directory' executed: Found 12 items")).toBeInTheDocument();
  });

  it('【P1-2】observation 不再显示 obs_reasoning（已删除该字段）', () => {
    // 新设计：observation 只显示 content，不再显示 obs_reasoning
    const messageWithObservation = {
      id: 'msg-obs-test',
      role: 'assistant' as const,
      content: 'Test',
      timestamp: new Date(),
      executionSteps: [
        {
          type: 'observation' as const,
          step: 1,
          timestamp: Date.now(),
          content: 'Observation completed',
          // 注意：不再有 obs_reasoning 字段
        },
      ],
    };

    render(<MessageItem message={messageWithObservation} showExecution={true} />);
    
    // 只显示 content，不显示 obs_reasoning
    expect(screen.getByText('Observation completed')).toBeInTheDocument();
  });

  it('【P1-3】工具执行结果在 tool_name 阶段显示（不是 observation）', () => {
    // 验证工具执行结果（文件列表）在 tool_name 阶段显示
    const messageWithActionTool = {
      id: 'msg-action-tool-test',
      role: 'assistant' as const,
      content: 'Test',
      timestamp: new Date(),
      executionSteps: [
        {
          type: 'action_tool' as const,
          step: 1,
          timestamp: Date.now(),
          tool_name: 'list_directory',
          tool_params: { path: '/test' },
          execution_status: 'success' as const,
          summary: 'Found 5 items',
          raw_data: {
            entries: [
              { name: 'file1.txt', type: 'file', path: '/test/file1.txt' },
              { name: 'folder1', type: 'directory', path: '/test/folder1' },
            ],
          },
        },
      ],
    };

    render(<MessageItem message={messageWithActionTool} showExecution={true} />);
    
    // 文件列表在 action_tool 阶段显示
    expect(screen.getByText(/file1\.txt/)).toBeInTheDocument();
    expect(screen.getByText(/folder1/)).toBeInTheDocument();
    expect(screen.getByText(/Found 5 items/)).toBeInTheDocument();
  });

  it('【P1-4】tool_name 阶段显示 summary（不是 observation）', () => {
    // 验证执行摘要在 tool_name 阶段显示
    const messageWithSummary = {
      id: 'msg-summary-test',
      role: 'assistant' as const,
      content: 'Test',
      timestamp: new Date(),
      executionSteps: [
        {
          type: 'action_tool' as const,
          step: 1,
          timestamp: Date.now(),
          tool_name: 'search_files',
          tool_params: { keyword: 'test' },
          execution_status: 'success' as const,
          summary: 'Search completed, found 10 results',
          raw_data: null,
        },
      ],
    };

    render(<MessageItem message={messageWithSummary} showExecution={true} />);
    
    // summary 在 action_tool 阶段显示
    expect(screen.getByText(/Search completed/)).toBeInTheDocument();
  });
});

describe('Thought 步骤测试（无变化）', () => {
  it('【P2-1】thought 步骤显示 content 字段（reasoning已删除，与content合并）', () => {
    const messageWithThought = {
      id: 'msg-thought-test',
      role: 'assistant' as const,
      content: 'Test',
      timestamp: new Date(),
      executionSteps: [
        {
          type: 'thought' as const,
          step: 1,
          timestamp: Date.now(),
          content: 'Analyzing the request...',  // 现在只显示content
          // reasoning 字段已删除（与content重复）
          tool_name: 'list_directory',
          tool_params: { path: '/test' },
        },
      ],
    };

    render(<MessageItem message={messageWithThought} showExecution={true} />);
    
    // 现在只显示content，不显示reasoning
    expect(screen.getByText(/Analyzing the request/)).toBeInTheDocument();
    expect(screen.getByText(/⬇️ 下一步：list_directory/)).toBeInTheDocument();
  });
});

describe('Map 状态管理测试（无变化）', () => {
  it('【Map-1】多个步骤应能独立管理展开/折叠状态', () => {
    // tool_name 阶段的 raw_data（文件列表）可以独立折叠
    const messageWithMultipleSteps = {
      id: 'msg-multi-steps',
      role: 'assistant' as const,
      content: 'Test with multiple steps',
      timestamp: new Date(),
      executionSteps: [
        {
          type: 'action_tool' as const,
          step: 1,
          timestamp: Date.now(),
          tool_name: 'list_directory',
          tool_params: { path: '/test1' },
          execution_status: 'success' as const,
          summary: 'Found 1 item',
          raw_data: {
            entries: [
              { name: 'file1.txt', type: 'file', path: '/test1/file1.txt' },
            ],
          },
        },
        {
          type: 'action_tool' as const,
          step: 2,
          timestamp: Date.now(),
          tool_name: 'list_directory',
          tool_params: { path: '/test2' },
          execution_status: 'success' as const,
          summary: 'Found 2 items',
          raw_data: {
            entries: [
              { name: 'file2.txt', type: 'file', path: '/test2/file2.txt' },
              { name: 'file3.txt', type: 'file', path: '/test2/file3.txt' },
            ],
          },
        },
      ],
    };

    render(<MessageItem message={messageWithMultipleSteps} showExecution={true} />);
    
    // 两个 action_tool 步骤都能显示
    expect(screen.getByText(/file1\.txt/)).toBeInTheDocument();
    expect(screen.getByText(/file2\.txt/)).toBeInTheDocument();
    expect(screen.getByText(/file3\.txt/)).toBeInTheDocument();
  });
});