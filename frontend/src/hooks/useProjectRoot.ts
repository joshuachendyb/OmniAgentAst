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
// 2026-11-02 小欧 - 去结果缓存（北京老陈定案「每次重新取根」）：load() 只共享在途请求，
//   完成后丢弃；新增 getFreshProjectRoot() 供 chip 点击现取根 — 小欧-2026-11-02
// 2026-11-02 小欧 - 收敛为**唯一**取根函数 fetchProjectRoot()：删 getCurrentProjectRoot（读快照）
//   与 getFreshProjectRoot（与 load 重复），渲染订阅仍由 useProjectRoot 承担 — 小欧-2026-11-02
// 2026-11-02 小欧 - 设置保存监听改模块级注册一次（原每个订阅组件各注册一个）；fetchProjectRoot
//   改为 export const（去掉多余的 export{} 转发）— 小欧-2026-11-02
/**
 * useProjectRoot —— `GET /files/root` 的**唯一**取数入口（实时取数，结果不缓存）
 *
 * 只导出三件，职责互斥、不重叠：
 *  - `fetchProjectRoot()`：唯一取根函数。每次调用实时打 `/files/root`（同刻在途请求合并去重）。
 *  - `useProjectRoot()`：唯一渲染订阅。内部调 `fetchProjectRoot()`，根变化时触发重渲染。
 *  - `resolveChipUrlFresh()`：点击唯一入口。现取根 → 交 projectPath.resolvePathTarget 裁决。
 * 禁止再新增「读快照取根」的第二个入口（快照/现取并存 → 根内被判根外）。
 */
import { useEffect, useSyncExternalStore } from 'react';
import { fileApi } from '@/services/api/file.api';
import { SETTINGS_SAVED_EVT } from '@/constants/settingsEvents';
import { resolvePathTarget, type PathTargetOptions } from '@/utils/projectPath';

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

/**
 * 唯一取根函数（实时）：每次调用都打一次 `/files/root`，结果不缓存（同刻在途请求合并）。
 * 2026-11-02 小欧 - 渲染订阅、chip 点击、文件页取根全部走本函数，禁止再各自拉 /files/root — 小欧-2026-11-02
 */
export const fetchProjectRoot = (): Promise<string> => {
  if (cached) return cached;
  // 2026-11-02 小欧 - 去结果缓存（北京老陈定案「每次重新取根」）：只共享**在途请求**，
  //   一回来立即丢弃 cached → 下次调用重新打 /files/root，不再跨渲染/跨会话持旧根 — 小欧-2026-11-02
  const p = Promise.resolve()
    .then(() => fileApi.fetchRoot())
    .then((r) => {
      publish(r.project_root);
      return r.project_root;
    })
    .catch(() => {
      publish('');
      return '';
    })
    .finally(() => {
      if (cached === p) cached = null;
    });
  cached = p;
  return p;
};

const subscribe = (cb: () => void): (() => void) => {
  listeners.add(cb);
  return () => {
    listeners.delete(cb);
  };
};

const getSnapshot = (): Snapshot => snapshot;

/**
 * 通知重取 —— 项目根可能已变（设置页落盘 / 后端配置变更）时清在途并自增 gen，
 * 订阅中的 hook 重新走 `fetchProjectRoot()`。**不是取根入口**，只发信号。
 */
export const invalidateProjectRoot = (): void => {
  cached = null;
  snapshot = { ...snapshot, gen: snapshot.gen + 1 };
  notify();
};

// 2026-11-02 小欧 - 设置保存监听改模块级注册**一次**：原在 useProjectRoot 的 effect 里
//   每个订阅组件各注册一个（一屏几十个路径 = 几十个监听器），且卸载时序不同步 — 小欧-2026-11-02
if (typeof window !== 'undefined')
  window.addEventListener(SETTINGS_SAVED_EVT, invalidateProjectRoot);

export const useProjectRoot = (enabled = true): string => {
  const { root, gen } = useSyncExternalStore(
    subscribe,
    getSnapshot,
    getSnapshot
  );
  useEffect(() => {
    if (!enabled) return;
    // 2026-11-02 小欧 - 唯一取根函数（实时，不读缓存） — 小欧-2026-11-02
    void fetchProjectRoot();
  }, [enabled, gen]);
  return root;
};

/**
 * 点击时**实时取根**再算深链（所有 chip / 链接点击的唯一入口）。
 * 2026-11-02 小欧 - 自 utils/fileDeepLink.ts 移入（该文件已并入 utils/projectPath.ts）：
 *   本函数是唯一需要「取根 + 路径解析」两件事的地方，放在取根模块里避免纯判据模块
 *   反向依赖 React / 网络 — 小欧-2026-11-02
 */
export const resolveChipUrlFresh = async (
  rawPath: string,
  lineRange?: { start: number; end: number } | null,
  opts: Omit<PathTargetOptions, 'lineRange'> = {}
): Promise<string> => {
  const target = resolvePathTarget(rawPath, await fetchProjectRoot(), {
    ...opts,
    lineRange,
  });
  // 2026-11-02 小欧 - 判不过返回空串，由调用方判空不跳：原实现退回原文深链，
  //   与 FileTrailPanel 的 if(url) 口径矛盾（同一路径一处跳一处不跳）— 小欧-2026-11-02
  return target.url;
};
