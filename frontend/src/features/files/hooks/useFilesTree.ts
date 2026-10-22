// 编辑历史: 2026-10-22 小欧 - 新建：文件树状态机（纯树域）— 小欧-2026-10-22
//   文档[43] R7：从 pages/Files 抽出树的全部状态与操作，页面退化为布局壳。
//   收编：tree / treeStatus / loadedKeys / expandedKeys / scanNotices +
//         beginTreeReq / claimDir / loadTree / loadDir / patchNodes + expandToPath。
//   不放：openPath（跨 tree+selection 编排，留页面层）；loadRoot / setWorkspace（会话域）。
//   2026-10-22 小欧 - 文档[43] G-4：claimDir 的「登记序号→取子树→过期判定」抽为纯函数
//     withSeqGate（loadDir / expandToPath 各抄一遍判据，改口径会「改 A 漏 B」；原 claimDir
//     把纯计算与写 ref 混一个函数，违 SLAP）。claimDir 失去全部消费者被删；
//     beginTreeReq 不抽（AbortController 是浏览器生命周期 API，抽了即为抽象而抽象）— 小欧-2026-10-22
import { useCallback, useEffect, useRef, useState } from 'react';
import { fileApi, type FileNode } from '@/services/api/file.api';
import { findNode } from '@/features/files/components/FilesTree';
import { buildScanNotices, mergeKids } from '@/utils/fileTree';
import { isSilentError } from '@/services/error/handler';

export type TreeStatus =
  | { phase: 'loading' }
  | { phase: 'ready' }
  | { phase: 'error'; message: string };

/**
 * 合并型补拉的序号闸门（纯函数，唯一实现）。
 * 同键后发者作废先发者：登记序号 → 执行 → 响应到达时比对序号，过期返回 null。
 * 2026-10-22 小欧 - 文档[43] G-4：原实现把「算序号」（纯逻辑）与「写 ref」（状态存储）
 *   混在一个回调里（违 SLAP），且 loadDir / expandToPath 各抄一遍（DRY 硬伤，
 *   改判定口径会「改 A 漏 B」）。抽成纯函数后不变量可单测。— 小欧-2026-10-22
 */
export const withSeqGate = async <T,>(
  seqs: Map<string, number>,
  key: string,
  run: () => Promise<T>
): Promise<T | null> => {
  const seq = (seqs.get(key) ?? 0) + 1;
  seqs.set(key, seq);
  const result = await run();
  return seqs.get(key) !== seq ? null : result;
};

export function useFilesTree() {
  const [scanNotices, setScanNotices] = useState<string[]>([]);
  const [tree, setTree] = useState<FileNode[]>([]);
  const [treeStatus, setTreeStatus] = useState<TreeStatus>({
    phase: 'loading',
  });
  const [loadedKeys, setLoadedKeys] = useState<string[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);

  const treeReady = treeStatus.phase === 'ready';
  const treeLoading = treeStatus.phase === 'loading';
  const treeErr =
    treeStatus.phase === 'error' ? treeStatus.message : null;

  const treeRef = useRef<FileNode[]>([]);
  const treeAbortRef = useRef<AbortController | null>(null);
  const dirSeqRef = useRef<Map<string, number>>(new Map());

  const beginTreeReq = useCallback((): AbortSignal => {
    treeAbortRef.current?.abort();
    const ctl = new AbortController();
    treeAbortRef.current = ctl;
    return ctl.signal;
  }, []);

  /** 合并型补拉（登记序号 → 取子树 → 过期响应丢弃），唯一实现 */
  const fetchGated = useCallback(
    async (key: string): Promise<FileNode[] | null> =>
      withSeqGate(dirSeqRef.current, key, async () => {
        const r = await fileApi.fetchTree(key, { maxDepth: 3 });
        return r.nodes;
      }),
    []
  );

  const loadTree = useCallback(async () => {
    const signal = beginTreeReq();
    setTreeStatus({ phase: 'loading' });
    try {
      const r = await fileApi.fetchTree('', { maxDepth: 3, signal });
      treeRef.current = r.nodes;
      setTree(r.nodes);
      setLoadedKeys([]);
      setScanNotices(buildScanNotices(r));
      setTreeStatus({ phase: 'ready' });
    } catch (e) {
      if (isSilentError(e)) return;
      setTreeStatus({ phase: 'error', message: '目录加载失败，请重试' });
    }
  }, [beginTreeReq]);

  useEffect(() => {
    void loadTree();
  }, [loadTree]);

  useEffect(() => () => treeAbortRef.current?.abort(), []);

  const expandToPath = useCallback(
    async (rel: string): Promise<FileNode | null> => {
      const targetKey = rel
        .replace(/\\/g, '/')
        .replace(/^\.\/+/, '')
        .replace(/\/+/g, '/');
      const segs = targetKey.split('/').filter(Boolean);
      const dirKeys: string[] = [];
      let cur = '';
      for (const s of segs) {
        cur = cur ? `${cur}/${s}` : s;
        let hit = findNode(treeRef.current, cur);
        if (!hit) return null;
        if (hit.type === 'dir' && !hit.children) {
          const kids = await fetchGated(cur);
          if (!kids) return null; // 过期响应：同键后发者已作废本轮
          const merged = mergeKids(treeRef.current, cur, kids);
          treeRef.current = merged;
          setTree(merged);
          setLoadedKeys((prev) =>
            prev.includes(cur) ? prev : [...prev, cur]
          );
          hit = findNode(treeRef.current, cur);
          if (!hit) return null;
        }
        if (hit.type === 'dir') dirKeys.push(cur);
      }
      const target = findNode(treeRef.current, targetKey);
      if (!target) return null;
      setExpandedKeys((prev) => {
        const add = dirKeys.filter((k) => !prev.includes(k));
        return add.length > 0 ? [...prev, ...add] : prev;
      });
      return target;
    },
    [fetchGated]
  );

  /** 补拉一个目录（降级）：失败静默返回 null，由树侧按需重试 */
  const loadDir = useCallback(
    async (key: string): Promise<FileNode[] | null> => {
      try {
        return await fetchGated(key);
      } catch {
        return null;
      }
    },
    [fetchGated]
  );

  const patchNodes = useCallback((parentKey: string, kids: FileNode[]) => {
    const merged = mergeKids(treeRef.current, parentKey, kids);
    treeRef.current = merged;
    setTree(merged);
  }, []);

  return {
    tree,
    status: treeStatus,
    loadedKeys,
    setLoadedKeys,
    expandedKeys,
    setExpandedKeys,
    scanNotices,
    treeReady,
    treeLoading,
    treeErr,
    loadTree,
    loadDir,
    patchNodes,
    expandToPath,
  };
}
