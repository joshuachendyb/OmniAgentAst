/**
 * useChatTaskControl Hook - 任务中断与暂停控制
 *
 * 功能：
 * - handleInterrupt: 中断正在执行的任务
 * - handleTogglePause: 暂停/继续任务执行
 * - waitForInterruptEvent: 等待中断事件的内部辅助函数
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

import { useCallback } from "react";
import { taskControlApi } from "../../services/api";
import {
  showTaskControlInfo,
  showTaskResultMessage,
  showTaskControlMessage,
  showNoActiveTaskWarning,
} from "../../utils/chatMessages";
import { handleError } from "../../utils/errorHandler";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * useChatTaskControl 配置参数
 */
export interface UseChatTaskControlOptions {
  // chatState 提供
  setLoading: (v: boolean) => void;
  setIsPaused: (v: boolean) => void;
  interruptInProgressRef: React.MutableRefObject<boolean>;
  hasReceivedInterruptEventRef: React.MutableRefObject<boolean>;
  waitTimerRef: React.MutableRefObject<number | null>;
  isPaused: boolean;
  isPausedRef: React.MutableRefObject<boolean>;
  
  // chatStreaming 提供
  serverTaskId: string | null;
  setIsReceiving: (v: boolean) => void;
  disconnect: (stopServer?: boolean, force?: boolean, callback?: () => void) => void;
  
  // session
  sessionId: string | null;
}

/**
 * useChatTaskControl Hook返回值
 */
