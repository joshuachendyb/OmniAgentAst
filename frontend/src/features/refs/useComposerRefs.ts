// 编辑历史: 2026-10-22 小欧 - 新建：引用（refs）共享 hook —— 订阅投递通道 + 托管待发引用 — 小欧-2026-10-22
/**
 * useComposerRefs —— 引用（refs）的唯一状态托管点
 *
 * 存在理由：
 * - ChatInput 常驻不卸载，同路由仅 query 变化时 React 不重挂载 → "挂载时取一次"
 *   的写法会静默丢引用（M21）。故必须订阅外部 store。
 * - 本 hook 是唯一消费端（takeAll + merge 的实现只此一处），
 *   任何第二个消费方（引用历史面板、待发引用预览）都应复用本 hook，不再自写订阅。
 *
 * 语义：
 * - store 是投递通道（一次性消费，takeAll 后即清空）；
 * - 本 hook 把投递来的条目并入待发引用状态（会话内持续存在，用户可删可改）；
 * - 发送成功由调用方清（refs 保留在 store 台账里是另一件事，见 chatStreamStore.pushSentRefs）。
 */
import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';
import { composerRefStore, mergeRefs, type ComposerRef } from './store';

export interface UseComposerRefsResult {
  /** 当前待发引用 */
  refs: ComposerRef[];
  /** 有条目正在载入（发送闸门据此阻断） */
  pending: boolean;
  /** 有条目已失效（文件被删/不可读） */
  invalid: boolean;
  /** 移除一条（token 上的 ×，按 id） */
  remove: (id: string) => void;
  /** 按谓词移除（@ 补全失败时按 path 删占位，无 id 可用） */
  removeWhere: (pred: (r: ComposerRef) => boolean) => void;
  /** 全部清空（发送成功后） */
  clear: () => void;
  /** 直接并入一条（@ 补全插 pending 占位，不经 store） */
  add: (ref: ComposerRef) => void;
  /** 整体替换（refreshRefs 回写校验结果） */
  setAll: (refs: ComposerRef[]) => void;
}

export const useComposerRefs = (): UseComposerRefsResult => {
  const [refs, setRefs] = useState<ComposerRef[]>([]);
  const count = useSyncExternalStore(
    composerRefStore.subscribe,
    composerRefStore.getSnapshot,
    composerRefStore.getSnapshot
  );

  useEffect(() => {
    if (count === 0) return;
    const incoming = composerRefStore.takeAll();
    if (incoming.length === 0) return;
    setRefs((prev) => mergeRefs(prev, incoming));
  }, [count]);

  const remove = useCallback((id: string) => {
    setRefs((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const removeWhere = useCallback((pred: (r: ComposerRef) => boolean) => {
    setRefs((prev) => prev.filter((r) => !pred(r)));
  }, []);

  const clear = useCallback(() => setRefs([]), []);

  const add = useCallback((ref: ComposerRef) => {
    setRefs((prev) => mergeRefs(prev, [ref]));
  }, []);

  const setAll = useCallback((next: ComposerRef[]) => setRefs(next), []);

  return {
    refs,
    pending: refs.some((r) => r.pending),
    invalid: refs.some((r) => r.invalid),
    remove,
    removeWhere,
    clear,
    add,
    setAll,
  };
};
