// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.12/10.2(S1-9) 新建：项目根一次性取数（模块级缓存，多处共用） — 小杨-2026-10-21
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
  cached = fileApi
    .fetchRoot()
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

export const useProjectRoot = (): string => {
  const [root, setRoot] = useState(cachedValue);
  useEffect(() => {
    let alive = true;
    load().then((r) => {
      if (alive) setRoot(r);
    });
    return () => {
      alive = false;
    };
  }, []);
  return root;
};
