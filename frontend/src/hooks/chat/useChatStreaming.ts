/**
 * useChatStreaming Hook - SSE协议与流式状态管理
 *
 * 功能：
 * - 管理SSE连接和流式状态
 * - 提供发送消息、中断任务等操作
 * - 集成useChatCallbacks中的回调函数
 * - 提供executeSend方法处理完整发送流程
 *
 * 设计说明：
 * - 作为SSE连接的核心管理Hook
 * - 依赖useChatState和useChatCallbacks
 * - 提供完整的SSE功能接口
 *
 * @author 小强
 * @version 2.1.0
 * @since 2026-04-21
 * @update 2026-04-22 添加executeSend方法，迁移executeStreamSend逻辑
 */

import { useCallback } from "react";
import type { UseChatStateReturn } from "./useChatState";
import type { UseChatCallbacksReturn } from "./useChatCallbacks";
import type { ExecutionStep } from "../../utils/sse";
import type { Message } from "../../types/chat";
import { useSSE } from "../../utils/sse";
import { sessionApi } from "../../services/api";
import { getClientInfo } from "../../utils/clientInfo";
import { handleError } from "../../utils/errorHandler";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * SSE配置参数
 */
export interface SSEConfig {
  baseURL: string;
  sessionId: string | null;
}

/**
 * useChatStreaming Hook返回值
 */
export interface UseChatStreamingReturn {
  // 流式接收状态
  isReceiving: boolean;
  setIsReceiving: (receiving: boolean) => void;
  
  // 执行步骤
  executionSteps: ExecutionStep[];
  
  // 当前响应
  currentResponse: string;
  
  // SSE操作
  sendMessage: (content: string, sessionId?: string) => Promise<void>;
  disconnect: (stopServer?: boolean, force?: boolean, callback?: () => void) => void;
  clearSteps: () => void;
  
  // 服务器任务ID
  serverTaskId: string | null;
  
  // Refs - 用于累积流式内容（供外部访问）
  streamingContentRef: React.MutableRefObject<string>;
  streamingStepsRef: React.MutableRefObject<ExecutionStep[]>;
  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
  
