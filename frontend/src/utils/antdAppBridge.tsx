// 编辑历史: 2026-08-28 小欧 - 新建: AntdAppBridge 桥接组件, 在<App>上下文内调用App.useApp()注入message/notification实例到antdApp单例 - 小欧-2026-08-28
import React, { useEffect } from 'react';
import { App } from 'antd';
import { setAntdInstances } from './antdApp';

// 必须渲染在 antd <App> 内部, 才能拿到消费 ConfigProvider 上下文的 message/notification 实例
export const AntdAppBridge: React.FC = () => {
  const instances = App.useApp();
  useEffect(() => {
    setAntdInstances(instances);
  }, [instances]);
  return null;
};
