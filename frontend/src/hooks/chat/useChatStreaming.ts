/**
 * useChatStreaming Hook - SSE协议与流式状态管理
 *
 * 功能：
 * - SSE相关状态管理（streamingContentRef, streamingStepsRef, executionStepsRef）
 *
 * 设计说明（按方案2.1.7）：
 * - 先创建Hook但暂不使用，保持NewChatContainer原样
 * - 仅迁移SSE相关状态到Refs，供后续Task 3.1切换使用
 * - 导出Refs供NewChatContainer使用
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { useRef, useEffect } from "react";
import type { Message } from "../../types/chat";
import type { ExecutionStep } from "../../utils/sse";
import { useSSE } from "../../utils/sse";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * useChatStreaming Hook返回值
 */
export interface UseChatStreamingReturn {
  // 流式接收状态
  isReceiving: boolean;
  
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
 * 迁移自：NewChatContainer.tsx 中的SSE相关Ref（第123-129行）
 * - streamingContentRef：累积AI回复内容
 * - streamingStepsRef：累积执行步骤
 * - executionStepsRef：当前executionSteps
 * 
 * 设计（按方案步骤2.1.7）：
 * - NewChatContainer保持原样，暂不使用新Hook
 * - 仅迁移流式状态管理逻辑到Hook
 * - 后续Task 3.1阶段切换使用
 * 
 * @param messages - 消息列表（用于同步executionSteps到ref）
 * @returns isReceiving, streamingContentRef, streamingStepsRef, executionStepsRef
 */
export const useChatStreaming = (messages: Message[]): UseChatStreamingReturn => {
  // ========================================
  // Refs - 流式状态
  // 迁移自：NewChatContainer.tsx 第123-129行
  // ========================================
  
  // 【小查修复】用于在回调中获取最新的executionSteps
  const executionStepsRef = useRef<ExecutionStep[]>([]);
  
  // 累积AI回复内容
  const streamingContentRef = useRef('');
  
  // 累积执行步骤
  const streamingStepsRef = useRef<ExecutionStep[]>([]);
  
  // ========================================
  // useSSE Hook（空实现，按方案2.1.7暂不使用）
  // ========================================
  
  const { isReceiving } = useSSE(
    { baseURL: "", sessionId: "" } as any,
    undefined,
    undefined,
    undefined,
    undefined
  );
  
  // ========================================
  // 同步executionSteps到ref
  // 迁移自：NewChatContainer.tsx 第784-787行
  // ========================================
  
  useEffect(() => {
    // 同步最新executionSteps到ref，供onComplete使用
    executionStepsRef.current = messages.length > 0 
      ? messages[messages.length - 1].executionSteps || []
      : [];
  }, [messages]);
  
  // ========================================
  // 返回值
  // ========================================
  
  return {
    isReceiving,
    streamingContentRef: streamingContentRef as React.MutableRefObject<string>,
    streamingStepsRef: streamingStepsRef as React.MutableRefObject<ExecutionStep[]>,
    executionStepsRef: executionStepsRef as React.MutableRefObject<ExecutionStep[]>,
  };
};