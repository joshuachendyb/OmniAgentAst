/**
 * hitlPendingStore — HITL 待处理项集合（跨会话感知 + 断线对账）— 商量 2026-11-24
 *
 * 解决的问题：确认/问询原来只在"发起它的那条内容流"上才可见——用户切到别的会话/历史页时，
 *   完全不知道有活要干，只能等回到那个会话才弹出。本 store 汇集全站待处理项，供顶栏角标提示。
 *
 * 分工（三层不可混）：
 *   ① 本 store     = 「有哪些待处理项」的索引：只有 hitl_id / kind / task_id / session_id / 时间。
 *                    **不做弹窗**——弹窗正文（params、安全级别、题目）由内容流的 interact 帧提供。
 *   ② 内容流       = 弹窗详情的唯一来源（interactHandlers 写 pendingAuthorization/pendingQuestion）。
 *   ③ 本 store 点击 = 跳转到对应会话，由内容流自然把弹窗渲染出来。
 *
 * 可靠性（信封可丢 → 必须有对账）：
 *   · 实时：订阅 EventBus 信封（hitl_pending 增 / hitl_settled 删）；
 *   · 兜底：每次重连成功、以及页面重新可见时，拉 GET /chat/hitl/pending 全量重建。
 *     这是"断线期间丢信封"的唯一补偿手段——只靠信封会永久遗漏。
 *
 * 编辑历史: 2026-11-24 商量 - 新建: HITL 待处理项跨会话汇集 store, 订阅 EventBus 信封实时更新 + 重连对账兜底
 */
import { useSyncExternalStore } from 'react';

import { API_BASE_URL, getAccessToken } from '@/services/api/client';

/** 与 sessionEventsStore 同源：原生 fetch 绕过 axios 拦截器，鉴权头必须现取 */
function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export type HitlKind = 'confirm' | 'question';

export interface HitlPendingItem {
  hitl_id: string;
  kind: HitlKind;
  task_id: string;
  session_id: string | null;
  /** confirm: 工具名；question: 无（空串） */
  tool_name?: string;
  /** question 的题量 */
  count?: number;
  created_at: number;
  age_s?: number;
}

const items = new Map<string, HitlPendingItem>();
const listeners = new Set<() => void>();
/** 快照引用缓存：内容不变必须返回同一引用，否则 useSyncExternalStore 每次重渲 */
let snapshot: HitlPendingItem[] = [];
let inflight: Promise<void> | null = null;

function rebuild(): void {
  const next = [...items.values()].sort((a, b) => a.created_at - b.created_at);
  // 同上：内容不变就换回旧引用，避免无谓重渲
  const same =
    next.length === snapshot.length &&
    next.every(
      (x, i) =>
        x.hitl_id === snapshot[i].hitl_id && x.age_s === snapshot[i].age_s
    );
  if (same) return;
  snapshot = next;
  listeners.forEach((fn) => fn());
}

/** 收到 hitl_pending 信封：加入集合（幂等，同 id 覆盖） */
export function addPending(
  hitlId: string,
  kind: HitlKind,
  taskId: string,
  sessionId: string | null,
  extra?: { toolName?: string; count?: number }
): void {
  if (!hitlId) return;
  const prev = items.get(hitlId);
  items.set(hitlId, {
    hitl_id: hitlId,
    kind,
    task_id: taskId,
    session_id: sessionId ?? prev?.session_id ?? null,
    tool_name: extra?.toolName ?? prev?.tool_name ?? '',
    count: extra?.count ?? prev?.count,
    created_at: prev?.created_at ?? Date.now() / 1000,
  });
  rebuild();
}

/** 收到 hitl_settled 信封：移除（其他端已处理，本端角标同步消失） */
export function removePending(hitlId: string): void {
  if (items.delete(hitlId)) rebuild();
}

/** 全站待处理项快照（引用稳定，供 useSyncExternalStore） */
export function getHitlPendingSnapshot(): HitlPendingItem[] {
  return snapshot;
}

const subscribe = (fn: () => void): (() => void) => {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
};

/**
 * 权威对账：拉 GET /chat/hitl/pending 全量替换集合。
 * 单飞（并发调用只发一次请求）；失败静默保留旧值（下次可见性变化/重连会再拉）。
 */
export function refreshHitlPending(): Promise<void> {
  if (inflight) return inflight;
  inflight = fetch(`${API_BASE_URL}/chat/hitl/pending`, {
    headers: authHeaders(),
  })
    .then((r) => r.json())
    .then((res: { success?: boolean; items?: HitlPendingItem[] }) => {
      if (res?.success === false) {
        console.warn('[hitlPending] 后端查询失败，保留旧集合');
        return;
      }
      items.clear();
      (res?.items ?? []).forEach((it) => {
        if (it?.hitl_id) items.set(it.hitl_id, it);
      });
      rebuild();
    })
    .catch((e) => {
      // 后端不可达：保留旧集合，不清空（否则角标会闪一下没了）
      console.warn('[hitlPending] 对账失败(保留上次结果):', e);
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/** 组件订阅：全站待处理项列表 */
export function useHitlPending(): HitlPendingItem[] {
  return useSyncExternalStore(
    subscribe,
    getHitlPendingSnapshot,
    getHitlPendingSnapshot
  );
}
