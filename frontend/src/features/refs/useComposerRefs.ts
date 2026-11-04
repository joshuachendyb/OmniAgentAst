// 编辑历史: 2026-10-22 小欧 - 新建：引用（refs）共享 hook —— 订阅投递通道 + 托管待发引用 — 小欧-2026-10-22
// 编辑历史: 2026-10-30 小欧 - 批2序12(F13): 订阅 refNoticeStore 透传 notices, 供 chip 5 态消费;
//   身份函数改从 identity.ts 导入(批3序14) — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 批3: 入队/并入时按 path 清掉上一轮回执(mergeIncoming 单点,
//   store 投递与 @ 补全共用); 删 clear()(唯一调用方改为按 id 精确移除本轮条目, 整表清空会
//   抹掉 refs_blocked 回执重建的 chips) — 小欧-2026-10-30
// 编辑历史: 2026-10-30 小欧 R5-1/S4-1/R1-2/R2-1: ①发布 chips 快照给 composerRefStore.setLive
//   (上限判定真源); ②回声动作从 mergeIncoming 迁出(store 投递不再回声, 否则 refs_blocked 重建
//   会抹掉刚下发的回执), 改由 push 与 add 各自承担; ③新增 getRefs() 读最新 chips —— 预检返回后
//   按 id 合并、@ 补全写回前复核占位是否还在, 都要读"异步窗口后的真值" — 小欧-2026-10-30
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
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from 'react';
import { composerRefStore, refNoticeStore, type ComposerRef } from './store';
import { mergeRefs } from './identity';
import type { NoticeMap } from './notice';

export interface UseComposerRefsResult {
  /** 当前待发引用 */
  refs: ComposerRef[];
  /** 当前回执表(按 path 键控, chip 5 态的外部输入) — 小欧-2026-10-30 */
  notices: NoticeMap;
  /** 有条目正在载入（发送闸门据此阻断） */
  pending: boolean;
  /** 有条目已失效（文件被删/不可读） */
  invalid: boolean;
  /** 读**最新** chips(异步窗口后用: 预检返回合并、@ 补全写回前复核) — 小欧-2026-10-30 */
  getRefs: () => ComposerRef[];
  /** 移除一条（token 上的 ×，按 id） */
  remove: (id: string) => void;
  /** 按谓词移除（@ 补全失败时按 path 删占位；发送成功后按 id 精确移除本轮条目） */
  removeWhere: (pred: (r: ComposerRef) => boolean) => void;
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
  // chip 回执态: 唯一写入口是 SSE refs_notice(见 chatStreamTransport), 本 hook 只读
  const notices = useSyncExternalStore(
    refNoticeStore.subscribe,
    refNoticeStore.getSnapshot,
    refNoticeStore.getSnapshot
  );

  /** 最新 chips 镜像(异步窗口读真值) — 2026-10-30 小欧 */
  const refsRef = useRef<ComposerRef[]>([]);
  useEffect(() => {
    refsRef.current = refs;
    // 上限判定真源: store 需要知道"已入队多少条"(队列只是一次性投递通道)
    composerRefStore.setLive(refs);
  }, [refs]);
  useEffect(() => () => composerRefStore.setLive([]), []);

  const getRefs = useCallback(() => refsRef.current, []);

  /**
   * 并入引用 — 2026-10-30 小欧
   *   只并入, **不**碰回执: store 投递来源含 refs_blocked 台账重建(store.restore),
   *   那一路必须保留刚下发的 refs_notice; "重新引用同一文件是新的意图, 清上一轮黄/红标"
   *   的动作已下沉到 composerRefStore.push 与本 hook 的 add(两个真入口)。
   */
  const mergeIncoming = useCallback((incoming: ComposerRef[]) => {
    setRefs((prev) => mergeRefs(prev, incoming));
  }, []);

  useEffect(() => {
    if (count === 0) return;
    const incoming = composerRefStore.takeAll();
    if (incoming.length === 0) return;
    mergeIncoming(incoming);
  }, [count, mergeIncoming]);

  const remove = useCallback((id: string) => {
    setRefs((prev) => prev.filter((x) => x.id !== id));
  }, []);

  const removeWhere = useCallback((pred: (r: ComposerRef) => boolean) => {
    setRefs((prev) => prev.filter((r) => !pred(r)));
  }, []);

  const add = useCallback((ref: ComposerRef) => {
    if (ref.path) refNoticeStore.clearPath(ref.path); // 新意图: 清上一轮黄/红标
    setRefs((prev) => mergeRefs(prev, [ref]));
  }, []);

  const setAll = useCallback((next: ComposerRef[]) => setRefs(next), []);

  return {
    refs,
    notices,
    pending: refs.some((r) => r.pending),
    invalid: refs.some((r) => r.invalid),
    getRefs,
    remove,
    removeWhere,
    add,
    setAll,
  };
};
