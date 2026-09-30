// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 抽离beforeunload会话状态保存逻辑(容量阈值/lightState降级/QuotaExceeded容错)
// 2026-09-30 小欧 [63]7.x - 实施: 新增 readStoredSessionId(),供 App 壳解析"当前会话"用
//   病根: 左侧菜单「对话任务」navigate('/') 不带 session_id,会话归属隐式依赖本键的缓存;
//   缓存缺失/降级时静默漂到"最近会话",无显式契约。本函数是该 storage 结构的唯一读出口,
//   避免调用方各自 getItem+JSON.parse(重复解析反模式)。 — 小欧-2026-09-30
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

/**
 * 读取已保存的当前会话 id（不抛异常，缺失/损坏一律返回 null）。
 *
 * 用途：菜单「对话任务」显式回到当前会话（[63] 7.x）。
 * 语义与 saveChatState 对称：降级写入的 lightState 同样含 sessionId，故两种形态都读得到。
 * 解析失败返回 null 而非抛出——菜单导航不可因存储损坏而中断。
 *
 * @author 小欧
 * @date 2026-09-30
 */
export function readStoredSessionId(): string | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { sessionId?: string };
    return parsed?.sessionId || null;
  } catch (e) {
    console.warn('读取已存会话 id 失败，按无当前会话处理:', e);
    return null;
  }
}
