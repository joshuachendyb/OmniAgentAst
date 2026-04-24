/**
 * useChatGroups Hook - 统一状态分组管理
 * 
 * 功能：
 * - 包装现有的7个独立Hook
 * - 提供按需加载的初始化接口
 * - 保持与现有代码的兼容性
 * - 支持渐进式迁移
 * 
 * 设计说明（简化渐进方案）：
 * - 不改变现有Hook结构，只添加统一入口
 * - 通过initialize方法实现按需加载
 * - 保持与useChatState返回相同的接口
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-24
 */

import { useState, useRef, useEffect, useCallback } from "react";
import type { Message } from "../../types/chat";
import type { ExecutionStep } from "../../utils/sse";

// 导入现有Hook（保持兼容）
import { useChatState } from "./useChatState";
import { useChatCallbacks } from "./useChatCallbacks";
import { useChatStreaming } from "./useChatStreaming";
import { useChatSession } from "./useChatSession";
import { useChatPersistence } from "./useChatPersistence";
import { useChatSend } from "./useChatSend";
import { useChatTaskControl } from "./useChatTaskControl";

// 导入独立Hooks
import { useLoadingMessage } from "../useLoadingMessage";
import { useBeforeUnload } from "../useBeforeUnload";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * ChatGroups配置选项
 */
export interface ChatGroupsOptions {
  /** 是否立即加载所有组（默认true，用于首屏） */
  immediate?: boolean;
  /** 延迟加载流式组（按需） */
  lazyStreaming?: boolean;
  /** 延迟加载中断组（按需） */
  lazyInterrupt?: boolean;
  /** API配置 */
  apiBaseURL?: string;
}

/**
 * ChatGroups返回的5个组
 */
export interface ChatGroups {
  // 组1：会话状态（立即加载）
  session: {
    sessionId: string | null;
    sessionTitle: string;
    sessionVersion: number;
    titleLocked: boolean;
    editingTitle: boolean;
    titleInput: string;
    setSessionId: React.Dispatch<React.SetStateAction<string | null>>;
    setSessionTitle: React.Dispatch<React.SetStateAction<string>>;
    setSessionVersion: React.Dispatch<React.SetStateAction<number>>;
    setTitleLocked: React.Dispatch<React.SetStateAction<boolean>>;
    setEditingTitle: React.Dispatch<React.SetStateAction<boolean>>;
    setTitleInput: React.Dispatch<React.SetStateAction<string>>;
    currentSessionIdRef: React.MutableRefObject<string | null>;
  };
  
  // 组2：消息状态（立即加载）
  message: {
    messages: Message[];
    loading: boolean;
    isRetrying: boolean;
    setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
    setLoading: React.Dispatch<React.SetStateAction<boolean>>;
    setIsRetrying: React.Dispatch<React.SetStateAction<boolean>>;
    messagesRef: React.MutableRefObject<Message[]>;
    messagesEndRef: React.MutableRefObject<HTMLDivElement | null>;
    messagesCountRef: React.MutableRefObject<number>;
    replyUserMessageIdRef: React.MutableRefObject<number | null>;
  };
  
  // 组3：流式状态（按需）
  streaming: {
    isReceiving: boolean;
    isPaused: boolean;
    waitTime: number;
    executionSteps: ExecutionStep[];
    serverTaskId: string | null;
    currentResponse: string;
    setIsReceiving: (v: boolean) => void;
    setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;
    setWaitTime: React.Dispatch<React.SetStateAction<number>>;
    sendMessage: (content: string, sessionId?: string) => Promise<void>;
    disconnect: (stopServer?: boolean, force?: boolean, callback?: () => void) => void;
    clearSteps: () => void;
    executeSend: (userMessage: Message) => Promise<void>;
  } | null;
  
  // 组4：UI状态（立即加载）
  ui: {
    showExecution: boolean;
    useStream: boolean;
    isInitialized: boolean;
    sessionJumpLoading: boolean;
    isMessageListLoading: boolean;
    isRenderingMessages: boolean;
    retryCount: Record<string, number>;
    setShowExecution: React.Dispatch<React.SetStateAction<boolean>>;
    setUseStream: React.Dispatch<React.SetStateAction<boolean>>;
    setIsInitialized: React.Dispatch<React.SetStateAction<boolean>>;
    setSessionJumpLoading: React.Dispatch<React.SetStateAction<boolean>>;
    setIsMessageListLoading: React.Dispatch<React.SetStateAction<boolean>>;
    setIsRenderingMessages: React.Dispatch<React.SetStateAction<boolean>>;
    setRetryCount: React.Dispatch<React.SetStateAction<Record<string, number>>>;
    userScrolledUpRef: React.MutableRefObject<boolean>;
    lastScrollTimeRef: React.MutableRefObject<number>;
    isLoadingHistoryRef: React.MutableRefObject<boolean>;
  };
  
