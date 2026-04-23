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
import { loadHistoryMessages, loadLatestHistoryMessages, STORAGE_KEY } from "../../utils/chatHistory";
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
  initializeSession: (options: InitializeSessionOptions) => Promise<InitializeSessionResult>;
  
  // 标题编辑函数
  setEditingTitle: (editing: boolean) => void;
  setTitleInput: (input: string) => void;
  setLastSavedTitle: (title: string) => void;
  
  // Refs
  currentSessionIdRef: React.MutableRefObject<string | null>;
}

/**
 * initializeSession 方法的参数
 */
export interface InitializeSessionOptions {
  searchParams: URLSearchParams;
  retryCount: Record<string, number>;
  setRetryCount: (fn: (prev: Record<string, number>) => Record<string, number>) => void;
  isLoadingHistoryRef: React.MutableRefObject<boolean>;
  setIsInitialized: (v: boolean) => void;
  restoreState: () => Promise<{
    messages: Message[];
    sessionId: string | null;
    sessionTitle: string;
    sessionVersion: number;
  } | null>;
  onLoadingStart: () => void;
  onLoadingEnd: () => void;
  onRenderStart: () => void;
  onRenderEnd: () => void;
  onMessageListLoadingStart: () => void;
  onMessageListLoadingEnd: () => void;
}

/**
 * initializeSession 方法的返回值
 */
export interface InitializeSessionResult {
  loaded: boolean;
  fromCache: boolean;
  hasUrlSession: boolean;
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

