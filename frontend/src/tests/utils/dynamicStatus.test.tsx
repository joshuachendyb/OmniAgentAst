/**
 * 动态状态提示组件测试
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-03
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import React from 'react';

// 导入待实现的组件（此时还不存在，测试会失败）
import { DynamicStatusDisplay } from '../../utils/dynamicStatus';

describe('DynamicStatusDisplay', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  describe('状态映射测试', () => {
    it('应该显示"AI开始执行任务"当没有 steps 时', () => {
      const { container } = render(
        <DynamicStatusDisplay executionSteps={[]} isStreaming={true} />
      );
      
      expect(container.textContent).toContain('AI开始执行任务');
      expect(container.textContent).toContain('🚀');
    });

    it('应该显示"AI 正在思考"当 start step 到达时', () => {
      const executionSteps = [{ type: 'start' }];
      const { container } = render(
        <DynamicStatusDisplay executionSteps={executionSteps} isStreaming={true} />
      );
      
      expect(container.textContent).toContain('AI 正在思考');
      expect(container.textContent).toContain('🤔');
    });

    it('应该显示"Agent 正在执行tool_name"当 thought step 到达时', () => {
      const executionSteps = [{ type: 'start' }, { type: 'thought' }];
      const { container } = render(
        <DynamicStatusDisplay executionSteps={executionSteps} isStreaming={true} />
      );
      
      expect(container.textContent).toContain('tool_name');
      expect(container.textContent).toContain('🛠️');
    });

    it('应该显示"Agent 正在执行observation"当 action_tool step 到达时', () => {
      const executionSteps = [{ type: 'start' }, { type: 'thought' }, { type: 'action_tool' }];
      const { container } = render(
        <DynamicStatusDisplay executionSteps={executionSteps} isStreaming={true} />
      );
      
      expect(container.textContent).toContain('observation');
      expect(container.textContent).toContain('👁️');
    });

    it('应该显示"AI 正在回复"当 chunk step 到达时', () => {
      const executionSteps = [{ type: 'start' }, { type: 'chunk', content: '你好' }];
      const { container } = render(
        <DynamicStatusDisplay executionSteps={executionSteps} isStreaming={true} />
      );
      
      expect(container.textContent).toContain('AI 正在回复');
      expect(container.textContent).toContain('💬');
    });

    it('应该显示"AI任务执行完成"当 final step 到达时', () => {
      const executionSteps = [{ type: 'start' }, { type: 'final' }];
      const { container } = render(
        <DynamicStatusDisplay executionSteps={executionSteps} isStreaming={false} />
      );
      
      expect(container.textContent).toContain('AI任务执行完成');
      expect(container.textContent).toContain('✅');
    });

    it('应该显示"AI任务执行完成"当 error step 到达时', () => {
      const executionSteps = [{ type: 'start' }, { type: 'error' }];
      const { container } = render(
        <DynamicStatusDisplay executionSteps={executionSteps} isStreaming={false} />
      );
      
      expect(container.textContent).toContain('AI任务执行完成');
      expect(container.textContent).toContain('✅');
    });
  });

  describe('计时器测试', () => {
    it('应该从 00:00 开始计时', () => {
      const { container } = render(
        <DynamicStatusDisplay executionSteps={[]} isStreaming={true} />
      );
      
      expect(container.textContent).toContain('00:00');
    });

    it('应该在 5 秒后显示 00:05', () => {
      const { container } = render(
        <DynamicStatusDisplay executionSteps={[]} isStreaming={true} />
      );
      
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      
      expect(container.textContent).toContain('00:05');
    });

    it('应该在 65 秒后显示 01:05', () => {
      const { container } = render(
        <DynamicStatusDisplay executionSteps={[]} isStreaming={true} />
      );
      
      act(() => {
        vi.advanceTimersByTime(65000);
      });
      
      expect(container.textContent).toContain('01:05');
    });

    it('应该在状态切换时重置计时器', () => {
      const { rerender, container } = render(
        <DynamicStatusDisplay executionSteps={[]} isStreaming={true} />
      );
      
      // 前进 5 秒
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      
      expect(container.textContent).toContain('00:05');
      
      // 状态切换（start 到达）
      rerender(
        <DynamicStatusDisplay executionSteps={[{ type: 'start' }]} isStreaming={true} />
      );
      
      // 计时器应该重置
      expect(container.textContent).toContain('00:00');
    });

    it('应该在 final 状态时停止计时', () => {
      const { rerender, container } = render(
        <DynamicStatusDisplay executionSteps={[]} isStreaming={true} />
      );
      
      // 前进 10 秒
      act(() => {
        vi.advanceTimersByTime(10000);
      });
      
      // final 到达
      rerender(
        <DynamicStatusDisplay executionSteps={[{ type: 'final' }]} isStreaming={false} />
      );
      
      // 再前进 10 秒，计时器不应该变化
      act(() => {
        vi.advanceTimersByTime(10000);
      });
      
      expect(container.textContent).toContain('AI任务执行完成');
      expect(container.textContent).not.toMatch(/\d{2}:\d{2}/);
    });
  });

  describe('动画测试', () => {
    it('应该在非 final 状态显示动画光标', () => {
      const { container } = render(
        <DynamicStatusDisplay executionSteps={[]} isStreaming={true} />
      );
      
      expect(container.textContent).toContain('▌');
    });

    it('应该在 final 状态不显示动画光标', () => {
      const { container } = render(
        <DynamicStatusDisplay executionSteps={[{ type: 'final' }]} isStreaming={false} />
      );
      
      expect(container.textContent).not.toContain('▌');
    });
  });
});
