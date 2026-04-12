/**
 * MessageListSkeleton 组件测试
 *
 * @author 小资
 * @version 1.0.0
 * @since 2026-04-12
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageListSkeleton } from '../../components/Skeleton/MessageListSkeleton';

describe('MessageListSkeleton Component', () => {
  // 基础渲染测试
  describe('Basic Rendering', () => {
    it('should render message list skeleton', () => {
      render(<MessageListSkeleton />);
      
      // 验证骨架屏容器存在
      expect(document.querySelector('[class*="messageListSkeleton"]')).toBeInTheDocument();
    });

    it('should render 4 message placeholders by default', () => {
      render(<MessageListSkeleton />);
      
      // 验证显示4条消息骨架（默认count=4）
      const messageItems = document.querySelectorAll('[class*="skeletonMessageItem"]');
      expect(messageItems).toHaveLength(4);
    });

    it('should render custom number of messages', () => {
      render(<MessageListSkeleton count={3} />);
      
      const messageItems = document.querySelectorAll('[class*="skeletonMessageItem"]');
      expect(messageItems).toHaveLength(3);
    });

    it('should render user message skeleton', () => {
      render(<MessageListSkeleton />);
      
      // 验证用户消息骨架（skeletonUser）
      const userSkeletons = document.querySelectorAll('[class*="skeletonUser"]');
      expect(userSkeletons.length).toBeGreaterThan(0);
    });

    it('should render assistant message skeleton', () => {
      render(<MessageListSkeleton />);
      
      // 验证助手消息骨架（skeletonAI）
      const assistantSkeletons = document.querySelectorAll('[class*="skeletonAI"]');
      expect(assistantSkeletons.length).toBeGreaterThan(0);
    });
  });

  // 消息内容测试
  describe('Message Content', () => {
    it('should render avatar placeholder', () => {
      render(<MessageListSkeleton />);
      
      // 验证头像骨架
      const avatars = document.querySelectorAll('[class*="skeletonAvatar"]');
      expect(avatars.length).toBeGreaterThan(0);
    });

    it('should render content placeholder', () => {
      render(<MessageListSkeleton />);
      
      // 验证内容骨架
      const contents = document.querySelectorAll('[class*="skeletonContent"]');
      expect(contents.length).toBeGreaterThan(0);
    });

    it('should render line placeholders', () => {
      render(<MessageListSkeleton />);
      
      // 验证线条骨架
      const lines = document.querySelectorAll('[class*="skeletonLine"]');
      expect(lines.length).toBeGreaterThan(0);
    });
  });

  // 动画测试
  describe('Animation', () => {
    it('should have loading animation', () => {
      render(<MessageListSkeleton />);
      
      // 验证动画样式存在
      const skeletonItems = document.querySelectorAll('[class*="skeleton"]');
      expect(skeletonItems.length).toBeGreaterThan(0);
    });
  });

  // 空状态测试
  describe('Empty State', () => {
    it('should render with count=0', () => {
      render(<MessageListSkeleton count={0} />);
      
      // 验证不渲染任何消息
      const messageItems = document.querySelectorAll('[class*="skeletonMessageItem"]');
      expect(messageItems).toHaveLength(0);
    });
  });
});