export interface UseChatTaskControlReturn {
  handleInterrupt: () => Promise<void>;
  handleTogglePause: () => Promise<void>;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatTaskControl - 任务中断与暂停控制
 * 
 * 迁移自：NewChatContainer.tsx 中的 handleInterrupt 和 handleTogglePause 函数
 * - waitForInterruptEvent: 等待中断事件的内部辅助函数
 * - handleInterrupt: 中断正在执行的任务
 * - handleTogglePause: 暂停/继续任务执行
 * 
 * @param options - 配置参数
 * @returns 任务控制函数
 */
export const useChatTaskControl = (
  options: UseChatTaskControlOptions
): UseChatTaskControlReturn => {
  const {
    setLoading,
    setIsPaused,
    interruptInProgressRef,
    hasReceivedInterruptEventRef,
    waitTimerRef,
    isPaused,
    isPausedRef,
    serverTaskId,
    setIsReceiving,
    disconnect,
    sessionId,
  } = options;

  // =========================================================================
  // 内部辅助函数
  // =========================================================================

  /**
   * 智能等待中断事件函数
   * 等待后端发送 interrupted 事件，最多等待 maxWaitTime
   */
  const waitForInterruptEvent = useCallback(async (
    maxWaitTime = 3000,
    checkInterval = 200
  ): Promise<boolean> => {
    const startTime = Date.now();
    let hasReceivedEvent = false;
    
    while (Date.now() - startTime < maxWaitTime) {
      if (hasReceivedInterruptEventRef.current) {
        console.log("[waitForInterruptEvent] 已收到 interrupted 事件");
        hasReceivedEvent = true;
        break;
      }
      await new Promise(resolve => setTimeout(resolve, checkInterval));
    }
    
    if (!hasReceivedEvent) {
      console.warn(`[waitForInterruptEvent] 在 ${maxWaitTime}ms 内未收到 interrupted 事件，继续执行`);
    }
    
    return hasReceivedEvent;
  }, [hasReceivedInterruptEventRef]);

  // =========================================================================
  // 任务控制函数
  // =========================================================================

  /**
   * handleInterrupt - 中断正在执行的任务
   * 
   * 功能：
   * 1. 防重复点击检查
   * 2. 调用 taskControlApi.cancel 取消任务
   * 3. 智能等待 interrupted 事件
   * 4. 断开SSE连接
   * 5. 更新UI状态
   */
  const handleInterrupt = useCallback(async () => {
    // 【防重复点击】如果正在中断中，忽略后续点击
    if (interruptInProgressRef.current) {
      console.log("[handleInterrupt] 正在中断中，忽略重复点击");
      return;
    }
    interruptInProgressRef.current = true;
    
    const taskIdToCancel = serverTaskId;
    console.log(`[handleInterrupt] serverTaskId=${serverTaskId}, taskIdToCancel=${taskIdToCancel}`);
    
    try {
      if (taskIdToCancel) {
        try {
          showTaskControlInfo("正在中断任务...");
          console.log("[handleInterrupt] 已显示 '正在中断任务...' 提示");
          
          // ✅【方案1】立即更新UI状态，给用户即时反馈
          setLoading(false);
          setIsPaused(false);
          if (setIsReceiving) setIsReceiving(false);
          
          // ✅【方案3】设置超时保护，防止请求长时间挂起
          const timeoutPromise = new Promise<any>((_, reject) => {
            setTimeout(() => reject(new Error("中断请求超时")), 5000);
          });
          
          // ✅【关键修复】不立即断开连接！等待后端发送interrupted/final事件
          // 如果后端正在处理，等它发送完事件后再断开
          // 立即断开会导致收不到interrupted事件，UI一直显示"加载中"
          
          // 使用统一的 taskControlApi（带超时）
          const result = await Promise.race([
            taskControlApi.cancel(taskIdToCancel, sessionId ?? undefined),
            timeoutPromise
          ]) as { success: boolean; message: string };
          console.log("[handleInterrupt] cancel API 返回:", result);
          
          // ✅ 使用智能等待策略等待后端发送interrupted事件
          // 最长等待3000ms，每200ms检查一次
          await waitForInterruptEvent(3000, 200);
          
          // ✅ 停止所有进行中的倒计时
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
            console.log("[handleInterrupt] 已清除waitTimerRef倒计时");
          }
          
          disconnect(true, true, () => {
            console.log("[handleInterrupt] SSE已断开，状态已同步");
            // 在断开连接完成后重置标记
            hasReceivedInterruptEventRef.current = false;
          });
          console.log("[handleInterrupt] 已调用 disconnect(true)");
          
          // 显示后端返回的具体消息
          showTaskResultMessage("interrupt", result.message);
          console.log("[handleInterrupt] 已显示中断成功提示");
        } catch (error) {
          console.error("[handleInterrupt] 错误:", error);
          
          // 【增强错误处理】区分错误类型并给出明确提示
          let errorMessage = "中断请求失败";
          if (error instanceof Error) {
            if (error.message.includes("timeout") || error.message.includes("超时")) {
              errorMessage = "中断请求超时，任务可能仍在运行";
            } else if (error.message.includes("Failed to fetch") || error.message.includes("Network")) {
              errorMessage = "网络连接失败，请刷新页面重试";
            } else {
              errorMessage = error.message;
            }
          }
          
          showTaskControlMessage("interrupt", false, errorMessage);
          
          // ✅ 即使出错也要确保UI状态更新，并延迟断开
          // 无论cancel API是否成功，都需要断开SSE连接
          setLoading(false);
          setIsPaused(false);
          if (setIsReceiving) setIsReceiving(false);
          
          // 【重试机制】错误情况下也等待interrupted事件
          let retries = 0;
          while (retries < 3) {
            await new Promise(resolve => setTimeout(resolve, 500));
            if (hasReceivedInterruptEventRef.current) {
              console.log("[handleInterrupt] 异常情况下仍收到 interrupted 事件");
              break;
            }
            retries++;
          }
          hasReceivedInterruptEventRef.current = false;
          disconnect(true);
          
          console.log("[handleInterrupt] 已处理异常，强制断开SSE连接");
        } finally {
          // 【防重复点击】重置中断标志（无论成功还是失败都重置）
          interruptInProgressRef.current = false;
        }
      } else {
        console.warn("[handleInterrupt] 没有有效的 taskId，可能任务尚未开始");
        
        // 【问题4修复】即使没有taskId，也要更新UI状态并断开连接
        setLoading(false);
        setIsPaused(false);
        if (setIsReceiving) setIsReceiving(false);
        
        // 断开SSE连接
        disconnect(true);
        
        // 显示提示
        showTaskResultMessage("interrupt", "任务尚未开始或已结束，请求已取消");
      }
    } finally {
      // 兜底：确保中断标志重置
      interruptInProgressRef.current = false;
    }
  }, [
    serverTaskId,
    sessionId,
    setLoading,
    setIsPaused,
    setIsReceiving,
    waitTimerRef,
    disconnect,
    hasReceivedInterruptEventRef,
    interruptInProgressRef,
    waitForInterruptEvent,
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
        const result = await taskControlApi.pause(serverTaskId ?? undefined, sessionId ?? undefined);
        console.log("⏸️ [handleTogglePause] 已发送暂停请求，后端返回:", result);
        
        // 更新前端暂停状态
        setIsPaused(true);
        isPausedRef.current = true;
        
        // 显示后端返回的具体消息
        showTaskResultMessage("pause", result.message);
      } else {
        // 继续：发送恢复请求
        const result = await taskControlApi.resume(serverTaskId ?? undefined, sessionId ?? undefined);
        console.log("▶️ [handleTogglePause] 已发送恢复请求，后端返回:", result);
        
        // 更新前端暂停状态
        setIsPaused(false);
        isPausedRef.current = false;
        
        // 显示后端返回的具体消息
        showTaskResultMessage("resume", result.message);
      }
    } catch (error) {
      console.error("❌ [handleTogglePause] 暂停/继续请求失败:", error);
      // 使用统一错误处理中心 - 任务控制失败
      handleError(error, { source: "api" });
    }
  }, [
    serverTaskId,
    sessionId,
    isPaused,
    isPausedRef,
    setIsPaused,
  ]);

  return {
    handleInterrupt,
    handleTogglePause,
  };
};
