// 编辑历史: 2026-10-05 小欧 - 新建: 设置保存广播事件名(唯一定义点)
//   动因: 设置页(settings2)保存成功后要通知 chat 页的 step 渲染偏好 hook 刷新,
//   但共享的只是一个事件名字符串。此前它定义在 chat 渲染目录的 hook 文件里, 导致
//   settings2 → features/chat/components/pipeline 的跨 feature 反向依赖
//   (全仓 @/features/* 互引 12 处, 其余 11 处均为 feature 内部, 跨 feature 先例为零),
//   且 chat 目录任何重构/删除 pipeline 文件都会连带打断设置页保存。
//   处置: 常量上移本中立层, 依赖方向由下向上(settings2 与 chat 各自依赖本文件),
//   不再由设置域反向依赖渲染域 —— 小欧-2026-10-05
//
//   事件语义: 设置页 saveKeys 落盘成功后派发; 订阅方收到后重取真值(不携带payload,
//   全量重取, 避免"事件里塞一份设置副本"形成第二真源)。

/** 设置保存成功广播事件名(唯一定义点; 生产侧仅 useSettings.saveKeys 派发, 消费侧仅 useStepRenderPrefs 订阅) */
export const SETTINGS_SAVED_EVT = 'omni-settings-saved';
