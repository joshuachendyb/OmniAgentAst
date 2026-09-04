// 编辑历史: 2026-08-26 小欧 - 参与P1-P7: 任务取消/暂停控制对齐final_cancel事件(7.7)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.5-19删内层finally/20 抽callCancelApi/waitForCancelOrTimeout/resetUiFlags编排
// 编辑历史: 2026-08-28 小强 - hooks修复#15: waitForCancelOrTimeout加5s超时兜底Promise.race, 防永久挂起
/**
 * useChatTaskControl Hook - 任务取消与暂停控制
 *
 * 功能：
 * - handleCancel: 取消正在执行的任务
 * - handleTogglePause: 暂停/继续任务执行
 * - waitForCancelEvent: 等待取消事件的内部辅助函数
 *
 * 设计说明：
 * - 专门处理任务控制逻辑
 * - 依赖 chatStreaming 提供的 serverTaskId 和 disconnect
 * - 依赖 chatState 提供的状态 setters 和 refs
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-22
 */

import { useCallback } from 'react';
import { taskControlApi } from '../../../services/api/task.api';
import {
  showTaskControlInfo,
  showTaskResultMessage,
  showTaskControlMessage,
  showNoActiveTaskWarning,
} from '../../../utils/chatMessages';
import { handleError } from '@/services/error/handler';

// ============================================================================
// 类型定义
// ============================================================================

/**
 * useChatTaskControl 配置参数
 *
 * 【P3优化】方案1：参数分组
 * - 将10个扁平参数改为4个分组参数
 * - setters: 状态设置函数
 * - states: 状态值
 * - refs: Ref引用
 * - functions: 函数
 */
export interface UseChatTaskControlOptions {
  // 状态设置函数
  setters: {
    setLoading: (v: boolean) => void;
    setIsPaused: (v: boolean) => void;
    setIsReceiving: (v: boolean) => void;
  };

  // 状态值
  states: {
    isPaused: boolean;
    sessionId: string | null;
    serverTaskId: string | null;
  };

  // Refs
  refs: {
    cancelInProgressRef: React.MutableRefObject<boolean>;
    hasReceivedCancelEventRef: React.MutableRefObject<boolean>;
    waitTimerRef: React.MutableRefObject<number | null>;
    isPausedRef: React.MutableRefObject<boolean>;
  };

  // 函数
  functions: {
    disconnect: (
      stopServer?: boolean,
      force?: boolean,
      callback?: () => void
    ) => void;
  };
}

/**
 * useChatTaskControl Hook返回值
 */
export interface UseChatTaskControlReturn {
  handleCancel: () => Promise<void>;
  handleTogglePause: () => Promise<void>;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatTaskControl - 任务取消与暂停控制
 *
 * 迁移自：NewChatContainer.tsx 中的 handleCancel 和 handleTogglePause 函数
 * - waitForCancelEvent: 等待取消事件的内部辅助函数
 * - handleCancel: 取消正在执行的任务
 * - handleTogglePause: 暂停/继续任务执行
 *
 * @param options - 配置参数
 * @returns 任务控制函数
 */
export const useChatTaskControl = (
  options: UseChatTaskControlOptions
): UseChatTaskControlReturn => {
  // 【P3优化】方案1参数分组解构
  const { setters, states, refs, functions } = options;
  const { setLoading, setIsPaused, setIsReceiving } = setters;
  const { isPaused, sessionId, serverTaskId } = states;
  const {
    cancelInProgressRef,
    hasReceivedCancelEventRef,
    waitTimerRef,
    isPausedRef,
  } = refs;
  const { disconnect } = functions;

  // =========================================================================
  // 内部辅助函数
  // =========================================================================

  /**
   * 智能等待取消事件函数
   * 等待后端发送 cancelled 事件，最多等待 maxWaitTime
   */
  const waitForCancelEvent = useCallback(
    async (maxWaitTime = 3000, checkInterval = 200): Promise<boolean> => {
      const startTime = Date.now();
      let hasReceivedEvent = false;

      while (Date.now() - startTime < maxWaitTime) {
        if (hasReceivedCancelEventRef.current) {
          console.log('[waitForCancelEvent] 已收到 cancelled 事件');
          hasReceivedEvent = true;
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, checkInterval));
      }

      if (!hasReceivedEvent) {
        console.warn(
          `[waitForCancelEvent] 在 ${maxWaitTime}ms 内未收到 cancelled 事件，继续执行`
        );
      }

      return hasReceivedEvent;
    },
    [hasReceivedCancelEventRef]
  );

