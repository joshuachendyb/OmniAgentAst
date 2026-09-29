// [63] 5.5：组件↔Store 订阅桥接（useSyncExternalStore）。页面只订阅：卸载仅 unsubscribe，
//   不会 abort、不会清 Store、不会删 sessionStorage（停止任务必须走显式 stop()）。
import { useEffect, useMemo, useSyncExternalStore } from 'react';
import type { ExecutionStep } from '@/types/execution';
import type { StreamEvent } from './backupTypes';
import { chatStreamStore } from './chatStreamStore';

/** 2026-09-29 小欧：空 sessionId 时的只读空 ref 视图（render 期不得 ensureSession 造 '' 假会话） */
const EMPTY_STEPS_REF: { current: ExecutionStep[] } = { current: [] };

/**
 * 订阅某会话的流快照与事件。
 * @param sessionId 会话 id（null 时只读冻结空快照，不订阅不创建）
 * @param onEvent 真实帧事件回调（须由调用方 useCallback 保持稳定引用）
 * @returns 快照字段 + 动作（sendMessage/resume/stop/clearSteps/waitClock/executionStepsRef）
 */
export function useChatStreamSession(
  sessionId: string | null,
  onEvent?: (event: StreamEvent) => void
) {
  const id = sessionId ?? '';
  // 2026-09-29 22:47:10 小欧（[63] 5.5 防退化修复）：render 期显式确保会话存在。
  //   原先会话只由下方 executionStepsRef 的 ensureSession 副作用创建，而它在返回对象里
  //   排在 waitClock 的 useMemo **之后**——首渲染时 waitClock 先算，此时 session 尚未创建，
  //   getClockSignals 只能返回 ZERO_CLOCK（三个字段恒 0）；空流/无心跳场景 heartbeatTs 恒 0，
  //   memo 依赖永不变化 → 组件永久持有零钟面，lastBizTs 恒 0，等待动画与静默升档全失效。
  //   ensureSession 幂等（Map 命中即返回），render 期调用安全；空 id 不建（防造 '' 假会话）。
  if (id) chatStreamStore.ensureSession(id);
  const snapshot = useSyncExternalStore(
    (callback) => (sessionId ? chatStreamStore.subscribe(sessionId, callback) : () => undefined),
    () => chatStreamStore.getSnapshot(id),
    () => chatStreamStore.getSnapshot(id)
  );
  useEffect(() => {
    if (!sessionId) return undefined; // 空 id 不订阅（只有真实 id 才有会话）
    return onEvent ? chatStreamStore.subscribeEvents(sessionId, onEvent) : undefined;
  }, [sessionId, onEvent]);
  return {
    ...snapshot,
    // 3 参形态对齐 useChatStreaming 消费：customSessionId 优先于默认 id
    sendMessage: (content: string, customSessionId?: string, mode?: 'linked' | 'independent') =>
      chatStreamStore.sendMessage(customSessionId ?? id, content, mode),
    resume: () => chatStreamStore.resume(id),
    stop: () => chatStreamStore.stop(id),
    clearSteps: () => chatStreamStore.clearSteps(id),
    waitClock: useMemo(
      () => chatStreamStore.getClockSignals(id),
      // 2026-09-29 22:47:10 小欧（[63] 5.5 防退化修复）：原稿每次 render 现调 getClockSignals
      //   必得新对象，而 useChatPanels.tsx:159 的 useMemo 把 waitClock 列入依赖（心跳微闪驱动
      //   RightViewer 重渲）——引用每次都变会让该 useMemo 永久失效、面板逐帧重算。
      //   口径与被删的 useSSE 一致：waitClock 仅依赖 heartbeatTs 变化才换引用。
      [id, snapshot.heartbeatTs]
    ),
    // 推导 ref 视图——5.3 parser 与组件层同一对象（非第二真源）；空 id 走只读空视图
    executionStepsRef: sessionId ? chatStreamStore.getExecutionStepsRef(id) : EMPTY_STEPS_REF,
  };
}

// 编辑历史: 2026-09-29 21:37:55 小欧 - 新建: [63] 5.5 Store 订阅桥接(useSyncExternalStore 快照 +
//   事件双通道；组件卸载只 unsubscribe，流不销毁) — 小欧-2026-09-29 21:37:55
//   相对 [63] 5.5 原稿的 1 处修正 — 小欧-2026-09-29 21:37:55：
//   executionStepsRef 原稿无条件 chatStreamStore.getExecutionStepsRef(id)，id 为 ''（sessionId=null）时
//   会在 render 期 ensureSession('') 造出假会话条目并泄漏（与 5.4「getSnapshot 路径绝不创建」相悖）；
//   改为空 id 返回模块级只读空视图。
//
// 编辑历史: 2026-09-29 22:47:10 小欧 - [63] 5.5 防退化修复 2 处 — 小欧-2026-09-29 22:47:10：
//   ① waitClock 原每次 render 新建对象 → useChatPanels useMemo 永久失效，改 useMemo([id, heartbeatTs])；
//   ② heartbeatTs 未列入 5.4 快照 → 心跳不触发 bump 通知、等待期 ClockStopwatch 冻结，
//      已在 backupTypes.SessionSnapshot + chatStreamStore.SNAPSHOT_KEYS/bump 补齐。
//
// 编辑历史: 2026-09-29 23:22:19 小欧 - [63] 5.5 防退化修复：零钟面锁死 — 小欧-2026-09-29 23:22:19：
//   症状：首帧迟到/空流的会话，waitClock.lastBizTsRef 恒 0，等待动画与静默升档全失效
//   （A5 单测"新任务 send 重置业务基线"红：expected 0 to be greater than 0）。
//   成因：会话原先只由返回对象里 executionStepsRef 的 ensureSession 副作用创建，而它排在
//   waitClock 的 useMemo **之后**——首渲染 waitClock 先算，session 尚未创建，
//   getClockSignals 只能返回 ZERO_CLOCK（恒 0）；空流场景 heartbeatTs 恒 0，memo 依赖永不
//   变化 → 组件永久持有零钟面。
//   修复：render 期显式 if (id) ensureSession(id)（幂等 Map 命中即返回；空 id 不建，防造
//   '' 假会话），effect 退化为纯订阅。heartbeatTs 仍留在 memo 依赖里——心跳微闪要靠它触发
//   useChatPanels 的 useMemo 重渲。
