// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离滚动控制逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import { useCallback, useEffect } from 'react';
import type { UseChatFacadeReturn } from './useChatFacade';

const SCROLL_THRESHOLD = 150;

type ScrollChatState = Pick<UseChatFacadeReturn['chatState'], 'isPaused'> &
  Pick<UseChatFacadeReturn['message'], 'messagesEndRef' | 'messages'> &
  Pick<UseChatFacadeReturn['ui'], 'userScrolledUpRef'> &
  Pick<UseChatFacadeReturn['shared'], 'isPausedRef' | 'executionStepsRef'>;

type ScrollStreaming = Pick<
  UseChatFacadeReturn['streaming'],
  'executionSteps' | 'currentResponse' | 'isReceiving'
>;

/**
 * 滚动控制 hook：同步 isPaused/executionSteps 到 ref、自动滚动到底部、滚动位置监听、可见性变化回滚
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatScroll(
  chatState: ScrollChatState,
  chatStreaming: ScrollStreaming
): void {
  const {
    messagesEndRef,
    userScrolledUpRef,
    isPausedRef,
    executionStepsRef,
    messages,
    isPaused,
  } = chatState;
  const { executionSteps, currentResponse, isReceiving } = chatStreaming;

  const scrollToBottomDelayed = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }, [messagesEndRef]);

  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused, isPausedRef]);

  useEffect(() => {
    scrollToBottomDelayed();
  }, [messages, currentResponse, executionSteps, scrollToBottomDelayed]);

  useEffect(() => {
    executionStepsRef.current = executionSteps;
  }, [executionSteps, executionStepsRef]);

  useEffect(() => {
    const container = messagesEndRef.current?.parentElement;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
      userScrolledUpRef.current = distanceFromBottom > SCROLL_THRESHOLD;
    };

    container.addEventListener('scroll', handleScroll, { passive: true });
    return () => container.removeEventListener('scroll', handleScroll);
  }, [messagesEndRef, userScrolledUpRef]);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        scrollToBottomDelayed();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [currentResponse, executionSteps, isReceiving, scrollToBottomDelayed]);
}
