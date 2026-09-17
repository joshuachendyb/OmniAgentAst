// 编辑历史: 2026-08-28 小欧 - 从NewChatContainer抽离滚动控制逻辑至独立hook(三堂会审: 零逻辑变更,仅复制重组) - 小欧-2026-08-28
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: ①HP-02 scrollToBottomDelayed加timerRef+clearTimeout防堆积②HP-03首帧ref null时用MutationObserver重试防永不监听 — 小欧-2026-09-02
// 编辑历史: 2026-09-03 小欧 BUG-25修复: MutationObserver观察范围由document.body全子树缩至消息容器父级, 降AntD弹窗/打字机逐字触发的无用回调
// 编辑历史: 2026-09-06 小欧 RG-4(北京老陈定案直接改码): scrollIntoView smooth→auto(即时到底), 消流式逐chunk高频下平滑动画反复被打断重启/追赶不及(右栏已弃smooth); 保留100ms防抖 — 小欧-2026-09-06
// 编辑历史: 2026-09-10 小欧 - 阶段二S2收尾(方案A): executionStepsRef 改从 chatStreaming(useSSE 唯一真源)取,
//   ScrollChatState 类型删该字段、ScrollStreaming 类型补该字段(useChatState 已删其定义) — 小欧-2026-09-10
// 编辑历史: 2026-09-13 小欧 - Prettier 格式统一(前端源码格式专项, 纯格式零逻辑): 对齐项目 prettier 排版规范 — 小欧-2026-09-13
import { useCallback, useEffect, useRef } from 'react';
import type { UseChatFacadeReturn } from './useChatFacade';
import type { ExecutionStep } from '../../../types/execution'; // 小欧 2026-09-10 S2收尾: ScrollStreaming 类型引用

const SCROLL_THRESHOLD = 150;

type ScrollChatState = Pick<UseChatFacadeReturn['chatState'], 'isPaused'> &
  Pick<UseChatFacadeReturn['message'], 'messagesEndRef' | 'messages'> &
  Pick<UseChatFacadeReturn['ui'], 'userScrolledUpRef'> &
  Pick<UseChatFacadeReturn['shared'], 'isPausedRef'>;

type ScrollStreaming = Pick<
  UseChatFacadeReturn['streaming'],
  'executionSteps' | 'currentResponse' | 'isReceiving'
> & {
  // 小欧 2026-09-10 S2收尾(方案A): executionStepsRef 改从 streaming(useSSE) 取，供 :61 同步 state→ref
  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
};

/**
 * 滚动控制 hook：同步 isPaused/executionSteps 到 ref、自动滚动到底部、滚动位置监听、可见性变化回滚
 * 逻辑与 NewChatContainer 中原逻辑一致，未做行为改写
 */
export function useChatScroll(
  chatState: ScrollChatState,
  chatStreaming: ScrollStreaming
): void {
  const { messagesEndRef, userScrolledUpRef, isPausedRef, messages, isPaused } =
    chatState;
  const { executionSteps, currentResponse, isReceiving, executionStepsRef } =
    chatStreaming;

  const timerRef = useRef<number | null>(null);
  const scrollToBottomDelayed = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => {
      // RG-4(2026-09-06 小欧): 弃 smooth 改 auto 即时——流式高频下 smooth 动画反复被打断追赶不及 — 小欧-2026-09-06
      messagesEndRef.current?.scrollIntoView({ behavior: 'auto' });
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
      // 2026-09-03 小欧 BUG-25修复: 缩小观察范围至消息容器父级, 非document.body全部子树, 降频繁触发 - 小欧-2026-09-03
      const target =
        messagesEndRef.current?.parentElement?.parentElement ?? document.body;
      mo.observe(target, { childList: true, subtree: true });
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
