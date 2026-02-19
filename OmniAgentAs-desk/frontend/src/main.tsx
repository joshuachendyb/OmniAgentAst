import React from 'react'
import ReactDOM from 'react-dom/client'
import { ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import App from './App'
import { SecurityProvider } from './contexts/SecurityContext'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConfigProvider locale={zhCN}>
      <SecurityProvider>
        <App />
      </SecurityProvider>
    </ConfigProvider>
  </React.StrictMode>,
)
