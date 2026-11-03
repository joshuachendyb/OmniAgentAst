/**
 * foregroundSessionStore — 会话页「此刻正在显示哪个会话」的单一发布口 (创建: 2026-11-03 小欧)
 * ChatPage 发布、AppLayout 只读(URL `/` 无参数时与画面不一致, 页面才是权威); mounted 与 sessionId 分开: 无会话顶栏静止。
 * 编辑历史: 2026-11-03 小欧 - 新建: 顶栏主语由页面发布(useSyncExternalStore), mounted/sessionId 双字段表达两种口径。
 */

import { useSyncExternalStore } from 'react';

export interface ForegroundSession {
  /** 会话页是否在眼前 */
  mounted: boolean;
  /** 会话页正在显示的会话 id; null = 无(新建空会话/尚未解析) */
  sessionId: string | null;
}

const DETACHED: ForegroundSession = { mounted: false, sessionId: null };
let current: ForegroundSession = DETACHED;
const listeners = new Set<() => void>();

const emit = (): void => {
  listeners.forEach((fn) => fn());
};

/** 会话页挂载/切换会话时调用。
 *  调用点用 useLayoutEffect: useEffect 在绘制后跑, 会先闪一帧"别的会话/最新在跑"的状态。 */
export function publishForegroundSession(sessionId: string | null): void {
  if (current.mounted && current.sessionId === sessionId) return;
  current = { mounted: true, sessionId };
  emit();
}

/** 会话页卸载时调用: 主语交还「开跑最晚且仍在跑」口径 */
export function clearForegroundSession(): void {
  if (!current.mounted) return;
  current = DETACHED;
  emit();
}

export function getForegroundSession(): ForegroundSession {
  return current;
}

const subscribe = (fn: () => void): (() => void) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};

/** 订阅口: 未变更时返回同一对象引用, 无谓重渲为零 */
export function useForegroundSession(): ForegroundSession {
  return useSyncExternalStore(
    subscribe,
    getForegroundSession,
    getForegroundSession
  );
}
