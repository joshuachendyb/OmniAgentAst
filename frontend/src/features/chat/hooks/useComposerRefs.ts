// 编辑历史: 2026-10-21 小杨 - 文档[28]§9.5(O5) 新建：refs 独立托管（当轮内存语义） — 小杨-2026-10-21
/**
 * useComposerRefs —— 本轮引用条目的**独立**托管 hook
 *
 * 为什么不用 useInputDraft 托管（O5 定案，修正 4.4.5 的语义错位）：
 * - draft = 落盘持久（切会话要恢复）；refs = 当轮内存（切会话必须清空）
 * - 两者生命周期不同，塞在一起必然出现"每打一个字清一次 refs"这类错位
 *
 * 清理时机（唯一）：**切会话**分支。
 * - 切会话 → 清空（M25：注入后切会话，token 必须清空，否则引用跨会话泄漏）
 * - 发送失败 → **不清**（M4：sessionId 未变 → effect 不触发 → refs 原样保留，重试仍有内容）
 */
import { useEffect, useRef, useState } from 'react';
import type { ComposerRef } from '../streams/composerRefStore';

export function useComposerRefs(sessionId?: string | null) {
  const [refs, setRefs] = useState<ComposerRef[]>([]);
  const sidRef = useRef<string | null | undefined>(sessionId);

  useEffect(() => {
    // 仅"真正切换会话"才清空；发送失败（sessionId 不变）不清（M4）
    // 2026-10-21 小杨 - 审计修复：**不在这里 setRefs([])**（effect 晚一帧 → 会把跨页刚注入的引用误杀）；
    //   旧引用的丢弃由渲染期派生（visibleRefs）承担，真正的 state 清理在下次 setRefs 时自然发生。
    sidRef.current = sessionId;
  }, [sessionId]);

  /**
   * 2026-10-21 小杨 - 文档[28] 审计修复（高危）：
   *   原实现把"清空"放在 effect 里 → **晚一帧**，而引用是**跨页注入**的：
   *   文件页 push → 会话页挂载 → useChatInit 异步建会话 → sessionId 由 '' 变成 'S'
   *   → effect 触发 setRefs([]) → **刚注入的引用被清空**，而正文里的 @token 还在
   *   → 发送时 refs 为空 → 正文里的 @a.md 原样发给模型，**文件正文从未上行**（静默丢数据）。
   *
   *   改为**渲染期派生**（不在 effect 里清 state）：
   *   - 会话未变 → 用 state 里的 refs
   *   - 会话已变 → 视为空（本次渲染不显示旧引用）
   *   - 真正的"丢弃"发生在下一次 setRefs 时（effect 里只更新 sidRef，不再 setRefs([])）
   */
  const visibleRefs = sidRef.current === sessionId ? refs : [];

  /** 是否还有引用正文在途（O3：pending 阻断发送，防发出 content:''） */
  const refsPending = visibleRefs.some((r) => r.pending);

  return { refs: visibleRefs, setRefs, refsPending };
}