  // =========================================================================
  // 任务控制函数
  // =========================================================================

  // 2026-08-27 小欧 三堂会审: 抽出小函数, 主函数仅编排(行为等价)
  const resetUiFlags = useCallback((): void => {
    setLoading(false);
    setIsPaused(false);
    if (setIsReceiving) setIsReceiving(false);
  }, [setLoading, setIsPaused, setIsReceiving]);

  const callCancelApi = useCallback(
    async (
      taskId: string,
      sid: string | null
    ): Promise<{ success: boolean; message: string }> => {
      const timeoutPromise = new Promise<unknown>((_, reject) => {
        setTimeout(() => reject(new Error('取消请求超时')), 5000);
      });
      return (await Promise.race([
        taskControlApi.cancel(taskId, sid ?? undefined),
        timeoutPromise,
      ])) as { success: boolean; message: string };
    },
    []
  );

  // 2026-08-28 小强 修复#15: Promise.race加5s硬超时兜底, 防waitForCancelEvent内部轮询永久挂起
  const waitForCancelOrTimeout = useCallback(async (): Promise<void> => {
    const cancelPromise = waitForCancelEvent(3000, 200);
    const timeoutPromise = new Promise<boolean>((resolve) => {
      setTimeout(() => resolve(false), 5000);
    });
    await Promise.race([cancelPromise, timeoutPromise]);
  }, [waitForCancelEvent]);

