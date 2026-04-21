import React from "react";
import ReactDOM from "react-dom/client";
import { ConfigProvider } from "antd";
import zhCN from "antd/locale/zh_CN";
// 【小强 2026-04-21】§2.1.3 引入 antd v5 重置样式，统一浏览器默认样式差异
import "antd/dist/reset.css";
import App from "./App";
import { SecurityProvider } from "./contexts/SecurityContext";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <SecurityProvider>
        <App />
      </SecurityProvider>
    </ConfigProvider>
  </React.StrictMode>
);
