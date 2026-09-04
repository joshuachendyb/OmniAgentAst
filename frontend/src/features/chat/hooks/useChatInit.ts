// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离会话初始化与loading生命周期至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useEffect } from 'react';
import { useLoadingMessage } from '../../../hooks/useLoadingMessage';
import { getMessage } from '../../../lib/antd/bridge';
import type { UseChatFacadeReturn } from './useChatFacade';

/**
 * 会话初始化 hook：initializeSession 效果 + loading 挂载/卸载清理
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatInit(opts: {
  chatFacade: UseChatFacadeReturn;
  searchParams: URLSearchParams;
}): void {
  const { chatState, chatSession, chatPersistence } = opts.chatFacade;
  const { show, hide } = useLoadingMessage({ duration: 0 });

  // 会话状态持久化 - 使用chatSession.initializeSession（仅 searchParams 变化重新初始化）
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

    chatSession.initializeSession({
      searchParams: opts.searchParams,
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
    // 仅保留searchParams，避免重复执行initializeSession
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opts.searchParams]);

  // 组件卸载时清理 loading + message
  useEffect(() => {
    return () => {
      getMessage().destroy('session-load');
      hide('session-load');
    };
  }, [hide]);
}
