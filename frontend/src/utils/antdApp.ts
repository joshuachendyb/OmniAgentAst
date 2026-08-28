// 编辑历史: 2026-08-28 小欧 - 新建: 桥接antd<App>上下文的message/notification实例单例, 根治静态message不消费ConfigProvider主题导致toast显示异常/不可点击的根因 - 小欧-2026-08-28
import {
  App,
  message as staticMessage,
  notification as staticNotification,
} from 'antd';

// antd v5 静态 message/notification 不消费 ConfigProvider 主题上下文, 且在 React 树外渲染导致交互异常。
// 通过 App.useApp() 获取上下文实例并存入单例, 全局工具统一走此实例, 修复"显示不正常/点不动/点击不消失"。
type AppInstances = ReturnType<typeof App.useApp>;
type MessageInstance = AppInstances['message'];
type NotificationInstance = AppInstances['notification'];

let messageInstance: MessageInstance | null = null;
let notificationInstance: NotificationInstance | null = null;

export const setAntdInstances = (instances: AppInstances): void => {
  messageInstance = instances.message;
  notificationInstance = instances.notification;
};

// App 未挂载(首屏极早场景)时回退静态实例, 挂载后由 AntdAppBridge 覆盖
export const getMessage = (): MessageInstance =>
  messageInstance ?? staticMessage;
export const getNotification = (): NotificationInstance =>
  notificationInstance ?? staticNotification;
