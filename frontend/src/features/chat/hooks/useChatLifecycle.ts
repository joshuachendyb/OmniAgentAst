// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离保存/离开拦截/快捷键生命周期至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useCallback, useEffect } from 'react';
import { useBeforeUnload } from '../../../hooks/useBeforeUnload';
import { saveChatState } from '../../../utils/sessionStorage';
import type { UseChatFacadeReturn } from './useChatFacade';

/**
 * 会话生命周期 hook：新建会话、离开前保存、Ctrl/Cmd+N 快捷键
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatLifecycle(opts: { chatFacade: UseChatFacadeReturn }): {
  handleNewSession: () => void;
} {
  const { chatState, chatStreaming, chatSession } = opts.chatFacade;

  const handleNewSession = useCallback(() => {
    chatSession.handleNewSession(0);
  }, [chatSession]);

  // 保存状态（用于beforeunload）
  const handleSaveBeforeUnload = useCallback(() => {
    if (!chatStreaming.isReceiving || !chatState.sessionId) return;

    let messagesToSave = chatState.messagesRef.current;
    if (chatState.executionStepsRef.current.length > 0) {
      messagesToSave = chatState.messagesRef.current.map((msg, idx) => {
        if (
          msg.role === 'assistant' &&
          msg.isStreaming &&
          idx === chatState.messagesRef.current.length - 1
        ) {
          return {
            ...msg,
            executionSteps: chatState.executionStepsRef.current,
          };
        }
        return msg;
      });
    }

    const state = {
      messages: messagesToSave,
      sessionId: chatState.sessionId,
      sessionTitle: chatState.sessionTitle,
      timestamp: Date.now(),
      scrollPosition: 0,
      isPaused: chatState.isPaused,
      isReceiving: chatStreaming.isReceiving,
    };

    // 2026-08-27 小欧 三堂会审: 会话状态保存下沉至 saveChatState
    saveChatState(state);
  }, [
    chatStreaming.isReceiving,
    chatState.sessionId,
    chatState.sessionTitle,
    chatState.isPaused,
    chatState.executionStepsRef,
    chatState.messagesRef,
  ]);

  // 使用useBeforeUnload Hook统一管理
  useBeforeUnload({
    shouldSave: !!chatStreaming.isReceiving && !!chatState.sessionId,
    saveData: handleSaveBeforeUnload,
    showDialog: true,
    dialogMessage: '正在接收消息，确定要离开吗？',
  });

  // 全局快捷键 Ctrl/Cmd + N 新建会话
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault();
        handleNewSession();
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleNewSession]);

  return { handleNewSession };
}
