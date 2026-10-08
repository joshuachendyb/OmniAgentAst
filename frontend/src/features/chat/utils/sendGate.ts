// 2026-10-08 小欧 - 文档[11] 3.5.2 新建: 发送门判据单一真源。
//   病根: ChatInput 的 sendBlocked 与 useChatSend 的 isInterject 是两处独立判断, 靠人工保持一致。

/** 插话判定: 执行中 + 开关开 = 追加输入, 否则 = 新任务 */
export const isInterjectRoute = (
  isReceiving: boolean,
  allowInterject: boolean
): boolean => isReceiving && allowInterject;

/**
 * 发送门: 执行中只看开关(开=放行插话/关=锁输入, 今天行为不变), 非执行中看 loading(防双击)。
 * loading 在整条 SSE 跑完前恒为 true(useChatSend 置位, 故意交给 SSE 终态复位), 不可裸当"发送中"用。
 */
export const isSendBlocked = (
  loading: boolean,
  isReceiving: boolean,
  allowInterject: boolean
): boolean => (isReceiving ? !allowInterject : loading);
