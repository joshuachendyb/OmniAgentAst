import React from 'react';
import ReactDOM from 'react-dom/client';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
// 【小强 2026-04-21】§2.1.3 引入 antd v5 重置样式，统一浏览器默认样式差异
import 'antd/dist/reset.css';
// 编辑历史: 2026-08-28 小欧 - 包裹antd<App>使message/notification消费ConfigProvider主题上下文, 根治toast显示异常/不可点击 - 小欧-2026-08-28
import App from './App';
import './index.css';

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ConfigProvider locale={zhCN}>
        <AntdApp>
          <App />
        </AntdApp>
      </ConfigProvider>
    </React.StrictMode>
  );
}
