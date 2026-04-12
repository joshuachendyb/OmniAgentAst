/**
 * 应用入口组件 - App.tsx
 *
 * 功能：应用根组件，整合Layout布局和路由
 *
 * Phase 2 P2 优化：路由懒加载 - 减少首屏 bundle 大小
 *
 * @author 小新
 * @version 3.1.0
 * @since 2026-02-17
 * @update 2026-02-18 集成React Router，支持多页面路由 - by 小新
 * @update 2026-04-12 添加路由懒加载 - by 小强
 */

import React, { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import AppLayout from './components/Layout';
import NewChatContainer from './components/Chat/NewChatContainer';
import { SecurityProvider } from './contexts/SecurityContext';
import { AppProvider } from './contexts/AppContext';

// 路由懒加载 - 减少首屏 bundle 大小
const HistoryPage = lazy(() => import('./pages/History'));
const Settings = lazy(() => import('./pages/Settings'));

// 懒加载加载中组件
const LazyLoadingFallback: React.FC = () => (
  <div style={{ 
    display: 'flex', 
    justifyContent: 'center', 
    alignItems: 'center', 
    height: '100vh',
    color: '#999',
    fontSize: '14px'
  }}>
    加载中...
  </div>
);

/**
 * 路由内容组件
 *
 * 功能：根据当前路由渲染不同页面，并传递activeKey给Layout
 * Phase 2 P2 优化：使用 Suspense 包装懒加载路由
 *
 * @author 小新
 */
const RouterContent: React.FC = () => {
  const location = useLocation();

  return (
    <AppLayout activeKey={location.pathname}>
      <Suspense fallback={<LazyLoadingFallback />}>
        <Routes>
          <Route path="/" element={<NewChatContainer />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings" element={<Settings />} />
          {/* 默认重定向到首页 */}
          <Route path="*" element={<NewChatContainer />} />
        </Routes>
      </Suspense>
    </AppLayout>
  );
};

/**
 * 应用主组件
 *
 * 变更记录：
 * - v3.0.0 (2026-02-18 by 小新): 集成React Router，支持多页面路由
 * - v2.0.0 (2026-02-17 by 小新): 重构为左右分栏布局，使用AppLayout组件
 * - v1.0.0: 初始版本，单栏布局
 */
const App: React.FC = () => {
  return (
    <BrowserRouter>
      <SecurityProvider>
        <AppProvider>
          <RouterContent />
        </AppProvider>
      </SecurityProvider>
    </BrowserRouter>
  );
};

export default App;