  /**
   * handleCancel - 取消正在执行的任务
   *
   * 功能：
   * 1. 防重复点击检查
   * 2. 调用 taskControlApi.cancel 取消任务
   * 3. 智能等待 cancelled 事件
   * 4. 断开SSE连接
   * 5. 更新UI状态
   */
  const handleCancel = useCallback(async () => {
    // 【防重复点击】如果正在取消中，忽略后续点击
    if (cancelInProgressRef.current) {
      console.log('[handleCancel] 正在取消中，忽略重复点击');
      return;
    }
    cancelInProgressRef.current = true;

    const taskIdToCancel = serverTaskId;
    console.log(
      `[handleCancel] serverTaskId=${serverTaskId}, taskIdToCancel=${taskIdToCancel}`
    );

    try {
      if (taskIdToCancel) {
        try {
          showTaskControlInfo('正在取消任务...');
          console.log("[handleCancel] 已显示 '正在取消任务...' 提示");

          // ✅【方案1】立即更新UI状态，给用户即时反馈
          resetUiFlags();

          // ✅【关键修复】不立即断开连接！等待后端发送cancelled/final事件
          const result = await callCancelApi(taskIdToCancel, sessionId);
          console.log('[handleCancel] cancel API 返回:', result);

          // ✅ 使用智能等待策略等待后端发送cancelled事件
          await waitForCancelOrTimeout();

          // ✅ 停止所有进行中的倒计时
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
            console.log('[handleCancel] 已清除waitTimerRef倒计时');
          }

          disconnect(true, true, () => {
            console.log('[handleCancel] SSE已断开，状态已同步');
            // 在断开连接完成后重置标记
            hasReceivedCancelEventRef.current = false;
          });
          console.log('[handleCancel] 已调用 disconnect(true)');

          // 显示后端返回的具体消息
          showTaskResultMessage('cancel', result.message);
          console.log('[handleCancel] 已显示取消成功提示');
        } catch (error) {
          console.error('[handleCancel] 错误:', error);

          // 【增强错误处理】区分错误类型并给出明确提示
          let errorMessage = '取消请求失败';
          if (error instanceof Error) {
            if (
              error.message.includes('timeout') ||
              error.message.includes('超时')
            ) {
              errorMessage = '取消请求超时，任务可能仍在运行';
            } else if (
              error.message.includes('Failed to fetch') ||
              error.message.includes('Network')
            ) {
              errorMessage = '网络连接失败，请刷新页面重试';
            } else {
              errorMessage = error.message;
            }
          }

          showTaskControlMessage('cancel', false, errorMessage);

          // ✅ 即使出错也要确保UI状态更新
          resetUiFlags();

          // 【重试机制】错误情况下也等待cancelled事件
          let retries = 0;
          while (retries < 3) {
            await new Promise((resolve) => setTimeout(resolve, 500));
            if (hasReceivedCancelEventRef.current) {
              console.log('[handleCancel] 异常情况下仍收到 cancelled 事件');
              break;
            }
            retries++;
          }
          hasReceivedCancelEventRef.current = false;
          // 2026-08-27 小欧 修复#10: 新签名 (stopServer, force), force=true 使 manualDisconnect=true 禁止自动重连
          disconnect(true, true);

          console.log('[handleCancel] 已处理异常，强制断开SSE连接');
        }
      } else {
        console.warn('[handleCancel] 没有有效的 taskId，可能任务尚未开始');

        // 【问题4修复】即使没有taskId，也要更新UI状态并断开连接
        resetUiFlags();

        // 断开SSE连接
        // 2026-08-27 小欧 修复#10: 新签名 (stopServer, force), force=true 使 manualDisconnect=true 禁止自动重连
        disconnect(true, true);

        // 显示提示
        showTaskResultMessage('cancel', '任务尚未开始或已结束，请求已取消');
      }
    } finally {
      // 兜底：确保取消标志重置（保留外层，删内层重复重置）
      cancelInProgressRef.current = false;
    }
  }, [
    serverTaskId,
    sessionId,
    resetUiFlags,
    callCancelApi,
    waitForCancelOrTimeout,
    waitTimerRef,
    disconnect,
    hasReceivedCancelEventRef,
    cancelInProgressRef,
  ]);

  /**
   * handleTogglePause - 暂停/继续任务执行
   *
   * 功能：
   * 1. 检查是否有活跃任务
   * 2. 根据当前暂停状态调用 pause 或 resume API
   * 3. 更新本地暂停状态
   */
  const handleTogglePause = useCallback(async () => {
    if (!serverTaskId) {
      showNoActiveTaskWarning();
      return;
    }

    try {
      if (!isPaused) {
        // 暂停：发送暂停请求
        const result = await taskControlApi.pause(
          serverTaskId ?? undefined,
          sessionId ?? undefined
        );
        console.log('⏸️ [handleTogglePause] 已发送暂停请求，后端返回:', result);

        // 更新前端暂停状态
        setIsPaused(true);
        isPausedRef.current = true;

        // 显示后端返回的具体消息
        showTaskResultMessage('pause', result.message);
      } else {
        // 继续：发送恢复请求
        const result = await taskControlApi.resume(
          serverTaskId ?? undefined,
          sessionId ?? undefined
        );
        console.log('▶️ [handleTogglePause] 已发送恢复请求，后端返回:', result);

        // 更新前端暂停状态
        setIsPaused(false);
        isPausedRef.current = false;

        // 显示后端返回的具体消息
        showTaskResultMessage('resume', result.message);
      }
    } catch (error) {
      console.error('❌ [handleTogglePause] 暂停/继续请求失败:', error);
      // 使用统一错误处理中心 - 任务控制失败
      handleError(error, { source: 'api' });
    }
  }, [serverTaskId, sessionId, isPaused, isPausedRef, setIsPaused]);

  return {
    handleCancel,
    handleTogglePause,
  };
};
