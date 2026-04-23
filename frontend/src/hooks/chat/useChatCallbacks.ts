/**
 * useChatCallbacks Hook - 统一回调管理
 *
 * 功能：
 * - 管理所有SSE回调函数（onStep, onChunk, onComplete, onError, onPaused, onResumed）
 * - 处理暂停缓冲区的数据回放
 * - 统一错误处理和状态更新
 *
 * 设计原则：
 * 1. 回调集中管理：所有SSE回调集中在一个Hook中
 * 2. 依赖注入：通过参数接收状态和函数依赖
 * 3. 闭包安全：正确使用useCallback和依赖数组
 * 4. 性能优化：避免不必要的重渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { useCallback } from "react";
import type { Message } from "../../types/chat";
import type { ExecutionStep } from "../../utils/sse";
import type { UseChatStateReturn } from "./useChatState";
import { handleSSEError, handleApiError, ErrorType } from "../../utils/errorHandler";
import { logAIComplete, logAIError } from "../../utils/chatLogger";
import { sessionApi } from "../../services/api";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * SSE错误类型
 */
interface SSEError {
  type: string;
  error_type: string;
  error_message: string;
  timestamp: string;
  model?: string;
  provider?: string;
  details?: string;
  stack?: string;
  retryable?: boolean;
  retry_after?: number;
  recoverable?: boolean;
  context?: {
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

/**
 * SSEMetadata类型
 */
interface SSEMetadata {
  model?: string;
  provider?: string;
  display_name?: string;
}

/**
 * useChatCallbacks Hook返回值
 */
export interface UseChatCallbacksReturn {
  onStep: (step: ExecutionStep) => void;
  onChunk: (chunk: string, is_reasoning?: boolean) => void;
  onComplete: (
    fullResponse: string,
    metadata?: string | SSEMetadata,
    executionStepsFromSSE?: ExecutionStep[]
  ) => Promise<void>;
  onError: (error: string | SSEError) => void;
  onPaused: () => void;
  onResumed: () => void;
  onShowSteps: (show: boolean) => void;
  onRetry: (message: string, waitTime?: number) => void;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatCallbacks - 统一回调管理Hook
 * 
 * 迁移自：NewChatContainer.tsx 中的所有SSE回调函数
 * - onStep: 处理执行步骤
 * - onChunk: 处理内容片段
 * - onComplete: 处理流式完成
 * - onError: 处理错误
 * - onPaused: 处理暂停事件
 * - onResumed: 处理恢复事件
 * 
 * @param state - useChatState返回的状态对象
 * @param streaming - useChatStreaming返回的流式对象（可选）
 * @returns 所有SSE回调函数
 */
export const useChatCallbacks = (
  state: UseChatStateReturn,
  streaming?: {
    setIsReceiving: (receiving: boolean) => void;
  }
): UseChatCallbacksReturn => {
  // 解构状态
  const {
    setMessages,
    setLoading,
    setWaitTime,
    setIsRetrying,
    setIsPaused,
    sessionId,
    setSessionTitle,
    setShowExecution,
    
    // Refs
    messagesEndRef,
    currentSessionIdRef,
    displayBufferRef,
    isPausedRef,
    executionStepsRef,
    streamingContentRef,
    streamingStepsRef,
    logFlagsRef,
    hasReceivedInterruptEventRef,
    interruptInProgressRef,
    waitTimerRef,
  } = state;

  // ==================== onStep回调 ====================

  const onStep = useCallback((step: ExecutionStep) => {
    // ✅ 如果正在中断中，忽略所有事件（防止中断后还收到start等事件）
    if (interruptInProgressRef.current) {
      console.log(`[中断] 忽略中断过程中收到的事件: ${step.type}`);
      return;
    }
    
    // 【中断检测】记录是否收到了interrupted事件
    if (step.type === "interrupted" || (step.type === "incident" && (step as any).incident_value === "interrupted")) {
      hasReceivedInterruptEventRef.current = true;
      console.log("[中断] 收到 interrupted 事件");
    }
    
    // 【小沈修复 2026-04-16】在收到第一个步骤时重置暂停状态
    // 问题原因：如果 isPausedRef.current = true，所有步骤会存入 displayBufferRef 而不是 streamingStepsRef
    // 这发生在：1)用户先按暂停再创建新会话 2)从sessionStorage恢复暂停状态 3)后端发送paused事件
    // 解决：当收到第一个非 chunk 步骤时，如果 isPausedRef.current = true，重置为 false
    if (step.type !== "chunk" && step.type !== "error" && isPausedRef.current) {
      console.log("⚠️ [onStep] 重置暂停状态 isPausedRef=true -> false");
      setIsPaused(false);
    }
    
    // type 处理流程日志（解析 -> 存储 -> 渲染）
    console.log("📝 type=%s timestamp=%s", step.type, step.timestamp ? new Date(step.timestamp).toLocaleTimeString() : 'N/A');
    
    // 只打印第一个chunk，减少日志
    if (step.type === "chunk") {
      if (!logFlagsRef.current.chunkFirstDone) {
        console.log("🔍 [onStep] 收到步骤, type= chunk (第一个)");
        logFlagsRef.current.chunkFirstDone = true;
      }
    }
    
    // ⭐ 暂停时存入缓冲区，不直接显示（原有逻辑保留）
    if (isPausedRef.current) {
      console.log("⏸️ [onStep] 暂停中，存入缓冲区, type:", step.type);
      displayBufferRef.current.push({ type: "step", step });
      return;
    }
    
    // ⭐ 累积到ref，不触发重渲染
    streamingStepsRef.current = [...streamingStepsRef.current, step];
    
    // 【修复】第一个step时streamingStepsRef还是空的，需要用当前step
    const currentSteps = streamingStepsRef.current.length > 0 
      ? streamingStepsRef.current 
      : [step];
    
    // 实时更新UI，每次都更新
    setMessages((prev) => {
      const lastMessage = prev[prev.length - 1];
      if (!lastMessage || lastMessage.role !== "assistant") {
        // 【关键修复 2026-04-13】任何step都创建消息，不只是start
        // 因为后端可能直接发incident/retrying，不发start
        const extractedDisplay_name = step.display_name;
        let finalDisplay_name = extractedDisplay_name;
        if (!finalDisplay_name && step.model && step.provider) {
          finalDisplay_name = `${step.provider} (${step.model})`;
        }
        
        const newAssistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: "assistant",
          content: step.content || (step.type === "error" ? step.error_message || "执行出错" : "🤔 AI 正在思考..."),
          timestamp: step.timestamp ? new Date(step.timestamp) : new Date(),
          executionSteps: currentSteps,
          isStreaming: step.type !== "error" && step.type !== "final",
          model: step.model,
          provider: step.provider,
          display_name: finalDisplay_name,
        };
        return [...prev, newAssistantMessage];
      }
      
      // 更新最后一条消息的executionSteps
      // 【修复 2026-04-16】同时更新 isStreaming，确保 final/error 时显示正确状态
      const updated = [...prev];
      updated[updated.length - 1] = {
        ...lastMessage,
        executionSteps: currentSteps,
        // final/error 时必须设置 isStreaming=false，停止 DynamicStatusDisplay
        isStreaming: step.type !== "error" && step.type !== "final" 
          ? lastMessage.isStreaming 
          : false,
      };
      return updated;
    });

    // onStep更新后滚动到底部
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  }, [
    setMessages,
    setIsPaused,
    messagesEndRef,
    // Refs dependencies
    interruptInProgressRef,
    hasReceivedInterruptEventRef,
    isPausedRef,
    displayBufferRef,
    streamingStepsRef,
    executionStepsRef,
    logFlagsRef,
  ]);

  // ==================== onChunk回调 ====================

  const onChunk = useCallback((chunk: string, is_reasoning?: boolean) => {
    // 精简日志：调试通过，不再打印每个chunk
    
    // ⭐ 暂停时存入缓冲区，不直接显示（原有逻辑保留）
    if (isPausedRef.current) {
      console.log("⏸️ [onChunk] 暂停中，存入缓冲区");
      displayBufferRef.current.push({ type: "chunk", content: chunk, is_reasoning });
      return;
    }
    
    // ⭐ 累积到ref，不触发重渲染
    streamingContentRef.current += chunk;
    
    // 【小沈注释 2026-04-18】去掉节流机制，每次都更新UI
    setMessages((prev) => {
      const lastMessage = prev[prev.length - 1];
      if (
        lastMessage &&
        lastMessage.role === "assistant" &&
        lastMessage.isStreaming
      ) {
        const updated = [...prev];
        const newIs_reasoning = is_reasoning ?? false;
        updated[updated.length - 1] = {
          ...lastMessage,
          content: streamingContentRef.current,
          is_reasoning: newIs_reasoning,
        };
        return updated;
      }
      return prev;
    });
  }, [
    setMessages,
    // Refs dependencies
    isPausedRef,
    displayBufferRef,
    streamingContentRef,
  ]);

  // ==================== onComplete回调 ====================

  const onComplete = useCallback(async (
    fullResponse: string,
    metadata?: string | SSEMetadata,
    executionStepsFromSSE?: ExecutionStep[]
  ) => {
    // ✅ 支持旧格式（model 字符串）和新格式（metadata 对象）
    const metadataObj =
      typeof metadata === "string" ? { model: metadata } : metadata || {};

    // 🔴 修复：处理 AI 返回空内容的情况
    // 【小新修复 2026-03-14】补充完整的错误字段，避免导出时缺少error_type等
    let finalResponse = fullResponse;
    let isError = false;
    let errorType: string | undefined = undefined;
    // 【小沈修改2026-04-15】删除errorCode字段，统一使用errorMessage
    let errorMessage: string | undefined = undefined;
    
    if (!finalResponse || !finalResponse.trim()) {
      finalResponse = "抱歉，我暂时无法回答这个问题。请您稍后再尝试，或者换个方式提问。";
      isError = true; // 标记为错误类型，以便显示红色样式
      // 【小新修复 2026-03-14】补充错误字段，与onError保持一致
      errorType = "empty_response";
      // 【小沈修改2026-04-15】删除errorCode
      errorMessage = "模型未能生成有效回复，请尝试更换问题或稍后重试";
      console.warn("⚠️ AI 返回了空内容，已使用默认回复，errorType:", errorType);
    }

    setMessages((prev) => {
      const lastMessage = prev[prev.length - 1];
      if (lastMessage && lastMessage.role === "assistant") {
        const updated = [...prev];
        // 【小强修复 2026-03-18】修复竞争条件导致的final/steps丢失问题
        // 问题：onStep异步更新message.executionSteps，onComplete可能在其完成前执行，导致覆盖
        // 解决：优先使用message中已有的executionSteps（如果更长），否则使用SSE传递的
        const sseSteps = executionStepsFromSSE || executionStepsRef.current || [];
        const msgSteps = lastMessage.executionSteps || [];
        // 选择更长的那个，避免覆盖已存在的数据
        const latestSteps = msgSteps.length >= sseSteps.length ? msgSteps : sseSteps;
        
        // 【调试日志】说明：为什么有两个steps数量？
        // - SSE传递的steps：本次对话实时收到的步骤数量（比如：start → thought → chunk → final）
        // - message已有的steps：这个消息之前保存的步骤数量（比如：历史会话加载进来的）
        // - 最终选择：取两者中更多的那个来保存（确保不丢失数据）
        console.log("📊 type=%s AI完成 实时=%d 历史=%d 保存=%d", sseSteps.length, msgSteps.length, latestSteps.length);
        
        // 【小健修复 2026-04-13】优先使用streamingContentRef累积内容，确保不丢失
        const finalContent = streamingContentRef.current || finalResponse;
        
        // 【小健修复 2026-04-13】优先使用streamingStepsRef累积步骤，再与SSE和message比较
        const refSteps = streamingStepsRef.current || [];
        // 取三者中最长的，确保不丢失任何数据
        const allSteps = [refSteps, executionStepsFromSSE || [], msgSteps];
        const finalSteps = allSteps.reduce((longest, curr) => 
          curr.length > longest.length ? curr : longest, []);
        
        updated[updated.length - 1] = {
          ...lastMessage,
          content: finalContent,
          isStreaming: false,
          is_reasoning: false,
          isError: isError,
          errorType: errorType,
          // 【小沈修改2026-04-15】删除errorCode
          errorMessage: errorMessage,
          model: metadataObj.model || lastMessage.model,
          provider: metadataObj.provider || lastMessage.provider,
          display_name: metadataObj.display_name || lastMessage.display_name,
          executionSteps: finalSteps,
        };
        console.log("  └─ ✅ 已更新 (ref累积+SSE+历史) steps:", finalSteps.length, "| last3:", finalSteps.slice(-3).map((s: any) => s.type).join(","));
        return updated;
      }
      return prev;
    });

    // 保存AI回复到会话
    // 【小沈修复2026-03-03】现在只保存AI回复消息，用户消息已在发送前保存
    // 这样更加健壮，即使AI响应失败，用户消息也已保存
    const currentSessionId = currentSessionIdRef.current || sessionId;
    // 【小查修复 2026-03-14】恢复使用executionStepsFromSSE参数
    // 历史教训：2026-03-12 小沈提交commit 800f0fd27时，将参数从ExecutionStep[]改为{sseData?: {execution_steps?: ExecutionStep[]}}
    // 但调用方sse.ts第716行仍然传递ExecutionStep[]数组，导致类型不匹配
    // 结果：sseData?.execution_steps永远是undefined，思考过程(execution_steps)无法保存到数据库
    // 症状：AI回复完成后刷新页面，"思考"部分的详细内容丢失，只剩下"正在分析任务..."
    // 教训：修改函数签名时必须同步修改所有调用方，不能单方面改变参数结构！
    // const stepsFromSSE = executionStepsFromSSE;  // 已废弃，后端自动保存
    if (currentSessionId && finalResponse && finalResponse.trim()) {
      // 🔴 修复：添加详细的调试日志
      // console.log("💾 [保存AI回复] 正在保存到数据库:");
      // console.log("  ├─ 会话ID:", currentSessionId);
      // console.log("  ├─ 回复长度:", finalResponse.length, "字符");
      // console.log("  ├─ SSE传递的步骤数:", stepsFromSSE?.length, "个");
      // console.log("  └─ ref中的步骤数:", executionStepsRef.current?.length, "个");

      try {
        // 后端在流式结束时自动保存steps到数据库，无需前端触发
        // console.log("✅ type=%s 后端已保存steps");

        // ⭐ 【小新修复 2026-03-04】保存AI回复后不再调用 ensureTitlePersisted
        // 原因：标题应该在用户修改时立即保存，避免版本冲突
        // 如果需要同步最新数据，应该在用户修改标题时处理
        // console.log("✅ [保存AI回复] 保存成功！");
      } catch (saveError: any) {
        console.error("❌ [保存AI回复] 保存失败:", saveError?.message || saveError);
        console.error("   └─ 保存时使用的会话ID:", currentSessionId);
        
        // 使用统一错误处理中心
        const errorResult = handleApiError(saveError);
        
        // 根据错误类型进行特殊处理
        if (errorResult.errorType === ErrorType.SESSION_CONFLICT) {
          // 409版本冲突 - 尝试从服务器获取最新数据
          try {
            const sessionData = await sessionApi.getSessionMessages(currentSessionId);
            if (sessionData.title) setSessionTitle(sessionData.title);
          } catch (syncError) {
            console.error("   └─ 同步最新数据失败:", syncError);
          }
          return;
        }
        
        // 如果是需要继续执行的错误（如用户消息保存失败），不阻断流程
        if (errorResult.shouldContinue) {
          console.warn("   └─ 保存失败但继续执行:", errorResult.errorType);
          return;
        }
        
        // 其他错误已经通过errorHandler显示提示
        return;
      }
    } else {
      console.warn("⚠️ [保存AI回复] 跳过保存：缺少必要数据");
      console.log("   ├─ 会话ID是否为空:", !currentSessionId ? "是（跳过保存）" : "否");
      console.log("   └─ 回复内容是否为空:", !fullResponse ? "是（跳过保存）" : "否");
    }

    console.log("✅ type=%s AI流式完成 %s", new Date().toLocaleTimeString());
    
    // ========== 黄色结束标志 ==========
    logAIComplete(fullResponse?.length || 0);
    // ==================================
    
    setLoading(false);
    // ⭐ 停止等待计时器
    if (waitTimerRef.current) {
      clearInterval(waitTimerRef.current);
      waitTimerRef.current = null;
    }
    setWaitTime(0);
    setIsRetrying(false);
    
    // ⭐ 【小资优化 2026-04-13】完成后清理ref，准备下一次对话
    streamingContentRef.current = '';
    streamingStepsRef.current = [];
    // lastUpdateTimeRef.current = 0;
    
    // console.log("✅ [onComplete] AI回答保存完成！");
  }, [
    setMessages,
    setLoading,
    setWaitTime,
    setIsRetrying,
    setSessionTitle,
    sessionId,
    // Refs dependencies
    currentSessionIdRef,
    executionStepsRef,
    streamingContentRef,
    streamingStepsRef,
    waitTimerRef,
  ]);

  // ==================== onError回调 ====================

  const onError = useCallback((
    error: string | SSEError
  ) => {
    // ✅ 支持字符串和对象两种格式
    const errorObj =
      typeof error === "string"
        ? { type: "error", error_type: "unknown_error", error_message: error, timestamp: new Date().toISOString() }
        : error;

    console.error("🔴 [onError] SSE 流式错误:", errorObj);
    
    // ⭐ 使用统一错误处理中心errorHandler处理提示
    const errorResult = handleSSEError(errorObj, { 
      reconnectAttempts: 0, 
      maxRetries: 0,
      onReconnect: undefined 
    });
    
    // 如果errorHandler认为不需要显示（如静默错误），则跳过
    if (errorResult.handled === false) {
      return;
    }
    
    // ⭐ 暂停时存入缓冲区（原有逻辑保留）
    if (isPausedRef.current) {
      displayBufferRef.current.push({ type: "error", error: errorObj });
      return;
    }

    // 【小沈注释 2026-04-18】去掉节流机制，每次都更新UI
    setMessages((prev) => {
      const lastMessage = prev[prev.length - 1];
      if (lastMessage && lastMessage.role === "assistant") {
        // 【小强修复 2026-03-18】修复竞争条件 - 选择更长的executionSteps
        const refSteps = executionStepsRef.current || [];
        const msgSteps = lastMessage.executionSteps || [];
        const latestSteps = msgSteps.length >= refSteps.length ? msgSteps : refSteps;
        
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...lastMessage,
          // 错误时直接用错误消息替换内容，不保留"思考中"
          // 【小沈修改2026-04-15】优先使用error_message，兼容旧字段message
          content: (errorObj as any).error_message || (errorObj as any).message || "未知错误",
          isError: true,
          isStreaming: false,
          executionSteps: latestSteps,
          // 【小沈修改2026-04-16】删除details/stack/retryable，后端已删除
          errorType: errorObj.error_type,
          errorMessage: (errorObj as any).error_message || (errorObj as any).message || "",  // 【小沈修改2026-04-15】优先使用error_message
          errorRetryAfter: errorObj.retry_after,
          errorTimestamp: errorObj.timestamp,
          // 【小沈添加2026-04-15】新增recoverable和context字段
          errorRecoverable: (errorObj as any).recoverable,
          errorContext: (errorObj as any).context,
          // 如果 errorObj 中没有 model/provider，使用消息中已有的值
          model: errorObj.model || lastMessage.model,
          provider: errorObj.provider || lastMessage.provider,
        };
        return updated;
      }
      return prev;
    });
    
    // 清理状态
    setLoading(false);
    if (waitTimerRef.current) {
      clearInterval(waitTimerRef.current);
      waitTimerRef.current = null;
    }
    setWaitTime(0);
    setIsRetrying(false);
    
    // 【小沈修改2026-04-15】优先使用error_message，兼容旧字段message
    logAIError((errorObj as any).error_message || (errorObj as any).message || "未知错误");
    
    // ⭐ 完成后清理ref
    streamingContentRef.current = '';
    streamingStepsRef.current = [];
    // lastUpdateTimeRef.current = 0;
  }, [
    setMessages,
    setLoading,
    setWaitTime,
    setIsRetrying,
    // Refs dependencies
    isPausedRef,
    displayBufferRef,
    executionStepsRef,
    streamingContentRef,
    streamingStepsRef,
    waitTimerRef,
  ]);

  // ==================== onPaused回调 ====================

  const onPaused = useCallback(() => {
    console.log("⏸️ [onPaused] SSE 暂停");
    setIsPaused(true);
  }, [setIsPaused]);

  // ==================== onResumed回调 ====================

  const onResumed = useCallback(() => {
    console.log("▶️ [onResumed] 收到恢复事件，缓冲区长度:", displayBufferRef.current.length);
    
    // 从缓冲区按顺序显示数据
    displayBufferRef.current.forEach(data => {
      if (data.type === "chunk" && data.content) {
        // 处理 chunk 类型
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === "assistant" && lastMessage.isStreaming) {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMessage,
              content: lastMessage.content + data.content,
            };
            return updated;
          }
          return prev;
        });
      } else if (data.type === "step" && data.step) {
        // 【关键修复】恢复时要把step添加到executionSteps
        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === "assistant" && lastMessage.isStreaming) {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMessage,
              executionSteps: [...(lastMessage.executionSteps || []), data.step],
            };
            return updated;
          }
          return prev;
        });
      } else if (data.type === "error" && data.error) {
        // 处理 error 类型
        onError(data.error);
      }
    });
    
    // 清空缓冲区
    displayBufferRef.current = [];
    
    // 更新暂停状态
    setIsPaused(false);
    
    // 通知流式组件恢复接收
    if (streaming?.setIsReceiving) {
      streaming.setIsReceiving(true);
    }
  }, [setMessages, setIsPaused, onError, streaming, displayBufferRef]);

  // ==================== onShowSteps回调 ====================

  const onShowSteps = useCallback((show: boolean) => {
    setShowExecution(show);
  }, [setShowExecution]);

  // ==================== onRetry回调 ====================

  const onRetry = useCallback((message: string, waitTime?: number) => {
    console.log("🔄 [onRetry] 收到重试事件:", message, "等待时间:", waitTime);
    setIsRetrying(true);
    if (waitTime !== undefined) {
      setWaitTime(waitTime);
    } else {
      setWaitTime(0);
    }
  }, [setIsRetrying, setWaitTime]);

  // ==================== 返回值 ====================

  return {
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onShowSteps,
    onRetry,
  };
};