/**
 * useChatSession Hook - 会话生命周期管理
 *
 * 功能：
 * - 会话状态管理（sessionId, sessionTitle, sessionVersion, titleLocked等）
 * - 会话函数（loadSession, handleNewSession, handleClear, updateSessionTitle等）
 * - 会话标题编辑和版本控制
 *
 * 设计说明：
 * - 集中管理所有会话相关状态和逻辑
 * - 处理会话加载、创建、清空、标题更新等操作
 * - 处理版本冲突和错误处理
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-21
 */

import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import type { Message } from "../../types/chat";
import type { UseChatStateReturn } from "./useChatState";
import type { UseChatStreamingReturn } from "./useChatStreaming";
import { sessionApi } from "../../services/api";
import { loadHistoryMessages, STORAGE_KEY } from "../../utils/chatHistory";
import { 
  showNewSessionSuccess, 
  showNewSessionRetryWarning, 
  showNewSessionError,
  showLoadErrorWithKey,
  showSaveError
} from "../../utils/chatMessages";


// ============================================================================
// 类型定义
// ============================================================================

/**
 * useChatSession Hook返回值
 */
export interface UseChatSessionReturn {
  // 会话状态
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  titleLocked: boolean;
  editingTitle: boolean;
  titleInput: string;
  lastSavedTitle: string;
  
  // 会话函数
  loadSession: (sessionId: string) => Promise<Message[]>;
  handleNewSession: (retry?: number) => Promise<void>;
  handleNewSessionInternal: (retry?: number) => Promise<void>;
  handleClear: () => void;
  updateSessionTitle: (newTitle: string) => Promise<void>;
  
  // 标题编辑函数
  setEditingTitle: (editing: boolean) => void;
  setTitleInput: (input: string) => void;
  setLastSavedTitle: (title: string) => void;
  