  /**
   * initializeSession - 初始化会话（核心入口）
   * 迁移自：NewChatContainer.tsx loadSession useEffect (第838-1055行)
   * 
   * 处理三种互斥场景：
   * 1. URL指定会话 -> loadHistoryMessages
   * 2. 缓存恢复 -> restoreState
   * 3. 最近会话 -> loadLatestHistoryMessages
   */
  const initializeSession = useCallback(async (options: InitializeSessionOptions): Promise<InitializeSessionResult> => {
    const {
      searchParams,
      retryCount,
      setRetryCount,
      isLoadingHistoryRef,
      setIsInitialized,
      restoreState,
      onLoadingStart,
      onLoadingEnd,
      onRenderStart,
      onRenderEnd,
      onMessageListLoadingStart,
      onMessageListLoadingEnd,
    } = options;

    const urlSessionId = searchParams.get("session_id");

    // 检测是否是强制刷新（Ctrl+F5或Cmd+Shift+R）
    const navigationEntry = performance.getEntriesByType("navigation")?.[0] as PerformanceNavigationTiming | undefined;
    const isReload = navigationEntry?.type === "reload";
    
    if (isReload) {
      console.log("🔄 检测到刷新操作，清除sessionStorage缓存");
      sessionStorage.removeItem(STORAGE_KEY);
    }

    // 场景1: URL指定会话
    if (urlSessionId) {
      const retryKey = `session-load-${urlSessionId}`;
      const currentRetry = retryCount[retryKey] || 0;

      // 如果正在加载中，跳过此次调用
      if (isLoadingHistoryRef.current) {
        console.log("⏭️ 正在加载中，跳过重复调用");
        onLoadingEnd();
        return { loaded: false, fromCache: false, hasUrlSession: true };
      }

      isLoadingHistoryRef.current = true;
      onLoadingStart();
      onRenderStart();

      try {
        const result = await loadHistoryMessages(urlSessionId);
        if (result) {
          setSessionId(result.sessionId);
          currentSessionIdRef.current = result.sessionId;
          setMessages(result.messages);
          setSessionTitle(result.title);
          if (result.version !== undefined) {
            setSessionVersion(result.version);
          }
          if (result.title_locked !== undefined) {
            setTitleLocked(result.title_locked);
          }
          setLastSavedTitle(result.title || "新会话");
          
          onLoadingEnd();
          onRenderEnd();
          onMessageListLoadingEnd();
          setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));

          console.log("🔵 从URL加载会话:", urlSessionId, "标题:", result.title, "版本:", result.version);
          isLoadingHistoryRef.current = false;
          return { loaded: true, fromCache: false, hasUrlSession: true };
        } else {
          // URL会话没有消息，清理状态
          console.warn("🔴 URL会话没有消息，清理状态并跳过加载:", urlSessionId);
          setSessionId(null);
          currentSessionIdRef.current = null;
          setMessages([]);
          setSessionTitle("新会话");
          setSessionVersion(1);
          setTitleLocked(false);
          setLastSavedTitle("新会话");
          
          onLoadingEnd();
          onRenderEnd();
          isLoadingHistoryRef.current = false;
          return { loaded: false, fromCache: false, hasUrlSession: true };
        }
      } catch (error) {
        console.warn("加载URL会话失败:", error);
        onRenderEnd();
        isLoadingHistoryRef.current = false;

        // 重试机制 - 最多3次
        if (currentRetry < 3) {
          const newRetry = currentRetry + 1;
          setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));

          // 延迟1秒后重试
          await new Promise(resolve => setTimeout(resolve, 1000));
          return initializeSession(options); // 递归重试
        } else {
          // 超过重试次数
          onLoadingEnd();
          setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
          return { loaded: false, fromCache: false, hasUrlSession: true };
        }
      }
    }

    // 场景2: 缓存恢复
    if (!urlSessionId) {
      const restored = await restoreState();
      if (restored) {
        console.log("🟢 从缓存恢复会话状态");
        setSessionId(restored.sessionId);
        currentSessionIdRef.current = restored.sessionId;
        setMessages(restored.messages);
        setSessionTitle(restored.sessionTitle);
        setSessionVersion(restored.sessionVersion);
        setLastSavedTitle(restored.sessionTitle);
        
        onLoadingEnd();
        isLoadingHistoryRef.current = false;
        return { loaded: true, fromCache: true, hasUrlSession: false };
      }
    }

    // 场景3: 加载最近会话
    if (urlSessionId) {
      // 有URL参数但不加载最近会话
      onLoadingEnd();
      return { loaded: false, fromCache: false, hasUrlSession: true };
    }

    // 检查是否正在加载
    if (isLoadingHistoryRef.current) {
      console.log("⏭️ 正在加载中，跳过重复调用");
      onLoadingEnd();
      setIsInitialized(true);
      return { loaded: false, fromCache: false, hasUrlSession: false };
    }

    isLoadingHistoryRef.current = true;
    onLoadingStart();
    onRenderStart();

    try {
      const result = await loadLatestHistoryMessages();
      if (result) {
        setSessionId(result.sessionId);
        currentSessionIdRef.current = result.sessionId;
        setSessionTitle(result.title);
        if (result.version !== undefined) {
          setSessionVersion(result.version);
        }
        if (result.title_locked !== undefined) {
          setTitleLocked(result.title_locked);
        }
        setLastSavedTitle(result.title);
        
        setMessages(result.messages);
        
        onLoadingEnd();
        onRenderEnd();
        onMessageListLoadingEnd();
        
        console.log("🟡 加载最近会话:", result.sessionId, "标题:", result.title, "版本:", result.version);
      } else {
        console.log("🟡 没有找到任何会话，显示新会话界面");
        setSessionTitle("新会话");
        setMessages([]);
        setSessionId(null);
        setLastSavedTitle("新会话");
        onLoadingEnd();
        onRenderEnd();
      }

      onLoadingEnd();
      isLoadingHistoryRef.current = false;
      setIsInitialized(true);
      return { loaded: true, fromCache: false, hasUrlSession: false };
    } catch (error) {
      console.warn("加载最近会话失败:", error);
      onLoadingEnd();
      onRenderEnd();
      isLoadingHistoryRef.current = false;
      setIsInitialized(true);
      return { loaded: false, fromCache: false, hasUrlSession: false };
    }
  }, [
    setSessionId,
    setMessages,
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
    } catch (error: unknown) {
      const err = error as { message?: string };
      if (retry < maxRetries) {
        const newRetry = retry + 1;
        showNewSessionRetryWarning(newRetry, maxRetries);
        // 延迟1秒后重试
        await new Promise(resolve => setTimeout(resolve, 1000));
        return handleNewSessionInternal(newRetry);
      }
      const errMsg = err?.message || "未知错误";
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
    } catch (error: unknown) {
      const err = error as { message?: string; response?: { status?: number } };
      const errMsg = err?.message || "更新标题失败";
      if (err?.response?.status === 409) {
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
    initializeSession,
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