/**
 * 应用入口组件 - App.tsx
 * 
 * 功能：应用根组件，整合Layout布局和路由
 * 
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-17
 * @update 重构为左右分栏布局，新增导航功能 - by 小新
 */

import React from 'react';
import AppLayout from './components/Layout';
import Chat from './components/Chat';

/**
 * 应用主组件
 * 
 * 变更记录：
 * - v2.0.0 (2026-02-17 by 小新): 重构为左右分栏布局，使用AppLayout组件
 * - v1.0.0: 初始版本，单栏布局
 */
const App: React.FC = () => {
  return (
    <AppLayout activeKey="/">
      <Chat />
    </AppLayout>
  );
};

export default App;
