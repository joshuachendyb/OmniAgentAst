// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离滚动控制逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
import {
  useCallback,
  useEffect,
  type MutableRefObject,
  type RefObject,
} from 'react';
import type { Message } from '../../../types/chat';
import type { ExecutionStep } from '../../../types/execution';

interface UseChatScrollOptions {
  messagesEndRef: RefObject<HTMLDivElement | null>;
  userScrolledUpRef: MutableRefObject<boolean>;
  isPausedRef: MutableRefObject<boolean>;
  executionStepsRef: MutableRefObject<ExecutionStep[]>;
  isPaused: boolean;
  executionSteps: ExecutionStep[];
  messages: Message[];
  currentResponse: string;
  isReceiving: boolean;
}

const SCROLL_THRESHOLD = 150;

/**
 * 滚动控制 hook：同步 isPaused/executionSteps 到 ref、自动滚动到底部、滚动位置监听、可见性变化回滚
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatScroll(opts: UseChatScrollOptions): void {
  const {
    messagesEndRef,
    userScrolledUpRef,
    isPaused,
    isPausedRef,
    executionSteps,
    executionStepsRef,
    messages,
    currentResponse,
    isReceiving,
  } = opts;

  // 延迟滚动
  const scrollToBottomDelayed = useCallback(() => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
  }, [messagesEndRef]);

  // 同步 isPaused 状态到 ref
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused, isPausedRef]);

  // 自动滚动到底部 - 修复清理后缺失的自动滚动功能
  useEffect(() => {
    scrollToBottomDelayed();
  }, [messages, currentResponse, executionSteps, scrollToBottomDelayed]);

  // 同步executionSteps到ref - 修复清理后缺失的同步功能
  useEffect(() => {
    executionStepsRef.current = executionSteps;
  }, [executionSteps, executionStepsRef]); // ✅ 加上executionStepsRef依赖

  // 滚动位置监听
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

  // 当页面从隐藏状态变为显示时也自动滚动到底部
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
