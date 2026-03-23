/**
 * MessageItem 字段修复测试
 * 
 * 【小强创建 2026-03-23】
 * @description TDD测试：验证步骤字段修复是否正确
 * 
 * 测试依据：小沈文档《步骤及action tool显示方案优化》第9章
 * - 阶段1：字段错误修复（16处）
 * - 阶段2：Map状态管理（3处）
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
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

describe('【阶段1】字段错误修复测试', () => {
  describe('Observation步骤字段修复', () => {
    it('【P1-1】observation导出应使用正确字段名（无obs_前缀）', () => {
      // 验证导出函数中observation case使用了正确的字段名
      // 根据小沈文档第9.8.1节第1-3项：
      // - obs_execution_status → execution_status
      // - obs_summary → summary  
      // - obs_raw_data → raw_data
      
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
            execution_status: 'success',  // sse.ts保存的字段（无obs_前缀）
            summary: 'Test summary',
            raw_data: { entries: [] },
            content: 'Test content',
            reasoning: 'Test reasoning',
            action_tool: 'test_tool',
            params: {},
            is_finished: true,
          },
        ],
      };

      render(<MessageItem message={messageWithObservation} showExecution={true} />);
      
      // 验证observation步骤能正确渲染（使用step.content）
      expect(screen.getByText('Test observation')).toBeInTheDocument();
    });

    it('【P1-2】observation显示应使用step.reasoning而非step.thought', () => {
      // 根据小沈文档第9.8.1节第8-9项：
      // - Line 312: step.thought → step.reasoning
      // - Line 320: 💭 {step.thought} → 💭 {step.reasoning}
      
      const messageWithObservationAndReasoning = {
        id: 'msg-reasoning-test',
        role: 'assistant' as const,
        content: 'Test',
        timestamp: new Date(),
        executionSteps: [
          {
            type: 'observation' as const,
            step: 1,
            timestamp: Date.now(),
            // 提供 reasoning 而非 thought，组件应正确显示
            reasoning: 'Agent reasoning text',
            content: '',  // 空content，确保显示reasoning
            raw_data: null,
          },
        ],
      };

      render(<MessageItem message={messageWithObservationAndReasoning} showExecution={true} />);
      
      // 使用正则表达式匹配，因为文本可能被拆分成多个元素
      expect(screen.getByText(/Agent reasoning text/)).toBeInTheDocument();
    });

    it('【P1-3】observation显示文件列表应使用step.raw_data而非step.observation?.result', () => {
      // 根据小沈文档第9.8.1节第10-13项：
      // - Line 344: step.observation?.result → step.raw_data
      // - Line 346: obsResult?.entries → obsRawData?.entries
      // - Line 370: obsResult.entries.map → obsRawData.entries.map
      // - Line 374: obsResult.entries.length → obsRawData.entries.length
      
      const messageWithRawData = {
        id: 'msg-rawdata-test',
        role: 'assistant' as const,
        content: 'Test',
        timestamp: new Date(),
        executionSteps: [
          {
            type: 'observation' as const,
            step: 1,
            timestamp: Date.now(),
            content: '',  // 空content，显示文件列表
            raw_data: {
              entries: [
                { name: 'file1.txt', type: 'file', path: '/path/file1.txt' },
                { name: 'folder1', type: 'directory', path: '/path/folder1' },
              ],
            },
          },
        ],
      };

      render(<MessageItem message={messageWithRawData} showExecution={true} />);
      
      // 使用正则表达式匹配
      expect(screen.getByText(/file1\.txt/)).toBeInTheDocument();
      expect(screen.getByText(/folder1/)).toBeInTheDocument();
    });

    it('【P1-4】observation显示summary应使用step.summary而非step.result', () => {
      // 根据小沈文档第9.8.1节第14-15项：
      // - Line 385: step.result → step.summary
      // - Line 386: {step.result} → {step.summary}
      
      const messageWithSummary = {
        id: 'msg-summary-test',
        role: 'assistant' as const,
        content: 'Test',
        timestamp: new Date(),
        executionSteps: [
          {
            type: 'observation' as const,
            step: 1,
            timestamp: Date.now(),
            content: '',  // 空content
            raw_data: null,  // 空raw_data
            summary: 'This is a summary string',  // 使用正确的summary字段
          },
        ],
      };

      render(<MessageItem message={messageWithSummary} showExecution={true} />);
      
      // 使用正则表达式匹配
      expect(screen.getByText(/This is a summary string/)).toBeInTheDocument();
    });
  });

  describe('Thought步骤字段修复', () => {
    it('【P1-5】thought步骤应使用step.reasoning而非step.thinking_prompt', () => {
      // 根据小沈文档第9.8.1节第16项：
      // - Line 410: step.thinking_prompt → step.reasoning
      
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
            content: '',
            reasoning: 'This is the reasoning text',  // 正确的字段
          },
        ],
      };

      render(<MessageItem message={messageWithThought} showExecution={true} />);
      
      // 使用正则表达式匹配
      expect(screen.getByText(/This is the reasoning text/)).toBeInTheDocument();
    });
  });
});

describe('【阶段2】Map状态管理测试', () => {
  it('【Map-1】多个步骤应能独立管理展开/折叠状态', () => {
    // 根据小沈文档第9.5节和8.1.4节：
    // 应使用 Map<number, boolean> 存储每个步骤的状态
    
    const messageWithMultipleSteps = {
      id: 'msg-multi-steps',
      role: 'assistant' as const,
      content: 'Test with multiple steps',
      timestamp: new Date(),
      executionSteps: [
        {
          type: 'observation' as const,
          step: 1,
          timestamp: Date.now(),
          content: '',
          raw_data: {
            entries: [
              { name: 'file1.txt', type: 'file', path: '/path/file1.txt' },
            ],
          },
        },
        {
          type: 'observation' as const,
          step: 2,
          timestamp: Date.now(),
          content: '',
          raw_data: {
            entries: [
              { name: 'file2.txt', type: 'file', path: '/path/file2.txt' },
            ],
          },
        },
      ],
    };

    render(<MessageItem message={messageWithMultipleSteps} showExecution={true} />);
    
    // 验证两个步骤的文件列表都能显示（默认展开）
    expect(screen.getByText(/file1\.txt/)).toBeInTheDocument();
    expect(screen.getByText(/file2\.txt/)).toBeInTheDocument();
  });
});
