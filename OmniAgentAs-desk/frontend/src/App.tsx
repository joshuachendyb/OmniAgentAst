/**
 * 应用入口组件 - App.tsx
 * 
 * 功能：应用根组件，整合Layout布局和路由
 * 
 * @author 小新
 * @version 3.0.0
 * @since 2026-02-17
 * @update 2026-02-18 集成React Router，支持多页面路由 - by 小新
 */

import React from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import AppLayout from './components/Layout';
import Chat from './components/Chat';
import HistoryPage from './pages/History';
import Settings from './pages/Settings';

/**
 * 路由内容组件
 * 
 * 功能：根据当前路由渲染不同页面，并传递activeKey给Layout
 * 
 * @author 小新
 */
const RouterContent: React.FC = () => {
  const location = useLocation();
  
  return (
    <AppLayout activeKey={location.pathname}>
      <Routes>
        <Route path="/" element={<Chat />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/settings" element={<Settings />} />
        {/* 默认重定向到首页 */}
        <Route path="*" element={<Chat />} />
      </Routes>
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
      <RouterContent />
    </BrowserRouter>
  );
};

export default App;
