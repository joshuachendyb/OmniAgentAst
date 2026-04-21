/**
 * useChatStreaming Hook - SSE协议与流式状态管理
 *
 * 功能：
 * - 管理SSE连接和流式状态
 * - 提供发送消息、中断任务等操作
 * - 集成useChatCallbacks中的回调函数
 *
 * 设计说明：
 * - 作为SSE连接的核心管理Hook
 * - 依赖useChatState和useChatCallbacks
 * - 提供完整的SSE功能接口
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-21
 */

import { useState, useCallback } from "react";
import type { UseChatStateReturn } from "./useChatState";
import type { UseChatCallbacksReturn } from "./useChatCallbacks";
import type { ExecutionStep } from "../../utils/sse";
import { useSSE } from "../../utils/sse";

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
  disconnect: () => void;
  clearSteps: () => void;
  
  // 服务器任务ID
  serverTaskId: string | null;
  
  // Refs - 用于累积流式内容（供外部访问）
  streamingContentRef: React.MutableRefObject<string>;
  streamingStepsRef: React.MutableRefObject<ExecutionStep[]>;
  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
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
  const { onStep, onChunk, onComplete, onError, onPaused, onResumed } = callbacks;
  
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
    onResumed
  );
  
  // 从state中获取Refs
  const {
    streamingContentRef,
    streamingStepsRef,
    executionStepsRef,
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
  
  // 中断任务函数
  const interruptTask = useCallback(() => {
    disconnect();
    // 清理流式状态
    streamingContentRef.current = '';
    streamingStepsRef.current = [];
  }, [disconnect, streamingContentRef, streamingStepsRef]);
  
  return {
    // 流式状态
    isReceiving,
    setIsReceiving,
    executionSteps,
    currentResponse,
    
    // SSE操作
    sendMessage,
    disconnect: interruptTask,
    clearSteps,
    serverTaskId,
    
    // Refs
    streamingContentRef,
    streamingStepsRef,
    executionStepsRef,
  };
};