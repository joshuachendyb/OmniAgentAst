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
import type { UseChatFacadeReturn } from './useChatFacade';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';

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
