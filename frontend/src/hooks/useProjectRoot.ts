// 编辑历史: 2026-10-21 小杨 - 新建：项目根一次性取数（模块级缓存，多处共用） — 小杨-2026-10-21
// 2026-10-22 小欧 - 增 enabled：纯文本/无绝对路径的 markdown 不必打 /files/root — 小欧-2026-10-22
// 2026-10-22 小欧 - 取数调用包 Promise.resolve().then()：fileApi.fetchRoot() **同步抛出**时
//   （api 模块方法缺失/被 mock 掉/内部同步抛错）异常会绕过 .catch 逃进 useEffect，
//   React 提交期报错 → 整块消息列表/文件页崩溃；包一层后同步抛出转成 rejection，
//   由 .catch 统一降级为空根 + 不缓存 — 小欧-2026-10-22
/**
 * useProjectRoot —— `GET /files/root` 的**唯一**取数入口（模块级缓存）
 *
 * 用途：把工具参数里的**绝对路径**转成文件页深链用的**相对路径**（PathLink）。
 * 缓存理由：同一页面可能渲染几十个 path 参数，参数视图与规格表两个入口都要用 ——
 *   每次各拉一次 /files/root 是纯浪费（后端无 IO，但多一次往返）。
 */
import { useEffect, useState } from 'react';
import { fileApi } from '@/services/api/file.api';

let cached: Promise<string> | null = null;
let cachedValue = '';

const load = (): Promise<string> => {
  if (cached) return cached;
  // 2026-10-22 小欧 - fetchRoot() 包在 Promise.resolve().then() 里：同步抛出也能落到 .catch
  //   （否则异常逃出 useEffect → React 提交期报错 → 整块渲染崩） — 小欧-2026-10-22
  cached = Promise.resolve()
    .then(() => fileApi.fetchRoot())
    .then((r) => {
      cachedValue = r.project_root;
      return cachedValue;
    })
    .catch(() => {
      cached = null; // 失败不缓存（下次可重试）
      return '';
    });
  return cached;
};

export const useProjectRoot = (enabled = true): string => {
  const [root, setRoot] = useState(cachedValue);
  useEffect(() => {
    if (!enabled) return;
    let alive = true;
    load().then((r) => {
      if (alive) setRoot(r);
    });
    return () => {
      alive = false;
    };
  }, [enabled]);
  return root;
};
