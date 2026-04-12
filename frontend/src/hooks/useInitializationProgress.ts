/**
 * useInitializationProgress Hook - 协调初始化时序
 *
 * 功能：协调 Layout 初始化和 Chat 数据加载的时序
 * 避免竞态条件，优化用户体验
 *
 * Phase 2 P2 优化 - 步骤9：协调初始化时序
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-12
 */

import { useState, useEffect } from 'react';

interface UseInitializationProgressProps {
  appInitialized: boolean;
  sessionLoaded: boolean;
}

export interface InitializationProgress {
  layoutReady: boolean;
  chatDataReady: boolean;
  isReady: boolean;
  phase: 'initializing' | 'loading-layout' | 'loading-chat' | 'ready';
}

export const useInitializationProgress = ({
  appInitialized,
  sessionLoaded,
}: UseInitializationProgressProps): InitializationProgress => {
  const [layoutReady, setLayoutReady] = useState(false);
  const [chatDataReady, setChatDataReady] = useState(false);

  // 监听 Layout 初始化完成
  useEffect(() => {
    if (appInitialized && !layoutReady) {
      // 延迟200ms确保 Layout 完全渲染
      const timer = setTimeout(() => setLayoutReady(true), 200);
      return () => clearTimeout(timer);
    }
  }, [appInitialized, layoutReady]);

  // 监听 Chat 数据加载完成
  useEffect(() => {
    if (sessionLoaded && !chatDataReady) {
      setChatDataReady(true);
    }
  }, [sessionLoaded, chatDataReady]);

  const isReady = layoutReady && chatDataReady;
  
  const phase = !appInitialized 
    ? 'initializing' 
    : !layoutReady 
      ? 'loading-layout' 
      : !chatDataReady 
        ? 'loading-chat' 
        : 'ready';

  return { layoutReady, chatDataReady, isReady, phase };
};

export default useInitializationProgress;