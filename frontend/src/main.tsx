import React from 'react';
import ReactDOM from 'react-dom/client';
import { App as AntdApp, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
// 【小强 2026-04-21】引入 antd v5 重置样式，统一浏览器默认样式差异
import 'antd/dist/reset.css';
// 编辑历史: 2026-08-28 小欧 - 包裹antd<App>使message/notification消费ConfigProvider主题上下文, 根治toast显示异常/不可点击 - 小欧-2026-08-28
// 编辑历史: 2026-09-15 小欧 - 全站Tooltip白底浅卡片统一(北京老陈令, 效果最佳标准):
//   页面整体为白底浅色体系, AntD默认黑底黑块突兀且灰字对黑底对比度仅1.9:1不可读;
//   colorBgSpotlight=#fff+colorTextLightSolid=#595959后, 全站53处Tooltip与页面视觉同语言,
//   现有5档灰阶(Color TERTIARY#999等)白底全部自然可读;
//   【三堂会审修正】箭头背景由antd ::before + --antd-arrow-background-color变量自动继承colorBgSpotlight,
//   白底shadow/radius走antd自带boxShadowSecondary+tooltipBorderRadius, 无需index.css任何覆盖(YAGNI/DRY) — 小欧-2026-09-15
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.3: main.tsx 注入 setTransportConfig(baseURL)（render 前模块级一次）— 小欧-2026-09-29 21:37:55
import App from './App';
import './index.css';
// [63] 5.3：SSE 传输层连接参数模块级注入一次（替代 useSSE 的 React 入参；React render 前注入）。
//   口令不传——传输层 authHeaders() 每次请求现取 getAccessToken()，登录/改口令后即时生效
//   （原 useSSE config.token 全仓 0 处赋值 → Authorization 从不附带，2026-09-26 缺陷不复现）。
import { setTransportConfig } from './features/chat/streams/chatStreamTransport';
import { API_BASE_URL } from './services/api/client';

setTransportConfig({ baseURL: API_BASE_URL });

const rootElement = document.getElementById('root');
if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ConfigProvider
        locale={zhCN}
        theme={{
          components: {
            Tooltip: {
              colorBgSpotlight: '#ffffff',
              colorTextLightSolid: '#595959',
            },
          },
        }}
      >
        <AntdApp>
          <App />
        </AntdApp>
      </ConfigProvider>
    </React.StrictMode>
  );
}
