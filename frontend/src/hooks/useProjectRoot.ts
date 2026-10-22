// 编辑历史: 2026-10-21 小杨 - 新建：项目根一次性取数（模块级缓存，多处共用） — 小杨-2026-10-21
// 2026-10-22 小欧 - 增 enabled：纯文本/无绝对路径的 markdown 不必打 /files/root — 小欧-2026-10-22
// 2026-10-22 小欧 - 取数调用包 Promise.resolve().then()：fileApi.fetchRoot() **同步抛出**时
//   （api 模块方法缺失/被 mock 掉/内部同步抛错）异常会绕过 .catch 逃进 useEffect，
//   React 提交期报错 → 整块消息列表/文件页崩溃；包一层后同步抛出转成 rejection，
//   由 .catch 统一降级为空根 + 不缓存 — 小欧-2026-10-22
// 2026-10-22 小欧 - 缓存可失效：改 useSyncExternalStore 订阅式缓存 + 导出 invalidateProjectRoot()。
//   动因：项目根来自全局配置 workspace.project_root（后端 config.get_project_root()），
//   设置页改完落盘后前端仍拿旧根做绝对↔相对路径换算 → 链接指向错位置（过期根）。
//   失效触发：复用既有 SETTINGS_SAVED_EVT 广播（与 useStepRenderPrefs 同款订阅法，
//   不另立事件名、不在事件里塞 payload —— 与 constants/settingsEvents.ts 的事件语义一致）。
//   失效时**保留旧根**直到新根取回，避免刷新瞬间所有 chip 闪成相对路径。 — 小欧-2026-10-22
/**
 * useProjectRoot —— `GET /files/root` 的**唯一**取数入口（模块级订阅式缓存）
 *
 * 用途：把工具参数里的**绝对路径**转成文件页深链用的**相对路径**（PathLink / FileRefChip）。
 * 缓存理由：同一页面可能渲染几十个 path 参数，参数视图与规格表两个入口都要用 ——
 *   每次各拉一次 /files/root 是纯浪费（后端无 IO，但多一次往返）。
 */
import { useEffect, useSyncExternalStore } from 'react';
import { fileApi } from '@/services/api/file.api';
import { SETTINGS_SAVED_EVT } from '@/constants/settingsEvents';

/** 缓存快照：root=当前项目根；gen=失效代号（每次失效自增，驱动订阅方重取） */
type Snapshot = { root: string; gen: number };

let snapshot: Snapshot = { root: '', gen: 0 };
/** 在途请求（去重：多个组件同时要根只发一次） */
let cached: Promise<string> | null = null;
const listeners = new Set<() => void>();

const notify = (): void => {
  listeners.forEach((cb) => cb());
};

const publish = (root: string): void => {
  if (snapshot.root === root) return;
  snapshot = { ...snapshot, root };
  notify();
};

const load = (): Promise<string> => {
  if (cached) return cached;
  // 2026-10-22 小欧 - fetchRoot() 包在 Promise.resolve().then() 里：同步抛出也能落到 .catch
  //   （否则异常逃出 useEffect → React 提交期报错 → 整块渲染崩） — 小欧-2026-10-22
  cached = Promise.resolve()
    .then(() => fileApi.fetchRoot())
    .then((r) => {
      publish(r.project_root);
      return r.project_root;
    })
    .catch(() => {
      cached = null; // 失败不缓存（下次可重试）
      publish('');
      return '';
    });
  return cached;
};

const subscribe = (cb: () => void): (() => void) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};

const getSnapshot = (): Snapshot => snapshot;

/**
 * 失效项目根缓存 —— 项目根改了（设置页改 workspace.project_root 落盘 / 后端配置变更）后调用。
 * 清掉在途与缓存并自增 gen → 订阅中的 hook 重取真值（与 SETTINGS_SAVED_EVT 订阅方同一套路）。
 */
export const invalidateProjectRoot = (): void => {
  cached = null;
  snapshot = { ...snapshot, gen: snapshot.gen + 1 };
  notify();
};

export const useProjectRoot = (enabled = true): string => {
  const { root, gen } = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getSnapshot
  );
  useEffect(() => {
    if (!enabled) return;
    void load();
    // 2026-10-22 小欧 - 设置保存后失效重取（项目根可能刚被改） — 小欧-2026-10-22
    const onSettingsSaved = () => invalidateProjectRoot();
    window.addEventListener(SETTINGS_SAVED_EVT, onSettingsSaved);
    return () =>
      window.removeEventListener(SETTINGS_SAVED_EVT, onSettingsSaved);
  }, [enabled, gen]);
  return root;
};