  // Refs
  currentSessionIdRef: React.MutableRefObject<string | null>;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatSession - 会话生命周期管理
 * 
 * 迁移自：NewChatContainer.tsx 中的会话相关逻辑
 * - 会话状态管理
 * - 会话加载、创建、清空
 * - 标题编辑和版本控制
 * - 错误处理和重试逻辑
 * 
 * @param state - useChatState返回的状态对象
 * @returns 会话相关状态和函数
 */
export const useChatSession = (
  state: UseChatStateReturn,
  streaming?: UseChatStreamingReturn
): UseChatSessionReturn => {
  const [searchParams] = useSearchParams();
  
  // 从state中解构需要的状态和setter
  const {
    sessionId, setSessionId,
    sessionTitle, setSessionTitle,
    sessionVersion, setSessionVersion,
    titleLocked, setTitleLocked,
    editingTitle, setEditingTitle,
    titleInput, setTitleInput,
    lastSavedTitle, setLastSavedTitle,
    messages, setMessages,
    currentSessionIdRef,
  } = state;
  
  // ========================================
  // 会话加载函数
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
        setSessionTitle(result.title || "新会话");
        setSessionVersion(result.version || 1);
        setTitleLocked(result.title_locked || false);
        setLastSavedTitle(result.title || "新会话");
        return result.messages || [];
      }
      return [];
    } catch (error) {
      console.error("加载会话失败:", error);
      showLoadErrorWithKey("加载失败", sid);
      return [];
    }
  }, [
    setSessionId,
    setSessionTitle,
    setSessionVersion,
    setTitleLocked,
    setLastSavedTitle,
    currentSessionIdRef,
  ]);
  
  // ========================================
  // 会话操作函数
  // ========================================
  
  /**
   * generateNewSessionTitle - 生成智能会话标题
   * 迁移自：NewChatContainer.tsx 第1351行
   */
  const generateNewSessionTitle = (): string => {
    const now = new Date();
    const hours = now.getHours();
    let timeOfDay = "";

    if (hours >= 5 && hours < 8) timeOfDay = "清晨";
    else if (hours >= 8 && hours < 12) timeOfDay = "上午";
    else if (hours >= 12 && hours < 14) timeOfDay = "午间";
    else if (hours >= 14 && hours < 18) timeOfDay = "下午";
    else if (hours >= 18 && hours < 21) timeOfDay = "晚间";
    else if (hours >= 21 && hours < 24) timeOfDay = "深夜";
    else timeOfDay = "深夜";

    const dateStr = `${now.getMonth() + 1}月${now.getDate()}日`;
    return `${dateStr} ${timeOfDay}会话 ${hours}:${now.getMinutes().toString().padStart(2, "0")}`;
  };

  /**
   * handleNewSessionInternal - 新建会话内部实现，支持重试机制
   * 迁移自：NewChatContainer.tsx handleNewSessionInternal
   */
  const handleNewSessionInternal = useCallback(async (retry: number = 0): Promise<void> => {
    const maxRetries = 3;

    try {
      // 生成智能标题
      const newTitle = generateNewSessionTitle();
      const response = await sessionApi.createSession(newTitle);
      const newSessionId = response.session_id;
      
      setSessionId(newSessionId);
      currentSessionIdRef.current = newSessionId;
      setSessionTitle(newTitle);
      setSessionVersion(1);
      setTitleLocked(false);
      setLastSavedTitle(newTitle);
      
      // 断开之前的SSE连接
      if (streaming?.disconnect) {
        streaming.disconnect();
      }
      if (streaming?.clearSteps) {
        streaming.clearSteps();
      }
      
      // 添加系统提示消息
      const systemMessage: Message = {
        id: (Date.now() + 1000).toString(),
        role: "system",
        content: "💡 新会话已创建！开始与AI助手对话吧。",
        timestamp: new Date(),
      };
      setMessages([systemMessage]);
      
      // 清除sessionStorage
      sessionStorage.removeItem(STORAGE_KEY);
      
      // 更新URL
      window.history.pushState({}, "", `/?session_id=${newSessionId}`);
      
      showNewSessionSuccess(newTitle);
    } catch (error: any) {
      if (retry < maxRetries) {
        const newRetry = retry + 1;
        showNewSessionRetryWarning(newRetry, maxRetries);
        // 延迟1秒后重试
        await new Promise(resolve => setTimeout(resolve, 1000));
        return handleNewSessionInternal(newRetry);
      }
      const errMsg = error?.message || "未知错误";
      showNewSessionError(errMsg);
    }
  }, [
    setSessionId,
    setSessionTitle,
    setSessionVersion,
    setTitleLocked,
    setMessages,
    setLastSavedTitle,
    currentSessionIdRef,
    streaming,
  ]);

  /**
   * handleNewSession - 新建会话入口
   */
  const handleNewSession = useCallback(async (retry: number = 0): Promise<void> => {
    return handleNewSessionInternal(retry);
  }, [handleNewSessionInternal]);
  
  /**
   * handleClear - 清空对话
   * 迁移自：NewChatContainer.tsx handleClear
   */
  const handleClear = useCallback(() => {
    console.log("[useChatSession] handleClear - 清空对话");
    
    // 断开SSE连接
    if (streaming?.disconnect) {
      streaming.disconnect();
    }
    if (streaming?.clearSteps) {
      streaming.clearSteps();
    }
    
    setSessionId(null);
    currentSessionIdRef.current = null;
    setSessionTitle("新会话");
    setSessionVersion(1);
    setTitleLocked(false);
    setMessages([]);
    setLastSavedTitle("新会话");
  }, [
    setSessionId,
    setSessionTitle,
    setSessionVersion,
    setTitleLocked,
    setMessages,
    setLastSavedTitle,
    currentSessionIdRef,
    streaming,
  ]);
  
  // ========================================
  // 标题管理函数
  // ========================================
  
  /**
   * updateSessionTitle - 更新会话标题
   * 迁移自：NewChatContainer.tsx 中的标题更新逻辑
   */
  const updateSessionTitle = useCallback(async (newTitle: string) => {
    if (!sessionId || !newTitle.trim()) {
      return;
    }
    
    try {
      const response = await sessionApi.updateSession(
        sessionId,
        newTitle.trim(),
        sessionVersion
      );
      
      setSessionTitle(newTitle.trim());
      setSessionVersion(response.version || sessionVersion);
      setLastSavedTitle(newTitle.trim());
      
      console.log("✅ 标题更新成功:", newTitle, "版本:", response.version);
    } catch (error: any) {
      const errMsg = error?.message || "更新标题失败";
      if (error?.response?.status === 409) {
        // 版本冲突，重新加载最新数据
        console.warn("⚠️ 标题版本冲突，重新加载最新数据");
        try {
          const result = await loadHistoryMessages(sessionId);
          if (result) {
            setSessionTitle(result.title || newTitle);
            setSessionVersion(result.version || sessionVersion + 1);
            setTitleLocked(result.title_locked || false);
            setLastSavedTitle(result.title || newTitle);
            
            // 提示用户重新编辑
            showSaveError("会话标题已被其他人修改，已自动更新为最新版本");
          }
        } catch (syncError) {
          console.error("同步最新数据失败:", syncError);
          showSaveError("同步最新数据失败，请刷新页面重试");
        }
      } else {
        showSaveError(errMsg);
      }
      throw error;
    }
  }, [
    sessionId,
    sessionVersion,
    setSessionTitle,
    setSessionVersion,
    setTitleLocked,
    setLastSavedTitle,
  ]);
  
  // ========================================
  // 标题编辑辅助函数
  // ========================================
  
  /**
   * startEditingTitle - 开始编辑标题
   */
  const startEditingTitle = useCallback(() => {
    setEditingTitle(true);
    setTitleInput(sessionTitle);
  }, [sessionTitle, setEditingTitle, setTitleInput]);
  
  /**
   * cancelEditingTitle - 取消编辑标题
   */
  const cancelEditingTitle = useCallback(() => {
    setEditingTitle(false);
    setTitleInput("");
  }, [setEditingTitle, setTitleInput]);
  
  /**
   * saveEditingTitle - 保存编辑的标题
   */
  const saveEditingTitle = useCallback(async () => {
    if (!titleInput.trim() || titleInput.trim() === sessionTitle) {
      setEditingTitle(false);
      setTitleInput("");
      return;
    }
    
    try {
      await updateSessionTitle(titleInput.trim());
      setEditingTitle(false);
      setTitleInput("");
    } catch (error) {
      // 错误已在updateSessionTitle中处理
      console.error("保存标题失败:", error);
    }
  }, [
    titleInput,
    sessionTitle,
    setEditingTitle,
    setTitleInput,
    updateSessionTitle,
  ]);
  
  // ========================================
  // 返回值
  // ========================================
  
  return {
    // 会话状态
    sessionId,
    sessionTitle,
    sessionVersion,
    titleLocked,
    editingTitle,
    titleInput,
    lastSavedTitle,
    
    // 会话函数
    loadSession,
    handleNewSession,
    handleNewSessionInternal,
    handleClear,
    updateSessionTitle,
    
    // 标题编辑函数
    setEditingTitle,
    setTitleInput,
    setLastSavedTitle,
    
    // Refs
    currentSessionIdRef,
  };
};