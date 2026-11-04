/**
 * runningTasksStore — 「此刻有哪些任务在跑」的唯一读取口与唯一合并口 (创建: 2026-11-03 小欧)
 * 真源 = 后端 GET /sessions/tasks/running(chat_tasks 非终态且非 idle): 前端内存只表达"本页见过什么"。
 * 编辑历史: 2026-11-03 小欧 - 新建: 合并收口 getMergedRunningTasks, 消费收口 useMergedRunningTasks, 拉取单飞。
 */

import { useSyncExternalStore } from 'react';

import { sessionApi, type RunningTask } from '@/services/api/session.api';
import { getActiveSessionStatusList, toStreamStatus } from './chatStreamStore';
import type { StreamStatus } from './backupTypes';

/** 一条"在跑"任务的前端口径视图: 状态已归一到 StreamStatus, 开跑时刻已解析为 epoch ms */
export interface RunningTaskView {
  taskId: string;
  sessionId: string;
  status: StreamStatus;
  /** 任务自身开跑时刻(epoch ms, 0=未知), 排序与"是否新于快照"共用 */
  startedAt: number;
}

const EMPTY: RunningTaskView[] = [];
let current: RunningTaskView[] = EMPTY;
/** 当前快照的请求发起时刻(epoch ms); 0 = 还没有成功快照过 */
let snapshotAt = 0;
let inflight: Promise<void> | null = null;

/** 合并视图的采样周期: 内存侧(chatStreamStore)没有变更事件可订阅, 1s 内必被看到,
 *  与 useStreamPulse 同频(顶栏/历史页本来就在 1s 粒度上刷新) — 小欧-2026-11-03 */
const MERGED_TICK_MS = 1000;
const mergedListeners = new Set<() => void>();
let mergedTimer: number | null = null;
/** 合并视图缓存: useSyncExternalStore 要求"内容不变即同一引用", 否则每秒重渲 */
let mergedCache: RunningTaskView[] = EMPTY;

const emit = (): void => {
  mergedListeners.forEach((fn) => fn());
};

const toView = (t: RunningTask): RunningTaskView => ({
  taskId: t.task_id,
  sessionId: t.session_id,
  status: toStreamStatus(t.status),
  startedAt: Date.parse(t.created_at) || 0,
});

/** 内容不变就不换引用: 无谓重渲为零 */
const sameTasks = (a: RunningTaskView[], b: RunningTaskView[]): boolean =>
  a.length === b.length &&
  a.every(
    (t, i) =>
      t.taskId === b[i].taskId &&
      t.sessionId === b[i].sessionId &&
      t.status === b[i].status &&
      t.startedAt === b[i].startedAt
  );

/** 单飞拉取: 聚焦/挂载/列表重载叠在一起也只发一次请求。失败静默保留旧值(留痕, 便于排查)。 */
export function refreshRunningTasks(): Promise<void> {
  if (inflight) return inflight;
  const at = Date.now();
  inflight = sessionApi
    .listRunningTasks()
    .then((r) => {
      const next = (r.tasks ?? []).map(toView);
      // 快照时刻必须先落: 合并判据"内存任务是否新于本快照"依赖它, 与内容是否变化无关
      snapshotAt = at;
      if (sameTasks(current, next)) return;
      current = next;
      emit();
    })
    .catch((e) => {
      // 后端不可达/接口缺失: 保留上次结果(不动 snapshotAt, 内存任务继续兜底), 不影响页面其余功能
      console.warn('[runningTasks] 拉取在跑任务失败(保留上次结果):', e);
    })
    .finally(() => {
      inflight = null;
    });
  return inflight;
}

/**
 * 在跑任务的唯一合并口(后端 ∪ 内存, 后端优先) — 小欧-2026-11-03
 * 后端列出的任务用后端状态(权威); 内存独有任务仅当开跑晚于快照请求时刻才保留(快照后新起), 否则视为已终态。
 */
export function getMergedRunningTasks(): RunningTaskView[] {
  const known = new Set(current.map((t) => t.taskId));
  const fresh: RunningTaskView[] = [];
  for (const m of getActiveSessionStatusList()) {
    if (m.taskId === null || known.has(m.taskId)) continue;
    if (m.startedAt <= snapshotAt) continue; // 早于快照仍未列出 = 后端已终态
    fresh.push({
      taskId: m.taskId,
      sessionId: m.sessionId,
      status: m.status,
      startedAt: m.startedAt,
    });
  }
  // 开跑晚的新任务在前, 其余按后端 created_at DESC 的既有顺序; 统一再按开跑时刻降序稳定一次
  return [...fresh, ...current].sort((a, b) => b.startedAt - a.startedAt);
}

const subscribeMerged = (fn: () => void): (() => void) => {
  mergedListeners.add(fn);
  if (mergedTimer === null) {
    mergedTimer = window.setInterval(() => {
      mergedListeners.forEach((f) => f());
    }, MERGED_TICK_MS);
  }
  return () => {
    mergedListeners.delete(fn);
    if (mergedListeners.size === 0 && mergedTimer !== null) {
      window.clearInterval(mergedTimer);
      mergedTimer = null;
    }
  };
};

/** 合并视图的稳定快照: 内容不变返回上一引用(否则 useSyncExternalStore 每秒重渲) */
const readMerged = (): RunningTaskView[] => {
  const next = getMergedRunningTasks();
  if (sameTasks(mergedCache, next)) return mergedCache;
  mergedCache = next;
  return next;
};

/** 在跑任务的唯一消费口(历史页角标/一览条、顶栏浮层共用) — 小欧-2026-11-03
 *  返回后端快照 ∪ 内存新任务的合并结果(见 getMergedRunningTasks), 1s 采样。 */
export function useMergedRunningTasks(): RunningTaskView[] {
  return useSyncExternalStore(subscribeMerged, readMerged, readMerged);
}
