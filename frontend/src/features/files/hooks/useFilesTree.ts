// 编辑历史: 2026-10-22 小欧 - 新建：文件树状态机（纯树域）— 小欧-2026-10-22
//   文档[43] R7：从 pages/Files 抽出树的全部状态与操作，页面退化为布局壳。
//   收编：tree / treeStatus / loadedKeys / expandedKeys / scanNotices +
//         beginTreeReq / claimDir / loadTree / loadDir / patchNodes + expandToPath。
//   不放：openPath（跨 tree+selection 编排，留页面层）；loadRoot / setWorkspace（会话域）。
import { useCallback, useEffect, useRef, useState } from 'react';
import { fileApi } from '@/services/api/file.api';
import type { FileNode } from '@/services/api/file.api';
import { findNode } from '@/features/files/components/FilesTree';
import { buildScanNotices, mergeKids } from '@/utils/fileTree';
import { isSilentError } from '@/services/error/handler';

export type TreeStatus =
  | { phase: 'loading' }
  | { phase: 'ready' }
  | { phase: 'error'; message: string };

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

  const claimDir = useCallback((key: string): number => {
    const seq = (dirSeqRef.current.get(key) ?? 0) + 1;
    dirSeqRef.current.set(key, seq);
    return seq;
  }, []);

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
          const seq = claimDir(cur);
          const r = await fileApi.fetchTree(cur, { maxDepth: 3 });
          if (dirSeqRef.current.get(cur) !== seq) return null;
          const merged = mergeKids(treeRef.current, cur, r.nodes);
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
    [claimDir]
  );

  const loadDir = useCallback(
    async (key: string): Promise<FileNode[] | null> => {
      const seq = claimDir(key);
      try {
        const r = await fileApi.fetchTree(key, { maxDepth: 3 });
        if (dirSeqRef.current.get(key) !== seq) return null;
        return r.nodes;
      } catch {
        return null;
      }
    },
    [claimDir]
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
