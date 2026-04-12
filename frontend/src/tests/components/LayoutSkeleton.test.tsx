/**
 * LayoutSkeleton 组件测试
 *
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-12
 * @update 2026-04-12 添加错误状态和重试按钮测试
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { LayoutSkeleton } from '../../components/Skeleton/LayoutSkeleton';

describe('LayoutSkeleton Component', () => {
  // 基础渲染测试
  describe('Basic Rendering', () => {
    it('should render skeleton layout', () => {
      render(<LayoutSkeleton />);
      
      // 验证骨架屏渲染
      expect(document.querySelector('.ant-layout')).toBeInTheDocument();
    });

    it('should render Sider skeleton in desktop mode', () => {
      render(<LayoutSkeleton isMobile={false} />);
      
      // 验证左侧导航骨架
      expect(document.querySelector('.ant-layout-sider')).toBeInTheDocument();
    });

    it('should not render Sider skeleton in mobile mode', () => {
      render(<LayoutSkeleton isMobile={true} />);
      
      // 验证移动端不显示左侧导航
      expect(document.querySelector('.ant-layout-sider')).not.toBeInTheDocument();
    });

    it('should render Header skeleton', () => {
      render(<LayoutSkeleton />);
      
      // 验证顶部导航骨架
      expect(document.querySelector('.ant-layout-header')).toBeInTheDocument();
    });

    it('should render Content skeleton', () => {
      render(<LayoutSkeleton />);
      
      // 验证内容区骨架
      expect(document.querySelector('.ant-layout-content')).toBeInTheDocument();
    });
  });

  // 错误状态测试
  describe('Error State', () => {
    it('should not show error UI when error is undefined', () => {
      render(<LayoutSkeleton error={undefined} onRetry={() => {}} />);
      
      // 验证没有显示错误图标
      expect(screen.queryByText('!')).not.toBeInTheDocument();
    });

    it('should not show error UI when error is empty string', () => {
      render(<LayoutSkeleton error="" onRetry={() => {}} />);
      
      // 验证空字符串不显示错误
      expect(screen.queryByText('!')).not.toBeInTheDocument();
    });

    it('should show error UI when error message is provided', () => {
      const errorMsg = '加载失败，请检查网络连接';
      render(<LayoutSkeleton error={errorMsg} onRetry={() => {}} />);
      
      // 验证显示错误图标
      expect(screen.getByText('!')).toBeInTheDocument();
    });

    it('should display error message text', () => {
      const errorMsg = '网络连接失败';
      render(<LayoutSkeleton error={errorMsg} onRetry={() => {}} />);
      
      // 验证显示错误信息
      expect(screen.getByText(errorMsg)).toBeInTheDocument();
    });
  });

  // 重试功能测试
  describe('Retry Function', () => {
    it('should not show retry button when onRetry is not provided', () => {
      render(<LayoutSkeleton error="error" />);
      
      // 验证没有重试按钮
      expect(screen.queryByText('重试')).not.toBeInTheDocument();
    });

    it('should show retry button when onRetry is provided and error exists', () => {
      render(<LayoutSkeleton error="error" onRetry={() => {}} />);
      
      // 验证显示重试按钮
      expect(screen.getByText('重试')).toBeInTheDocument();
    });

    it('should call onRetry when retry button is clicked', async () => {
      const mockRetry = vi.fn();
      render(<LayoutSkeleton error="error" onRetry={mockRetry} />);
      
      // 点击重试按钮
      fireEvent.click(screen.getByText('重试'));
      
      // 验证回调被调用
      expect(mockRetry).toHaveBeenCalledTimes(1);
    });
  });

  // 动画测试
  describe('Animation', () => {
    it('should have skeleton loading animation class', () => {
      render(<LayoutSkeleton />);
      
      // 验证动画类存在
      const skeletonElements = document.querySelectorAll('[class*="skeleton"]');
      expect(skeletonElements.length).toBeGreaterThan(0);
    });
  });
});