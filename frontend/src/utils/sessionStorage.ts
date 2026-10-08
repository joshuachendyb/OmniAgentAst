// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 抽离beforeunload会话状态保存逻辑(容量阈值/lightState降级/QuotaExceeded容错)
// 2026-09-30 小欧 [63]7.x - 实施: 新增 readStoredSessionId(),供 App 壳解析"当前会话"用
//   病根: 左侧菜单「对话任务」navigate('/') 不带 session_id,会话归属隐式依赖本键的缓存;
//   缓存缺失/降级时静默漂到"最近会话",无显式契约。本函数是该 storage 结构的唯一读出口,
//   避免调用方各自 getItem+JSON.parse(重复解析反模式)。 — 小欧-2026-09-30
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.10.3(a′): 降级态载荷补 linkEnabled(3 处写入点中的第 3 处)。
//   beforeunload 抽离路径若不带该字段, 页面关闭再打开时镜像缺值。 — 小欧-2026-10-03
// 编辑历史: 2026-10-05 小欧 - 降级态载荷补 sessionModel + 改走 buildChatCacheState(缓存 schema 单一来源):
//   同 linkEnabled 同型事故 —— 本写入点漏字段会让刷新后模型选择器误显示"跟随全局"
//   (老陈 2026-10-05 报: 刷新后输入框自动跟随全局, 但新任务仍用会话覆盖的 glm-5.2)。 — 小欧-2026-10-05
import {
  STORAGE_KEY,
  buildChatCacheState,
  type ChatCacheState,
} from './chatHistory';

// 2026-10-05 小欧 - 降级态(4MB 超限)形状收窄为 ChatCacheState 的子集, 不另立平行 interface
type LightChatState = ChatCacheState & { messageCount: number };

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
    const stateStr = buildChatCacheState(state as ChatCacheState);
    if (stateStr.length > 4 * 1024 * 1024) {
      // 2026-08-27 小欧 三堂会审: 超限降级为轻量状态, 避免写入失败
      // 2026-10-05 小欧: 降级分支补 sessionModel(与全量分支同字段, 否则超限会话同样丢模型选择器状态)
      const s = state as ChatCacheState;
      const lightState: LightChatState = {
        sessionId: s.sessionId,
        sessionTitle: s.sessionTitle,
        timestamp: Date.now(),
        messageCount: s.messages?.length ?? 0,
        isPaused: s.isPaused,
        isReceiving: s.isReceiving,
        linkEnabled: s.linkEnabled,
        allowInterject: s.allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.6: 写入点③(降级态)
        sessionVersion: s.sessionVersion,
        sessionModel: s.sessionModel ?? null,
      };
      sessionStorage.setItem(STORAGE_KEY, buildChatCacheState(lightState));
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
