/**
 * 应用入口组件 - App.tsx
 *
 * 功能：应用根组件，整合Layout布局和路由
 *
 * Phase 2 P2 优化：路由懒加载 - 减少首屏 bundle 大小
 *
 * @author 小新
 * @version 3.2.0
 * @since 2026-02-17
 * @update 2026-02-18 集成React Router，支持多页面路由 - by 小新
 * @update 2026-04-12 添加路由懒加载 - by 小强
 * @update 2026-06-09 删除未使用的SecurityProvider - by 小沈
 */

import React, { Suspense, lazy } from 'react';
// 编辑历史: 2026-09-09 小欧 - 根挂 ErrorBoundary 包住 RouterContent: 渲染期异常(含 dev HMR hook 变更崩溃)
//   从整页白屏降级为 Result 提示 + 一键刷新 — 小欧-2026-09-09
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import AppLayout from './components/Layout';
import ChatPage from './pages/ChatPage';
import { AppProvider } from './contexts/AppContext';
// 编辑历史: 2026-08-28 小欧 - 挂载AntdAppBridge桥接antd<App>上下文message/notification实例 - 小欧-2026-08-28
import { AntdAppBridge } from './lib/antd/bridge';
// 2026-09-09 小欧: 应用级错误边界(渲染异常白屏兜底)
import { ErrorBoundary } from './components/ErrorBoundary';
// 编辑历史: 2026-09-26 小欧 - [72]第九章(9.6-4): 引入登录页（访问口令输入）
import LoginPage from './pages/LoginPage';

// 路由懒加载 - 减少首屏 bundle 大小
const HistoryPage = lazy(() => import('./pages/History'));
const Settings2 = lazy(() => import('./pages/Settings2')); // 2026-09-20 小强 - 设置2版（6 Tab + 模型管理）
// 编辑历史: 2026-09-21 小欧 - 旧设置页(pages/Settings=settings1版)整体退休: 移除 /settings 路由与懒加载, 唯一入口为 /settings2(settings2版)

// 懒加载加载中组件
const LazyLoadingFallback: React.FC = () => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      height: '100vh',
      color: '#999',
      fontSize: '14px',
    }}
  >
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

  // 编辑历史: 2026-09-26 小欧 - [72]第九章(9.6-4): 新增 /login 路由（输入访问口令）。
  //   登录页**不进 AppLayout**（无侧边栏/顶栏），避免未鉴权用户看到界面骨架。
  //   逻辑: 未登录访问任意页 → 401 拦截器跳 /login；已登录正常进入。
  // @update 2026-09-26 [72]第九章: 新增 /login 路由 — by 小欧
  if (location.pathname === '/login') {
    return <LoginPage />;
  }

  return (
    <AppLayout activeKey={location.pathname}>
      <Suspense fallback={<LazyLoadingFallback />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ChatPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="/settings2" element={<Settings2 />} />
          {/* 默认重定向到首页 */}
          <Route path="*" element={<ChatPage />} />
        </Routes>
      </Suspense>
    </AppLayout>
  );
};

/**
 * 应用主组件
 *
 * 变更记录：
 * - v3.2.0 (2026-06-09 by 小沈): 删除未使用的SecurityProvider
 * - v3.0.0 (2026-02-18 by 小新): 集成React Router，支持多页面路由
 * - v2.0.0 (2026-02-17 by 小新): 重构为左右分栏布局，使用AppLayout组件
 * - v1.0.0: 初始版本，单栏布局
 */
const App: React.FC = () => {
  return (
    <BrowserRouter unstable_useTransitions={false}>
      <AppProvider>
        <AntdAppBridge />
        <ErrorBoundary>
          <RouterContent />
        </ErrorBoundary>
      </AppProvider>
    </BrowserRouter>
  );
};

export default App;
