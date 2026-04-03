/**
 * 前端分页功能测试
 * 
 * 设计依据：OmniFunctionCall工具分页设计与实现-小沈-2026-04-03.md
 * 核心原则：后端返回全部数据，前端自己控制分页显示
 * 
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-03
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import MessageItem from '../../components/Chat/MessageItem';

// Mock taskControlApi
vi.mock('../../services/api', () => ({
  taskControlApi: {
    nextPage: vi.fn(),
  },
}));

import { taskControlApi } from '../../services/api';

describe('前端分页功能（后端返回全部数据）', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const baseMessage = {
    id: 'test-msg-1',
    role: 'assistant' as const,
    content: '搜索结果',
    timestamp: new Date(),
    executionSteps: [
      {
        type: 'start',
        task_id: 'test-task-id',
        content: '🤔 AI 正在思考...',
        timestamp: 1712131200000,
        step: 1,
      },
    ],
    isStreaming: false,
  };

  describe('后端返回全部数据时，前端分页显示', () => {
    it('应该显示"加载更多"按钮当数据超过100条时', () => {
      const message = {
        ...baseMessage,
        executionSteps: [
          ...baseMessage.executionSteps,
          {
            type: 'action_tool',
            tool_name: 'search_files',
            tool_params: { file_pattern: '*.doc', path: 'E:/' },
            raw_data: {
              success: true,
              matches: Array.from({ length: 200 }, (_, i) => ({ name: `file${i}.doc`, path: `/path/file${i}.doc` })),
              total: 200,
              has_more: false,  // 后端返回全部数据
              next_page_token: null,
            },
            step: 2,
            timestamp: 1712131200000,
          },
        ],
      };

      render(<MessageItem message={message as any} showExecution={true} />);

      // 应该显示"加载更多"按钮（前端分页）
      expect(screen.getByText(/加载更多/)).toBeInTheDocument();
    });

    it('应该不显示"加载更多"按钮当数据少于100条时', () => {
      const message = {
        ...baseMessage,
        executionSteps: [
          ...baseMessage.executionSteps,
          {
            type: 'action_tool',
            tool_name: 'search_files',
            tool_params: {},
            raw_data: {
              success: true,
              matches: Array.from({ length: 50 }, (_, i) => ({ name: `file${i}.doc`, path: `/path/file${i}.doc` })),
              total: 50,
              has_more: false,
              next_page_token: null,
            },
            step: 2,
            timestamp: 1712131200000,
          },
        ],
      };

      render(<MessageItem message={message as any} showExecution={true} />);

      // 不应该显示"加载更多"按钮
      expect(screen.queryByText(/加载更多/)).not.toBeInTheDocument();
    });

    it('点击"加载更多"应该显示更多数据，不调用后端API', () => {
      const message = {
        ...baseMessage,
        executionSteps: [
          ...baseMessage.executionSteps,
          {
            type: 'action_tool',
            tool_name: 'search_files',
            tool_params: {},
            raw_data: {
              success: true,
              matches: Array.from({ length: 200 }, (_, i) => ({ name: `file${i}.doc`, path: `/path/file${i}.doc` })),
              total: 200,
              has_more: false,
              next_page_token: null,
            },
            step: 2,
            timestamp: 1712131200000,
          },
        ],
      };

      render(<MessageItem message={message as any} showExecution={true} />);

      // 点击"加载更多"
      fireEvent.click(screen.getByText(/加载更多/));

      // 不应该调用后端 nextPage API
      expect(taskControlApi.nextPage).not.toHaveBeenCalled();
    });
  });
});