  // 【小强 2026-04-22】executeSend - 完整的发送流程
  executeSend: (userMessage: Message) => Promise<void>;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatStreaming - SSE协议与流式状态管理
 * 
 * 迁移自：NewChatContainer.tsx 中的SSE相关逻辑
 * - useSSE Hook配置和调用
 * - 发送消息、中断任务等操作
 * - 流式状态管理
 * - executeStreamSend 完整逻辑（2026-04-22迁移）
 * 
 * @param state - useChatState返回的状态对象
 * @param callbacks - useChatCallbacks返回的回调函数
 * @param config - SSE配置（baseURL, sessionId）
 * @returns SSE相关状态和操作
 */
export const useChatStreaming = (
  state: UseChatStateReturn,
  callbacks: UseChatCallbacksReturn,
  config: SSEConfig
): UseChatStreamingReturn => {
  const { sessionId } = state;
  const { onStep, onChunk, onComplete, onError, onPaused, onResumed, onShowSteps, onRetry } = callbacks;
  
  // 使用useSSE Hook
  const {
    isReceiving,
    setIsReceiving,
    executionSteps,
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
    serverTaskId,
  } = useSSE(
    {
      baseURL: config.baseURL,
      sessionId: sessionId || "default-session",
    },
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onShowSteps,
    onRetry
  );
  
  // 从state中获取Refs
  const {
    streamingContentRef,
    streamingStepsRef,
    executionStepsRef,
    // 【小强 2026-04-22】需要解构的Refs和状态setters
    currentSessionIdRef,
    replyUserMessageIdRef,
    waitTimerRef,
  } = state;
  
  // 【小强 2026-04-22】从state解构需要的setters
  const {
    setLoading,
    setWaitTime,
    setIsRetrying,
    setMessages,
  } = state;
  
  // 发送消息函数（包装useSSE的sendMessage）
  const sendMessage = useCallback(async (content: string, customSessionId?: string) => {
    try {
      // 清理之前的流式内容
      streamingContentRef.current = '';
      streamingStepsRef.current = [];
      
      // 调用useSSE的sendMessage
      return await sendStreamMessage(content, customSessionId);
    } catch (error) {
      console.error("发送消息失败:", error);
      throw error;
    }
  }, [sendStreamMessage, streamingContentRef, streamingStepsRef]);
   
   // 【小沈 2026-04-22】中断任务函数
   const disconnectWithParams = useCallback((stopServer?: boolean, force?: boolean, callback?: () => void) => {
    disconnect();
    // 清理流式状态
    streamingContentRef.current = '';
    streamingStepsRef.current = [];
    if (callback) callback();
  }, [disconnect, streamingContentRef, streamingStepsRef]);
  
  // 【小强 2026-04-22】executeSend - 完整的发送流程
  // 迁移自：NewChatContainer.tsx 的 executeStreamSend 函数
  const executeSend = useCallback(async (userMessage: Message) => {
    console.log("📡 [executeSend] 开始发送消息");
    
    // 1. 启动等待计时器
    setLoading(true);
    setWaitTime(0);
    setIsRetrying(false);
    if (waitTimerRef.current) {
      clearInterval(waitTimerRef.current);
    }
    waitTimerRef.current = setInterval(() => {
      setWaitTime((t: number) => t + 1);
    }, 1000);
    clearSteps();

    // 2. 保存用户消息到后端
    const currentSessionId = currentSessionIdRef.current || sessionId;
    
    let backendUserMessageId: number | null = null;
    
    if (currentSessionId) {
      try {
        // 获取客户端信息
        const clientInfo = getClientInfo();
        console.log("🔍 [executeSend] 客户端信息:", clientInfo);
        
        console.log("🔍 [executeSend] 在调用AI之前先保存用户消息:", userMessage);
        const saveResult = await sessionApi.saveMessage(currentSessionId, {
          role: "user",
          content: userMessage.content,
          client_os: clientInfo.client_os,
          browser: clientInfo.browser,
          device: clientInfo.device,
          network: clientInfo.network,
        });
        
        // 保存用户消息ID，用于AI消息关联
        backendUserMessageId = saveResult?.message_id || null;
        replyUserMessageIdRef.current = backendUserMessageId;
        
        // 用后端返回的ID更新用户消息ID
        if (backendUserMessageId) {
          setMessages((prev) => {
            const newMessages = [...prev];
            const userMsgIndex = newMessages.findIndex(m => m.id === userMessage.id);
            if (userMsgIndex !== -1) {
              newMessages[userMsgIndex] = {
                ...newMessages[userMsgIndex],
                id: String(backendUserMessageId)
              };
              console.log("✅ [executeSend] 用户消息ID已更新:", backendUserMessageId);
            }
            return newMessages;
          });
        }
        
        console.log("✅ [executeSend] 用户消息保存成功, message_id:", saveResult?.message_id);
      } catch (error) {
        console.error("❌ [executeSend] 保存用户消息失败:", error);
        // 使用统一错误处理中心 - 错误消息保存失败但继续发送AI
        const result = handleError(error, { source: "api", continueOnError: true });
        if (!result.shouldContinue) {
          console.warn("   └─ 保存失败且不能继续");
        }
      }
    } else {
      console.warn("⚠️ [executeSend] 未找到sessionId，无法保存用户消息:", userMessage.id);
    }

    // 3. 创建assistant占位消息
    const assistantId = backendUserMessageId 
      ? (backendUserMessageId + 1).toString() 
      : (Date.now() + 1).toString();
    console.log("🔍 [executeSend] assistant消息ID:", assistantId, "(后端ID:", backendUserMessageId, "+1)");

    const assistantMessage: Message = {
      id: assistantId,
      role: "assistant",
      content: "🤔 AI 正在思考...",
      timestamp: new Date(),
      executionSteps: [],
      isStreaming: true,
      model: undefined,
    };
    setMessages((prev) => [...prev, assistantMessage]);

    // 4. 调用sendMessage发送
    sendMessage(userMessage.content, currentSessionIdRef.current ?? sessionId ?? undefined);
    console.log("✅ [executeSend] sendStreamMessage已调用");
  }, [
    sessionId,
    setLoading,
    setWaitTime,
    setIsRetrying,
    setMessages,
    waitTimerRef,
    currentSessionIdRef,
    replyUserMessageIdRef,
    clearSteps,
    sendMessage,
  ]);

  return {
    // 流式状态
    isReceiving,
    setIsReceiving: setIsReceiving || ((_: boolean) => { /* no-op */ }),
    executionSteps,
    currentResponse,
    
    // SSE操作
    sendMessage,
    disconnect: disconnectWithParams,
    clearSteps,
    serverTaskId: serverTaskId || null,
    
    // Refs
    streamingContentRef,
    streamingStepsRef,
    executionStepsRef,
    
    // 【小强 2026-04-22】executeSend
    executeSend,
  };
};
