// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 抽离beforeunload会话状态保存逻辑(容量阈值/lightState降级/QuotaExceeded容错)
import { STORAGE_KEY } from './chatHistory';

interface LightChatState {
  sessionId?: string;
  sessionTitle?: string;
  timestamp: number;
  messageCount: number;
  isPaused?: boolean;
  isReceiving?: boolean;
}

/**
 * 保存会话状态到 sessionStorage。
 * 含 4MB 容量阈值判定：超阈值则降级为仅含摘要字段的 lightState；
 * 捕获 QuotaExceededError 并给出告警，其余异常以 console.error 兜底。
 *
 * @author 小欧
 * @date 2026-08-27
 */
export function saveChatState(state: unknown): void {
  try {
    const stateStr = JSON.stringify(state);
    if (stateStr.length > 4 * 1024 * 1024) {
      // 2026-08-27 小欧 三堂会审: 超限降级为轻量状态, 避免写入失败
      const s = state as {
        sessionId?: string;
        sessionTitle?: string;
        isPaused?: boolean;
        isReceiving?: boolean;
        messages?: unknown[];
      };
      const lightState: LightChatState = {
        sessionId: s.sessionId,
        sessionTitle: s.sessionTitle,
        timestamp: Date.now(),
        messageCount: s.messages?.length ?? 0,
        isPaused: s.isPaused,
        isReceiving: s.isReceiving,
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(lightState));
    } else {
      sessionStorage.setItem(STORAGE_KEY, stateStr);
    }
  } catch (e) {
    if (e instanceof DOMException && e.name === 'QuotaExceededError') {
      console.warn('⚠️ [beforeunload] sessionStorage容量满，跳过保存');
    } else {
      console.error('保存会话状态失败:', e);
    }
  }
}
