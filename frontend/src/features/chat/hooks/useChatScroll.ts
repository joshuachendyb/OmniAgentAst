// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离滚动控制逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①HP-02 scrollToBottomDelayed加timerRef+clearTimeout防堆积②HP-03首帧ref null时用MutationObserver重试防永不监听 — 小欧-2026-09-02
import { useCallback, useEffect, useRef } from 'react';
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

  const timerRef = useRef<number | null>(null);
  const scrollToBottomDelayed = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }, [messagesEndRef]);
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

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
    let container = messagesEndRef.current?.parentElement;
    let cleanup: (() => void) | undefined;
    const attach = (c: HTMLElement) => {
      const handleScroll = () => {
        const { scrollTop, scrollHeight, clientHeight } = c;
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
        userScrolledUpRef.current = distanceFromBottom > SCROLL_THRESHOLD;
      };
      c.addEventListener('scroll', handleScroll, { passive: true });
      cleanup = () => c.removeEventListener('scroll', handleScroll);
    };
    if (container) {
      attach(container);
    } else {
      const mo = new MutationObserver(() => {
        const c = messagesEndRef.current?.parentElement;
        if (c) {
          container = c;
          mo.disconnect();
          attach(c);
        }
      });
      mo.observe(document.body, { childList: true, subtree: true });
      cleanup = () => mo.disconnect();
    }
    return () => cleanup?.();
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
