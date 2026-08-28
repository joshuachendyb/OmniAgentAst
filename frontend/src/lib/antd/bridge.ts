// 编辑历史: 2026-08-28 小欧 - 合并antdApp.ts+antdAppBridge.tsx为单一bridge模块, 桥接antd<App>上下文的message/notification实例单例
import React, { useEffect } from 'react';
import {
  App,
  message as staticMessage,
  notification as staticNotification,
} from 'antd';

type AppInstances = ReturnType<typeof App.useApp>;
type MessageInstance = AppInstances['message'];
type NotificationInstance = AppInstances['notification'];

let messageInstance: MessageInstance | null = null;
let notificationInstance: NotificationInstance | null = null;

export const setAntdInstances = (instances: AppInstances): void => {
  messageInstance = instances.message;
  notificationInstance = instances.notification;
};

export const getMessage = (): MessageInstance =>
  messageInstance ?? staticMessage;
export const getNotification = (): NotificationInstance =>
  notificationInstance ?? staticNotification;

export const AntdAppBridge: React.FC = () => {
  const instances = App.useApp();
  useEffect(() => {
    setAntdInstances(instances);
  }, [instances]);
  return null;
};
