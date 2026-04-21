/**
 * useChatSession Hook - 会话生命周期管理
 *
 * 功能：
 * - 会话状态管理（sessionId, sessionTitle, sessionVersion）
 * - 会话函数（loadSession, handleNewSession, handleClear）
 *
 * 设计说明（按方案2.2.7）：
 * - 先创建Hook但暂不使用，保持NewChatContainer原样
 * - 在后续Task 3.1阶段切换使用
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { useState, useCallback, useRef } from "react";
import type { Message } from "../../types/chat";
import { loadHistoryMessages } from "../../utils/chatHistory";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * useChatSession Hook返回值
 * 
 * 设计（按方案2.2.7）：
 * - NewChatContainer保持原样，暂不使用新Hook
 * - 仅迁移会话状态管理逻辑到Hook
 * - 后续Task 3.1阶段切换使用
 */
export interface UseChatSessionReturn {
  // 会话状态
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  
  // Refs
  currentSessionIdRef: React.MutableRefObject<string | null>;
  
  // 会话函数
  loadSession: (sessionId: string) => Promise<Message[]>;
  handleNewSession: () => void;
  handleClear: () => void;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatSession - 会话生命周期管理
 * 
 * 迁移自：NewChatContainer.tsx 中的会话相关逻辑
 * - sessionId, sessionTitle, sessionVersion状态
 * - handleNewSession, handleClear, loadHistoryMessages函数
 * 
 * 设计（按方案步骤2.2.7）：
 * - NewChatContainer保持原样，暂不使用新Hook
 * - 仅迁移会话状态管理逻辑到Hook
 * - 后续Task 3.1阶段切换使用
 * 
 * @returns sessionId, sessionTitle, sessionVersion, loadSession, handleNewSession, handleClear
 */
export const useChatSession = (): UseChatSessionReturn => {
  // ========================================
  // 会话状态
  // 迁移自：NewChatContainer.tsx 第100-102行
  // ========================================
  
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string>("新会话");
  const [sessionVersion, setSessionVersion] = useState<number>(1);
  
  // 用于在回调中获取最新的sessionId
  const currentSessionIdRef = useRef<string | null>(null);
  
  // ========================================
  // Helper Functions
  // ========================================
  
  /**
   * loadSession - 加载会话历史
   * 迁移自：NewChatContainer.tsx 第1207行
   */
  const loadSession = useCallback(async (sid: string): Promise<Message[]> => {
    try {
      const result = await loadHistoryMessages(sid);
      if (result) {
        setSessionId(result.sessionId);
        currentSessionIdRef.current = result.sessionId;
        return result.messages || [];
      }
      return [];
    } catch (error) {
      console.error("加载会话失败:", error);
      return [];
    }
  }, []);
  
  /**
   * handleNewSession - 新建会话
   * 迁移自：NewChatContainer.tsx 第2189行
   */
  const handleNewSession = useCallback(() => {
    console.log("[useChatSession] handleNewSession - 新建会话");
    setSessionId(null);
    currentSessionIdRef.current = null;
    setSessionTitle("新会话");
    setSessionVersion(1);
  }, []);
  
  /**
   * handleClear - 清空对话
   * 迁移自：NewChatContainer.tsx 第2197行
   */
  const handleClear = useCallback(() => {
    console.log("[useChatSession] handleClear - 清空对话");
    setSessionId(null);
    currentSessionIdRef.current = null;
    setSessionTitle("新会话");
    setSessionVersion(1);
  }, []);
  
  // ========================================
  // 返回值
  // ========================================
  
  return {
    sessionId,
    sessionTitle,
    sessionVersion,
    currentSessionIdRef: currentSessionIdRef as React.MutableRefObject<string | null>,
    loadSession,
    handleNewSession,
    handleClear,
  };
};