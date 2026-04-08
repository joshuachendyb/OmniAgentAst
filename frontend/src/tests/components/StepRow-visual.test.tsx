/**
 * StepRow UI视觉和布局测试
 * 
 * @author 小强
 * @description 验证StepRow组件各种step类型的视觉显示
 * @since 2026-03-24
 * 
 * 【重要】本测试遵循TDD原则：
 * 1. 先写测试
 * 2. 验证测试失败（RED）
 * 3. 写最简代码通过测试（GREEN）
 * 4. 验证测试通过
 * 5. 重构
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MessageItem from '../../components/Chat/MessageItem';

describe('StepRow UI视觉和布局', () => {
  const baseMessage = {
    id: 'msg-1',
    role: 'assistant' as const,
    content: 'Test message',
    timestamp: new Date(),
  };

  describe('start步骤', () => {
    it('应该显示任务开始信息', () => {
      const messageWithStart = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'start' as const,
            task_id: 'task-123',
            step: 1,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithStart} />);

      // 应该显示任务ID
      expect(screen.getByText(/task-123/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤1/)).toBeInTheDocument();
    });
  });

  describe('thought步骤', () => {
    it('应该显示推理内容', () => {
      const messageWithThought = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'thought' as const,
            content: '我需要先查看目录',  // 【小强修改 2026-04-08】reasoning已删除，改为content
            step: 1,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithThought} />);

      // 应该显示推理内容（现在从content读取）
      expect(screen.getByText(/我需要先查看目录/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤1/)).toBeInTheDocument();
    });
  });

  describe('final步骤', () => {
    it('应该显示最终回复内容', () => {
      const messageWithFinal = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'final' as const,
            content: '任务完成',
            step: 2,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithFinal} />);

      // 应该显示最终内容
      expect(screen.getByText(/任务完成/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤2/)).toBeInTheDocument();
    });
  });

  describe('error步骤', () => {
    it('应该显示错误信息', () => {
      const messageWithError = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'error' as const,
            error_message: 'something went wrong',
            step: 3,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithError} />);

      // 应该显示错误信息
      expect(screen.getByText(/something went wrong/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤3/)).toBeInTheDocument();
    });
  });

  describe('interrupted步骤', () => {
    it('应该显示中断信息', () => {
      const messageWithInterrupted = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'interrupted' as const,
            content: '客户端断开连接',
            step: 4,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithInterrupted} />);

      // 应该显示中断信息
      expect(screen.getByText(/客户端断开连接/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤4/)).toBeInTheDocument();
      // 应该显示⚠️标签
      expect(screen.getByText(/⚠️ 中断：/)).toBeInTheDocument();
    });
  });

  describe('paused步骤', () => {
    it('应该显示暂停信息', () => {
      const messageWithPaused = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'paused' as const,
            content: '任务已暂停',
            step: 5,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithPaused} />);

      // 应该显示暂停信息
      expect(screen.getByText(/任务已暂停/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤5/)).toBeInTheDocument();
      // 应该显示⏸️标签
      expect(screen.getByText(/⏸️ 暂停：/)).toBeInTheDocument();
    });
  });

  describe('resumed步骤', () => {
    it('应该显示恢复信息', () => {
      const messageWithResumed = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'resumed' as const,
            content: '任务已恢复',
            step: 6,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithResumed} />);

      // 应该显示恢复信息
      expect(screen.getByText(/任务已恢复/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤6/)).toBeInTheDocument();
      // 应该显示▶️标签
      expect(screen.getByText(/▶️ 恢复：/)).toBeInTheDocument();
    });
  });

  describe('retrying步骤', () => {
    it('应该显示重试信息', () => {
      const messageWithRetrying = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'retrying' as const,
            content: '正在重试',
            step: 7,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithRetrying} />);

      // 应该显示重试信息
      expect(screen.getByText(/正在重试/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤7/)).toBeInTheDocument();
      // 应该显示🔄标签
      expect(screen.getByText(/🔄 重试：/)).toBeInTheDocument();
    });
  });

  describe('action_tool步骤', () => {
    it('应该显示工具名称', () => {
      const messageWithActionTool = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'action_tool' as const,
            tool_name: 'list_directory',
            tool_params: { path: 'D:\\' },
            step: 2,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithActionTool} />);

      // 应该显示工具名称
      expect(screen.getByText(/list_directory/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤2/)).toBeInTheDocument();
    });
  });

  describe('observation步骤', () => {
    it('应该显示检查结果', () => {
      const messageWithObservation = {
        ...baseMessage,
        executionSteps: [
          {
            type: 'observation' as const,
            content: '执行成功',
            step: 3,
            timestamp: Date.now(),
          },
        ],
      };

      render(<MessageItem message={messageWithObservation} />);

      // 应该显示检查结果
      expect(screen.getByText(/执行成功/)).toBeInTheDocument();
      // 应该显示步骤编号
      expect(screen.getByText(/步骤3/)).toBeInTheDocument();
    });
  });
});