  // 组5：中断控制（按需）
  interrupt: {
    handleInterrupt: () => Promise<void>;
    handleTogglePause: () => Promise<void>;
  } | null;
  
  // 共享Refs（多个组需要）
  shared: {
    waitTimerRef: React.MutableRefObject<number | null>;
    executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
    isPausedRef: React.MutableRefObject<boolean>;
    hasReceivedInterruptEventRef: React.MutableRefObject<boolean>;
    interruptInProgressRef: React.MutableRefObject<boolean>;
  };
  
  // loading管理
  loading: {
    show: () => void;
    hide: () => void;
  };
  
  // beforeunload管理
  beforeUnload: {
    shouldSave: boolean;
    saveData: () => void;
  };
  
  // 会话管理
  session: {
    initializeSession: (options: {
      searchParams: URLSearchParams;
      retryCount: Record<string, number>;
      setRetryCount: React.Dispatch<React.SetStateAction<Record<string, number>>>;
      isLoadingHistoryRef: React.MutableRefObject<boolean>;
      setIsInitialized: React.Dispatch<React.SetStateAction<boolean>>;
      restoreState: (sessionId: string) => Promise<void>;
      onLoadingStart: () => void;
      onLoadingEnd: () => void;
      onRenderStart: () => void;
      onRenderEnd: () => void;
      onMessageListLoadingStart: () => void;
      onMessageListLoadingEnd: () => void;
    }) => void;
    handleNewSession: (retryCount: number) => void;
    handleClear: () => void;
  };
  
  // 消息发送
  send: {
    handleSend: (messageContent: string) => Promise<void>;
  };
}

/**
 * ChatGroups Hook - 统一状态分组管理
 * 
 * 使用方法：
 * ```typescript
 * const chat = useChatGroups({ immediate: true });
 * const { session, message, streaming, ui, interrupt } = chat;
 * ```
 */
