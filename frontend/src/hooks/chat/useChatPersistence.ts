/**
 * useChatPersistence Hook - 状态持久化与恢复
 *
 * 功能：
 * - 防抖保存逻辑（saveMessagesToStorage）
 * - 页面可见性处理（visibilitychange）
 * - 页面卸载前保存（beforeunload）
 * - 状态恢复（restoreState）
 * - 自动保存（当messages变化时）
 *
 * 设计说明：
 * - 集中管理所有持久化相关逻辑
 * - 处理sessionStorage的读写操作
 * - 处理页面可见性和卸载事件
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-21
 */

import { useEffect, useCallback, useRef } from "react";
import type { Message } from "../../types/chat";
import type { UseChatStateReturn } from "./useChatState";
import type { UseChatStreamingReturn } from "./useChatStreaming";
import { debounce, STORAGE_KEY, loadHistoryMessages } from "../../utils/chatHistory";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * 持久化状态接口
 */
interface PersistenceState {
  messages: Message[];
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  timestamp: number;
  scrollPosition: number;
  isPaused: boolean;
  isReceiving: boolean;
}

/**
 * 轻量级状态（用于大容量情况）
 */
interface LightState {
  sessionId: string | null;
  sessionTitle: string;
  timestamp: number;
  messageCount: number;
  isPaused: boolean;
  isReceiving: boolean;
}

/**
 * useChatPersistence Hook返回值
 */
export interface UseChatPersistenceReturn {
  // 保存函数
  saveState: () => void;
  saveStateWithSSECheck: () => void;
  clearStorage: () => void;
  
  // 恢复函数
  restoreState: () => Promise<{
    messages: Message[];
    sessionId: string | null;
    sessionTitle: string;
    sessionVersion: number;
    isPaused: boolean;
    isReceiving: boolean;
  } | null>;
  
  // 防抖保存函数Ref
  saveMessagesToStorage: React.MutableRefObject<
    (msgs: Message[], sid: string, title: string, paused: boolean, receiving: boolean) => void
  >;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatPersistence - 状态持久化与恢复
 * 
 * 迁移自：NewChatContainer.tsx 中的持久化逻辑
 * - saveMessagesToStorage：防抖保存到sessionStorage
 * - 页面可见性处理：visibilitychange事件
 * - 页面卸载前保存：beforeunload事件
 * - 自动保存：当messages变化时
 * - 状态恢复：从sessionStorage恢复状态
 * 
 * @param state - useChatState返回的状态对象
 * @param streaming - useChatStreaming返回的流式对象
 * @returns 持久化相关函数和Refs
 */
export const useChatPersistence = (
  state: UseChatStateReturn,
  streaming: UseChatStreamingReturn
): UseChatPersistenceReturn => {
  const {
    messages,
    sessionId,
    sessionTitle,
    sessionVersion,
    isPaused,
    messagesEndRef,
    messagesRef,
  } = state;
  
  const { isReceiving } = streaming;
  
  // ========================================
  // 防抖保存函数Ref
  // 迁移自：NewChatContainer.tsx 第139-170行
  // ========================================
  
  const saveMessagesToStorage = useRef(
    debounce((msgs: Message[], sid: string, title: string, paused: boolean, receiving: boolean) => {
      if (sid) {
        const state: PersistenceState = {
          messages: msgs,
          sessionId: sid,
          sessionTitle: title,
          sessionVersion: 1, // 默认版本
          timestamp: Date.now(),
          scrollPosition: messagesEndRef.current?.parentElement?.scrollTop || 0,
          isPaused: paused,
          isReceiving: receiving,
        };
        
        try {
          const stateStr = JSON.stringify(state);
          // 原有4MB检查保留
          if (stateStr.length > 4 * 1024 * 1024) {
            const lightState: LightState = {
              sessionId: sid,
              sessionTitle: title,
              timestamp: Date.now(),
              messageCount: msgs.length,
              isPaused: paused,
              isReceiving: receiving,
            };
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(lightState));
          } else {
            sessionStorage.setItem(STORAGE_KEY, stateStr);
          }
        } catch (e) {
          if (e instanceof DOMException && e.name === 'QuotaExceededError') {
            console.warn("⚠️ sessionStorage容量满，跳过保存");
          } else {
            console.error("保存会话状态失败:", e);
          }
        }
      }
    }, 500)  // 500ms防抖
  );
  
  // ========================================
  // 保存函数
  // ========================================
  
  /**
   * saveState - 保存当前状态到sessionStorage
   */
  const saveState = useCallback(() => {
    if (sessionId) {
      saveMessagesToStorage.current(messages, sessionId, sessionTitle, isPaused, isReceiving);
    }
  }, [sessionId, messages, sessionTitle, isPaused, isReceiving]);
  
  /**
   * saveStateWithSSECheck - 带SSE检查的保存
   * 如果正在接收SSE消息，延迟500ms保存
   */
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
  
  /**
   * clearStorage - 清除sessionStorage中的状态
   */
  const clearStorage = useCallback(() => {
    try {
      sessionStorage.removeItem(STORAGE_KEY);
    } catch (error) {
      console.error("清除存储失败:", error);
    }
  }, []);
  
  // ========================================
  // 恢复函数
  // ========================================
  
  /**
   * restoreState - 从sessionStorage恢复状态
   */
  const restoreState = useCallback(async () => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (!stored) {
        return null;
      }
      
      const data = JSON.parse(stored);
      
      // 检查是否是轻量级状态
      if (data.messageCount !== undefined) {
        // 轻量级状态，需要从服务器加载完整消息
        if (data.sessionId) {
          const result = await loadHistoryMessages(data.sessionId);
          if (result) {
            return {
              messages: result.messages || [],
              sessionId: result.sessionId,
              sessionTitle: result.sessionTitle || "新会话",
              sessionVersion: result.sessionVersion || 1,
              isPaused: data.isPaused || false,
              isReceiving: data.isReceiving || false,
            };
          }
        }
        return null;
      }
      
      // 完整状态
      return {
        messages: data.messages || [],
        sessionId: data.sessionId || null,
        sessionTitle: data.sessionTitle || "新会话",
        sessionVersion: data.sessionVersion || 1,
        isPaused: data.isPaused || false,
        isReceiving: data.isReceiving || false,
      };
    } catch (error) {
      console.error("恢复状态失败:", error);
      return null;
    }
  }, []);
  
  // ========================================
  // 副作用：页面可见性变化处理
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
  // 副作用：页面卸载前保存
  // 迁移自：NewChatContainer.tsx 第815-880行
  // ========================================
  
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      // 在页面卸载前保存状态
      saveState();
      
      // 标准做法：设置returnValue来显示确认对话框
      // 但为了更好的用户体验，我们只保存状态，不阻止用户离开
      // e.preventDefault();
      // e.returnValue = '';
    };
    
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [saveState]);
  
  // ========================================
  // 副作用：自动保存（当messages变化时）
  // ========================================
  
  useEffect(() => {
    // 使用防抖保存，避免频繁写入
    const timer = setTimeout(() => {
      saveStateWithSSECheck();
    }, 1000);
    
    return () => {
      clearTimeout(timer);
    };
  }, [messages, saveStateWithSSECheck]);
  
  // ========================================
  // 返回值
  // ========================================
  
  return {
    saveState,
    saveStateWithSSECheck,
    clearStorage,
    restoreState,
    saveMessagesToStorage,
  };
};