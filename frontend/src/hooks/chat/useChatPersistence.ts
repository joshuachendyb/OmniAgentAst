/**
 * useChatPersistence Hook - 状态持久化与恢复
 *
 * 功能：
 * - 防抖保存逻辑（saveMessagesToStorage）
 * - 页面可见性处理（visibilitychange）
 * - 状态恢复（restoreState）
 *
 * 设计说明（按方案2.3.5）：
 * - 先创建Hook但暂不使用，保持NewChatContainer原样
 * - 在后续Task 3.1阶段切换使用
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { useEffect, useCallback } from "react";
import type { Message } from "../../types/chat";
import { STORAGE_KEY } from "../../utils/chatHistory";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * LightState - 轻量级状态（用于持久化）
 */
interface LightState {
  messages?: Message[];
  sessionId?: string | null;
  sessionTitle?: string;
  sessionVersion?: number;
}

/**
 * useChatPersistence Hook返回值
 */
export interface UseChatPersistenceReturn {
  // 保存函数
  saveState: () => void;
  saveStateWithSSECheck: () => void;
  clearStorage: () => void;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatPersistence - 状态持久化与恢复
 * 
 * 迁移自：NewChatContainer.tsx 中的持久化逻辑（第139-170行，第815-880行，第931-1000行）
 * - saveMessagesToStorage：防抖保存到sessionStorage
 * - 页面可见性处理：visibilitychange事件
 * - saveState / saveStateWithSSECheck：状态保存函数
 * 
 * 设计（按方案步骤2.3.5）：
 * - NewChatContainer保持原样，暂不使用新Hook
 * - 仅迁移持久化逻辑到Hook
 * - 后续Task 3.1阶段切换使用
 * 
 * @param messages - 消息列表
 * @param sessionId - 会话ID
 * @param sessionTitle - 会话标题
 * @param sessionVersion - 会话版本
 * @returns saveState, saveStateWithSSECheck, clearStorage
 */
export const useChatPersistence = (
  messages: Message[],
  sessionId: string | null,
  sessionTitle: string,
  sessionVersion: number,
  isReceiving: boolean
): UseChatPersistenceReturn => {
  
  // ========================================
  // 保存函数
  // 迁移自：NewChatContainer.tsx 第931行
  // ========================================
  
  const saveState = useCallback(() => {
    try {
      const lightState: LightState = {
        messages,
        sessionId,
        sessionTitle,
        sessionVersion,
      };
      const stateStr = JSON.stringify(lightState);
      sessionStorage.setItem(STORAGE_KEY, stateStr);
    } catch (error) {
      console.error("保存状态失败:", error);
    }
  }, [messages, sessionId, sessionTitle, sessionVersion]);
  
  // ========================================
  // 带SSE检查的保存函数
  // 迁移自：NewChatContainer.tsx 第917行
  // ========================================
  
  const saveStateWithSSECheck = useCallback(() => {
    if (isReceiving) {
      // SSE正在接收，延迟保存
      setTimeout(() => {
        saveState();
      }, 500);
    } else {
      saveState();
    }
  }, [isReceiving, saveState]);
  
  // ========================================
  // 清除存储
  // ========================================
  
  const clearStorage = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error("清除存储失败:", error);
    }
  }, []);
  
  // ========================================
  // 页面可见性处理
  // 迁移自：NewChatContainer.tsx 第1079-1101行
  // ========================================
  
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === "hidden") {
        // 页面隐藏时保存
        saveState();
      }
    };
    
    document.addEventListener("visibilitychange", handleVisibilityChange);
    
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [saveState]);
  
  // ========================================
  // 返回值
  // ========================================
  
  return {
    saveState,
    saveStateWithSSECheck,
    clearStorage,
  };
};