export const useChatGroups = (options: ChatGroupsOptions = {}): ChatGroups => {
  const {
    immediate = true,
    lazyStreaming = false,
    lazyInterrupt = false,
    apiBaseURL = "",
  } = options;

  // ================================================================
  // 组1：会话状态（立即加载）
  // ================================================================
  const chatState = useChatState();
  const {
    sessionId, setSessionId,
    sessionTitle, setSessionTitle,
    sessionVersion, setSessionVersion,
    titleLocked, setTitleLocked,
    editingTitle, setEditingTitle,
    titleInput, setTitleInput,
    currentSessionIdRef,
  } = chatState;

  // ================================================================
  // 组2：消息状态（立即加载）
  // ================================================================
  const {
    messages, setMessages,
    loading, setLoading,
    isRetrying, setIsRetrying,
    messagesRef,
    messagesEndRef,
    messagesCountRef,
    replyUserMessageIdRef,
  } = chatState;

  // ================================================================
  // 组3：流式状态（按需）
  // ================================================================
  const [streamingLoaded, setStreamingLoaded] = useState(!lazyStreaming);
  
  const streamingGroup: ChatGroups["streaming"] = streamingLoaded
    ? (() => {
        const callbacks = useChatCallbacks(chatState);
        const streaming = useChatStreaming(
          chatState,
          callbacks,
          { baseURL: apiBaseURL, sessionId }
        );
        return {
          isReceiving: streaming.isReceiving,
          isPaused: chatState.isPaused,
          waitTime: chatState.waitTime,
          executionSteps: streaming.executionSteps,
          serverTaskId: streaming.serverTaskId,
          currentResponse: streaming.currentResponse,
          setIsReceiving: streaming.setIsReceiving,
          setIsPaused: chatState.setIsPaused,
          setWaitTime: chatState.setWaitTime,
          sendMessage: streaming.sendMessage,
          disconnect: streaming.disconnect,
          clearSteps: streaming.clearSteps,
          executeSend: streaming.executeSend,
        };
      })()
    : null;

  // ================================================================
  // 组4：UI状态（立即加载）
  // ================================================================
  const {
    showExecution, setShowExecution,
    useStream, setUseStream,
    isInitialized, setIsInitialized,
    sessionJumpLoading, setSessionJumpLoading,
    isMessageListLoading, setIsMessageListLoading,
    isRenderingMessages, setIsRenderingMessages,
    retryCount, setRetryCount,
    userScrolledUpRef,
    lastScrollTimeRef,
    isLoadingHistoryRef,
  } = chatState;

  // ================================================================
  // 组5：中断控制（按需）
  // ================================================================
  const [interruptLoaded, setInterruptLoaded] = useState(!lazyInterrupt);
  
  const interruptGroup: ChatGroups["interrupt"] = interruptLoaded && streamingLoaded
    ? (() => {
        const taskControl = useChatTaskControl({
          setters: {
            setLoading,
            setIsPaused: chatState.setIsPaused,
            setIsReceiving: streamingGroup?.setIsReceiving ?? (() => {}),
          },
          states: {
            isPaused: chatState.isPaused,
            sessionId: sessionId ?? null,
            serverTaskId: streamingGroup?.serverTaskId ?? null,
          },
          refs: {
            chatState.hasReceivedInterruptEventRef,
            chatState.interruptInProgressRef,
            chatState.waitTimerRef,
            chatState.isPausedRef,
          },
          functions: {
            disconnect: streamingGroup?.disconnect ?? (() => {}),
          },
        });
        return {
          handleInterrupt: taskControl.handleInterrupt,
          handleTogglePause: taskControl.handleTogglePause,
        };
      })()
    : null;

  // ================================================================
  // 会话管理
  // ================================================================
  const chatSession = useChatSession(chatState, streamingGroup ? {
    isReceiving: streamingGroup.isReceiving,
    executionSteps: streamingGroup.executionSteps,
    setIsReceiving: streamingGroup.setIsReceiving,
    clearSteps: streamingGroup.clearSteps,
  } : {
    isReceiving: false,
    executionSteps: [],
    setIsReceiving: () => {},
    clearSteps: () => {},
  });
  
  const chatPersistence = useChatPersistence(chatState, streamingGroup ? {
    isReceiving: streamingGroup.isReceiving,
    setIsReceiving: streamingGroup.setIsReceiving,
    executionSteps: streamingGroup.executionSteps,
    messages,
    sessionTitle,
  } : {
    isReceiving: false,
    setIsReceiving: () => {},
    executionSteps: [],
    messages: [],
    sessionTitle: "",
  });

  // ================================================================
  // 消息发送
  // ================================================================
  const chatSend = useChatSend({
    loading,
    sessionId,
    messages,
    waitTime,
    setLoading,
    setSessionId,
    setMessages,
    setWaitTime,
    chatState.waitTimerRef,
    currentSessionIdRef,
    executeSend: streamingGroup?.executeSend ?? (() => Promise.resolve()),
  });

  // ================================================================
  // loading管理 Hook
  // ================================================================
  const { show: showLoading, hide: hideLoading } = useLoadingMessage({ duration: 0 });

  // ================================================================
  // beforeunload管理 Hook（简化版，实际需要时才加载）
  // ================================================================
  const handleSaveBeforeUnload = useCallback(() => {
    if (!streamingGroup?.isReceiving || !sessionId) return;
    // 保存逻辑...
  }, [streamingGroup?.isReceiving, sessionId]);
  
  const beforeUnload = useBeforeUnload({
    shouldSave: !!(streamingGroup?.isReceiving && sessionId),
    saveData: handleSaveBeforeUnload,
    showDialog: true,
    dialogMessage: "正在接收消息，确定要离开吗？",
  });

  // ================================================================
  // 按需加载初始化
  // ================================================================
  const initializeStreaming = useCallback(() => {
    if (!streamingLoaded) {
      setStreamingLoaded(true);
    }
  }, [streamingLoaded]);

  const initializeInterrupt = useCallback(() => {
    if (!interruptLoaded) {
      setInterruptLoaded(true);
    }
  }, [interruptLoaded]);

  // ================================================================
  // 返回统一的5个组
  // ================================================================
  return {
    session: {
      sessionId,
      sessionTitle,
      sessionVersion,
      titleLocked,
      editingTitle,
      titleInput,
      setSessionId,
      setSessionTitle,
      setSessionVersion,
      setTitleLocked,
      setEditingTitle,
      setTitleInput,
      currentSessionIdRef,
    },
    message: {
      messages,
      loading,
      isRetrying,
      setMessages,
      setLoading,
      setIsRetrying,
      messagesRef,
      messagesEndRef,
      messagesCountRef,
      replyUserMessageIdRef,
    },
    streaming: streamingGroup,
    ui: {
      showExecution,
      useStream,
      isInitialized,
      sessionJumpLoading,
      isMessageListLoading,
      isRenderingMessages,
      retryCount,
      setShowExecution,
      setUseStream,
      setIsInitialized,
      setSessionJumpLoading,
      setIsMessageListLoading,
      setIsRenderingMessages,
      setRetryCount,
      userScrolledUpRef,
      lastScrollTimeRef,
      isLoadingHistoryRef,
    },
    interrupt: interruptGroup,
    shared: {
      waitTimerRef: chatState.waitTimerRef,
      executionStepsRef: chatState.executionStepsRef,
      isPausedRef: chatState.isPausedRef,
      hasReceivedInterruptEventRef: chatState.hasReceivedInterruptEventRef,
      interruptInProgressRef: chatState.interruptInProgressRef,
    },
    loading: {
      show: showLoading,
      hide: hideLoading,
    },
    beforeUnload: {
      shouldSave: !!(streamingGroup?.isReceiving && sessionId),
      saveData: handleSaveBeforeUnload,
    },
    session: {
      initializeSession: chatSession.initializeSession,
      handleNewSession: chatSession.handleNewSession,
      handleClear: chatSession.handleClear,
    },
    send: {
      handleSend: chatSend.handleSend,
    },
  };
};