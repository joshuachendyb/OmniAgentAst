// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离会话初始化与loading生命周期至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-10 小欧 - thought重复根治(三堂会审定案): 病根=effect依赖searchParams对象引用(每次渲染新引用)反复重跑
//   initializeSession覆盖流式消息; 根治=effect只依赖稳定session_id字符串, 不再传渲染无关的URL参数对象。
//   曾用useMemo稳定searchParams(堵截)与isReceiving守卫(边界退化)两案, 复查后均撤销。 — 小欧-2026-09-10
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.17 恢复优先: 同一 effect 内把 initializeSession 包成
//   chatStreamStore.resume().then 链——非 idle(流活着)且有 URL 会话时只 loadSession 补历史
//   (F7 不重新 POST、不重建任务); idle 走原三场景分支(参数未改) — 小欧-2026-09-29 21:37:55
import { useEffect } from 'react';
import { useLoadingMessage } from '../../../hooks/useLoadingMessage';
import { getMessage } from '../../../lib/antd/bridge';
import { showWarning } from '../../../utils/chatMessages';
import { ERROR_TYPE_LABELS } from '../components/ErrorDetail';
import type { UseChatFacadeReturn } from './useChatFacade';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import type { ResumeResult } from '@/features/chat/streams/backupTypes';

// 编辑历史: 2026-09-30 08:34:56 小欧 - [79] D4 恢复态差异化提示。
//   病根：resume() 返回 12 值 ResumeResult，此前全仓唯一消费点就是下方 `r !== 'idle'` 一个布尔判断
//   （12 值塌缩成 2 分支），导致 S5/S11 里"任务被中断 / 事件不完整 / 持久化降级"原地兜底成
//   "正常历史"——用户只见 DB 里的结果，无从判断该不该重试。
//   落点选在此处：这是 ResumeResult 唯一的 UI 边界，一次分派即拦住"恢复不完整却被静默吞掉"。
//   文案复用 ErrorDetail.ERROR_TYPE_LABELS（4 个 error_type 中文标签已存在，不另写一份以免漂移）；
//   ResumeResult↔error_type 的对应关系见 chatStreamTransport.RECOVERY_ERROR_BRANCH。
const RESUME_NOTICE: Partial<Record<ResumeResult, string>> = {
  task_interrupted: ERROR_TYPE_LABELS.task_interrupted,
  task_state_incomplete: ERROR_TYPE_LABELS.task_state_incomplete,
  gap: ERROR_TYPE_LABELS.persistence_gap,
  degraded: ERROR_TYPE_LABELS.persistence_degraded,
};
// 有意不提示的 8 值及依据：
//   idle / recovering / terminal  正常态，提示即噪声；
//   pending_draft                 草稿本就在客户端（recoverWithoutTaskId 语义），非异常；
//   aborted                       用户主动停，非故障；
//   polling                       轮询观察中，reconnectStatus 已在 UI 呈现；
//   failed                        已走 error 通道 → TaskInfoBar 位4（"error 实时显示唯一位置"定案），再提示即双显示；
//   not_found                     resumeStreamRequest 无终态短路，任务行被归档的**常见良性场景**同样命中，
//                                 发提示会对每次切回旧会话误报。

/**
 * 会话初始化 hook：initializeSession 效果 + loading 挂载/卸载清理
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatInit(opts: {
  chatFacade: UseChatFacadeReturn;
  urlSessionId: string | null;
}): void {
  const { chatState, chatSession, chatPersistence } = opts.chatFacade;
  const { show, hide } = useLoadingMessage({ duration: 0 });

  // 会话状态持久化 - 仅 URL session_id 真正变化重新初始化（依赖稳定字符串, 非渲染无关的对象引用）
  useEffect(() => {
    const onLoadingStart = () => {
      chatState.setSessionJumpLoading(true);
      show('正在加载会话...', 'session-load');
    };
    const onLoadingEnd = () => {
      hide('session-load');
      chatState.setSessionJumpLoading(false);
    };
    const onRenderStart = () => {
      chatState.setIsRenderingMessages(true);
    };
    const onRenderEnd = () => {
      chatState.setIsRenderingMessages(false);
    };
    const onMessageListLoadingStart = () => {
      // No-op: rendered inside initializeSession
    };
    const onMessageListLoadingEnd = () => {
      chatState.setIsMessageListLoading(false);
    };

    // 2026-09-10 小欧: initializeSession内部仅读searchParams.get('session_id')(据useChatSession.ts:227),
    //   故此处只构造session_id一个键的URLSearchParams, 避免渲染无关URL参数引入引用不稳定 — 小欧-2026-09-10
    const searchParams = new URLSearchParams(
      opts.urlSessionId ? { session_id: opts.urlSessionId } : {}
    );

    // [63] 5.17 v1.29 恢复优先：非 idle（流活着/已恢复/轮询/中断/降级等 12 态）→ 只补历史
    //   loadSession（F7：不重新 POST、不重建任务）；idle → 原 initializeSession 三场景原样执行
    void chatStreamStore.resume(opts.urlSessionId ?? undefined).then((r) => {
      if (r !== 'idle' && opts.urlSessionId) {
        // 2026-09-30 08:34:56 小欧 - [79] D4：恢复不完整必须让用户看见（先提示再补历史，不等 loadSession）。
        const notice = RESUME_NOTICE[r];
        if (notice) showWarning(notice);
        void chatSession.loadSession(opts.urlSessionId);
        return;
      }
      chatSession.initializeSession({
        searchParams,
        retryCount: chatState.retryCount,
        setRetryCount: chatState.setRetryCount,
        isLoadingHistoryRef: chatState.isLoadingHistoryRef,
        setIsInitialized: chatState.setIsInitialized,
        restoreState: chatPersistence.restoreState,
        onLoadingStart,
        onLoadingEnd,
        onRenderStart,
        onRenderEnd,
        onMessageListLoadingStart,
        onMessageListLoadingEnd,
      });
    });
    // 仅保留urlSessionId，避免重复执行initializeSession
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.urlSessionId]);

  // 组件卸载时清理 loading + message
  useEffect(() => {
    return () => {
      getMessage().destroy('session-load');
      hide('session-load');
    };
  }, [hide]);
}
