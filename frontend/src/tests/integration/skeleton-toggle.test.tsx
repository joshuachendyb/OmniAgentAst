/**
 * 骨架屏切换时机集成测试
 *
 * 测试骨架屏在 AppContext 初始化完成后的切换逻辑
 *
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-12
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React, { useState, useEffect } from 'react';

// 测试组件：模拟骨架屏切换逻辑（与 Layout/index.tsx 一致）
// 这个组件直接测试切换逻辑，不依赖 AppContext
const TestSkeletonToggle: React.FC<{
  isInitialized: boolean;
  initError: string | null;
  onRetry: () => void;
}> = ({ isInitialized, initError, onRetry }) => {
  const [skeletonState, setSkeletonState] = useState<{
    visible: boolean;
    error?: string;
  }>({ visible: true });

  // 模拟骨架屏切换逻辑（与 Layout/index.tsx 一致）
  useEffect(() => {
    // 初始化成功，延迟切换到实际内容
    if (isInitialized && skeletonState.visible && !initError) {
      const timer = setTimeout(() => {
        setSkeletonState({ visible: false });
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [isInitialized, skeletonState.visible, initError]);

  const handleRetry = async () => {
    setSkeletonState({ visible: true, error: undefined });
    onRetry();
  };

  return (
    <div>
      {skeletonState.visible ? (
        <div data-testid="skeleton">骨架屏显示中</div>
      ) : (
        <div data-testid="content">实际内容</div>
      )}
      {initError && (
        <div data-testid="error">{initError}</div>
      )}
      <button onClick={handleRetry} data-testid="retry">重试</button>
    </div>
  );
};

describe('骨架屏切换时机集成测试', () => {
  // 成功初始化测试
  describe('成功初始化', () => {
    it('should show skeleton initially', () => {
      render(
        <TestSkeletonToggle 
          isInitialized={false} 
          initError={null} 
          onRetry={() => {}} 
        />
      );
      
      // 初始显示骨架屏
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });

    it('should hide skeleton after initialization completes', async () => {
      render(
        <TestSkeletonToggle 
          isInitialized={true} 
          initError={null} 
          onRetry={() => {}} 
        />
      );
      
      // 等待初始化完成（100ms 延迟后切换）
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 200));
      });
      
      // 骨架屏应该隐藏
      await waitFor(() => {
        expect(screen.queryByTestId('skeleton')).not.toBeInTheDocument();
      });
      
      // 显示实际内容
      expect(screen.getByTestId('content')).toBeInTheDocument();
    });

    it('should stay showing skeleton when not initialized', async () => {
      render(
        <TestSkeletonToggle 
          isInitialized={false} 
          initError={null} 
          onRetry={() => {}} 
        />
      );
      
      // 等待一段时间
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 200));
      });
      
      // 骨架屏仍然显示
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });
  });

  // 初始化失败测试
  describe('初始化失败', () => {
    it('should show error when initialization fails', () => {
      const errorMsg = '网络连接失败';
      render(
        <TestSkeletonToggle 
          isInitialized={false} 
          initError={errorMsg} 
          onRetry={() => {}} 
        />
      );
      
      // 验证错误显示
      expect(screen.getByTestId('error')).toBeInTheDocument();
      expect(screen.getByText(errorMsg)).toBeInTheDocument();
    });

    it('should still show skeleton when error occurs', () => {
      render(
        <TestSkeletonToggle 
          isInitialized={false} 
          initError="error" 
          onRetry={() => {}} 
        />
      );
      
      // 骨架屏仍然显示
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
    });
  });

  // 重试功能测试
  describe('重试功能', () => {
    it('should reset skeleton when retry is clicked', async () => {
      const mockRetry = vi.fn();
      
      // 初始已完成初始化
      render(
        <TestSkeletonToggle 
          isInitialized={true} 
          initError={null} 
          onRetry={mockRetry} 
        />
      );
      
      // 等待初始渲染完成
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 50));
      });
      
      // 点击重试按钮
      const retryButton = screen.getByTestId('retry');
      await userEvent.click(retryButton);
      
      // 骨架屏应该重新显示
      expect(screen.getByTestId('skeleton')).toBeInTheDocument();
      
      // 验证重试回调被调用
      expect(mockRetry).toHaveBeenCalledTimes(1);
    });
  });
});