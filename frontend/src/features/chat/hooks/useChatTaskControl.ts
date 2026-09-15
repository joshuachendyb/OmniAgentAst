// 编辑历史: 2026-08-26 小欧 - 参与P1-P7: 任务取消/暂停控制对齐final_cancel事件(7.7)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.5-19删内层finally/20 抽callCancelApi/waitForCancelOrTimeout/resetUiFlags编排
// 编辑历史: 2026-08-28 小强 - hooks修复#15: waitForCancelOrTimeout加5s超时兜底Promise.race, 防永久挂起
// 编辑历史: 2026-09-09 小欧 - 会话页console日志治理(北京老陈指示「与后端消息不匹配的必须一致起来」): 3 处「cancelled 事件」文案
//   对齐后端现行取消终态契约 type=final+outcome=cancelled(waitForCancelEvent 2处 + handleCancel 1处)——取消事件已不存在,
//   取消收尾单一由 final+outcome=cancelled 承担(sseParser 4.4.1 所述), 日志反映系统实际 — 小欧-2026-09-09
// 编辑历史: 2026-09-15 20:13:04 小欧 - P-008注释清理: 去除取消链路[41]遗留F2/F4'代号, 改描述性术语(与commit b79b79b清理口径一致) — 小欧-2026-09-15 20:13:04
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
  // 2026-09-15 小欧 [41]v1.3: 删强断连病根+取消失败复位点唯一化
  // 取消确认由 SSE 自然流到达的 final+cancelled 承载，前端不再主动 disconnect
  const handleCancel = useCallback(async () => {
    // 【防重复点击】如果正在取消中，忽略后续点击
    if (cancelInProgressRef.current) {
      return;
    }
    cancelInProgressRef.current = true;

    const taskIdToCancel = serverTaskId;

    try {
      if (taskIdToCancel) {
        try {
          showTaskControlInfo('正在取消任务...');

          // ✅【方案1】立即更新UI状态，给用户即时反馈
          resetUiFlags();

          // ✅【关键修复】不立即断开连接！等待后端发送cancelled/final事件
          const result = await callCancelApi(taskIdToCancel, sessionId);

          // 删除多余等待: await waitForCancelOrTimeout() — 死代码（3s<5s，5s分支永不触发）

          // ✅ 停止所有进行中的倒计时
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
          }

          // 删除强制断连 disconnect(true, true) — 病根（掐死SSE通道，丢final帧的唯一动作）

          // 显示后端返回的具体消息
          showTaskResultMessage('cancel', result.message);
        } catch (error) {
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

          // 取消失败/无取消终态帧路径兜底：显式复位闸，防取消闸永锁
          cancelInProgressRef.current = false;
        }
      } else {
        // 【问题4修复】即使没有taskId，也要更新UI状态
        resetUiFlags();

        // 无taskId路径兜底：显式复位闸，防取消闸永锁
        cancelInProgressRef.current = false;

        // 显示提示
        showTaskResultMessage('cancel', '任务尚未开始或已结束，请求已取消');
      }
    } finally {
      // 复位点唯一化：finally不再无条件复位（成功取消路径由取消终态帧 isCancelEvent 分支复位）
      // 仅保留兜底：若 try/catch 都未复位（极端异常），finally 兜底防永久锁死
      if (cancelInProgressRef.current) {
        cancelInProgressRef.current = false;
      }
    }
  }, [
    serverTaskId,
    sessionId,
    resetUiFlags,
    callCancelApi,
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

        // 更新前端暂停状态
        setIsPaused(false);
        isPausedRef.current = false;

        // 显示后端返回的具体消息
        showTaskResultMessage('resume', result.message);
      }
    } catch (error) {
      // 使用统一错误处理中心 - 任务控制失败
      handleError(error, { source: 'api' });
    }
  }, [serverTaskId, sessionId, isPaused, isPausedRef, setIsPaused]);

  return {
    handleCancel,
    handleTogglePause,
  };
};
