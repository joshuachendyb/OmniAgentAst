// 编辑历史: 2026-10-21 小杨 - 新建：recent-files 共享 hook（模块级缓存，三处共用） — 小杨-2026-10-21
// 编辑历史: 2026-10-22 小欧 - 请求失败不再缓存空数组：原实现 catch 后仍 cache.set(空)，
//   一次网络抖动即致足迹面板与树上 ● 集体空态至手动刷新；改为失败只删在途项，下次请求重试 — 小欧-2026-10-22
/**
 * useRecentFiles —— `/files/recent-files` 的**唯一**取数入口（共享缓存）
 *
 * 为什么要有这个 hook：
 * - 树上的 `●` 标记（files 页）、足迹面板（会话页）、推荐行（会话页）
 *   **三处消费同一份数据**，各拉各的会出现"树上标了 ●、面板里没有"的不一致，
 *   且一次会话触发 3 次相同请求。
 * - 故：模块级缓存 + 订阅式复用 —— 同一 sessionId 只发一次请求，三处共享同一份状态。
 *
 * 语义：
 * - 404 / 请求失败 → 静默降级为空态（该标记本就是锦上添花，报错反而吵）
 * - 不轮询；刷新由调用方显式调用 `reload()`（文件页工具条刷新一并刷足迹）
 */
import { useCallback, useEffect, useState } from 'react';
import { fileApi, type RecentFile } from '@/services/api/file.api';

interface CacheEntry {
  files: RecentFile[];
  promise: Promise<RecentFile[]>;
}

const cache = new Map<string, CacheEntry>();
const subscribers = new Map<string, Set<(files: RecentFile[]) => void>>();

const publish = (sessionId: string, files: RecentFile[]) => {
  subscribers.get(sessionId)?.forEach((cb) => cb(files));
};

const load = (sessionId: string): Promise<RecentFile[]> => {
  const hit = cache.get(sessionId);
  if (hit) return hit.promise;
  const promise = fileApi
    .fetchRecentFiles(sessionId)
    .then((files) => {
      cache.set(sessionId, { files, promise: Promise.resolve(files) });
      publish(sessionId, files);
      return files;
    })
    .catch(() => {
      // 2026-10-22 小欧 - 失败**不缓存空**
      //   原实现 .catch(()=>[]) 之后仍 cache.set(空数组) → 一次网络抖动后足迹面板与
      //   树上 ● 集体空态直到手动刷新（本 hook 无自动失效）。改法：失败只删本次在途项
      //   （cur.promise===promise 防误删 reload() 的新请求），下次调用重新请求。
      const cur = cache.get(sessionId);
      if (cur && cur.promise === promise) cache.delete(sessionId);
      publish(sessionId, []);
      return [] as RecentFile[];
    });
  cache.set(sessionId, { files: [], promise });
  return promise;
};

export interface UseRecentFilesResult {
  files: RecentFile[];
  loading: boolean;
  /** 显式重取（文件页「↻刷新」用；不轮询） */
  reload: () => Promise<RecentFile[]>;
}

/**
 * @param sessionId 会话 id；为空则返回空态（不请求）
 */
export const useRecentFiles = (
  sessionId?: string | null
): UseRecentFilesResult => {
  const [files, setFiles] = useState<RecentFile[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!sessionId) {
      setFiles([]);
      setLoading(false);
      return;
    }
    let alive = true;
    setLoading(true);
    const cached = cache.get(sessionId);
    if (cached) setFiles(cached.files);
    const sub = (next: RecentFile[]) => {
      if (alive) setFiles(next);
    };
    subscribers.set(
      sessionId,
      (subscribers.get(sessionId) ?? new Set()).add(sub)
    );
    load(sessionId)
      .then((next) => {
        if (alive) setFiles(next);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
      const set = subscribers.get(sessionId);
      set?.delete(sub);
      if (set && set.size === 0) subscribers.delete(sessionId);
    };
  }, [sessionId]);

  const reload = useCallback(async () => {
    if (!sessionId) return [];
    cache.delete(sessionId);
    const next = await load(sessionId);
    setFiles(next);
    return next;
  }, [sessionId]);

  return { files, loading, reload };
};
