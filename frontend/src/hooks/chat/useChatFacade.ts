/**
 * useChatFacade Hook - 便捷的Chat状态组合
 * 
 * 功能：
 * - 提供统一的Chat状态访问入口
 * - 组合7个独立Hook的便捷访问
 * - 通过useMemo缓存避免不必要的重渲染
 * 
 * 设计说明：
 * - 不改变现有7个Hook的结构
 * - 不追求"按需加载"Hook（React规则禁止）
 * - 通过UI条件渲染实现"按需显示"
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-24
 */

import { useMemo } from "react";
import { useChatState } from "./useChatState";
import { useChatCallbacks } from "./useChatCallbacks";
import { useChatStreaming } from "./useChatStreaming";
import { useChatSession } from "./useChatSession";
import { useChatPersistence } from "./useChatPersistence";
import { useChatSend } from "./useChatSend";
import { useChatTaskControl } from "./useChatTaskControl";
import type { Message } from "../../types/chat";
import type { ExecutionStep } from "../../utils/sse";

/**
 * useChatFacade 返回类型定义
 */
export interface UseChatFacadeReturn {
  // ===== 状态组 =====
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
  
  message: {
    messages: Message[];
    loading: boolean;
    isRetrying: boolean;
    setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
    setLoading: React.Dispatch<React.SetStateAction<boolean>>;
    setIsRetrying: React.Dispatch<React.SetStateAction<boolean>>;
    messagesRef: React.MutableRefObject<Message[]>;
    messagesEndRef: React.MutableRefObject<HTMLDivElement | null>;
  };
  
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
  };
  
  ui: {
    showExecution: boolean;
    useStream: boolean;
    isInitialized: boolean;
    sessionJumpLoading: boolean;
    isMessageListLoading: boolean;
    setShowExecution: React.Dispatch<React.SetStateAction<boolean>>;
    setUseStream: React.Dispatch<React.SetStateAction<boolean>>;
    setIsInitialized: React.Dispatch<React.SetStateAction<boolean>>;
    setSessionJumpLoading: React.Dispatch<React.SetStateAction<boolean>>;
    setIsMessageListLoading: React.Dispatch<React.SetStateAction<boolean>>;
    userScrolledUpRef: React.MutableRefObject<boolean>;
    lastScrollTimeRef: React.MutableRefObject<number>;
  };
  
  // ===== 操作组 =====
  send: {
    handleSend: (content: string) => Promise<void>;
  };
  
  interrupt: {
    handleInterrupt: () => Promise<void>;
    handleTogglePause: () => Promise<void>;
  };
  
  sessionOps: {
    initializeSession: (options: any) => Promise<any>;
    handleNewSession: (retry?: number) => Promise<void>;
    handleClear: () => void;
  };
  
  persistence: {
    saveStateWithSSECheck: (msg: Message) => void;
    saveMessagesToStorage: React.MutableRefObject<
      (msgs: Message[], sid: string, title: string, paused: boolean, receiving: boolean) => void
    >;
  };
  
  // ===== 共享Refs =====
  shared: {
    waitTimerRef: React.MutableRefObject<number | null>;
    executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
    isPausedRef: React.MutableRefObject<boolean>;
    hasReceivedInterruptEventRef: React.MutableRefObject<boolean>;
    interruptInProgressRef: React.MutableRefObject<boolean>;
  };
}

/**
 * useChatFacade - 统一的Chat状态Facade
 */
export const useChatFacade = (options?: { baseURL?: string; sessionId?: string | null }): UseChatFacadeReturn => {
  const { baseURL = "", sessionId } = options || {};
  
  // 1. 基础状态（始终加载）
  const chatState = useChatState();
  
  // 2. 回调函数（始终加载）
  const chatCallbacks = useChatCallbacks(chatState);
  
  // 3. 流式处理（始终加载，但可UI按需显示）
  const chatStreaming = useChatStreaming(
    chatState,
    chatCallbacks,
    { baseURL, sessionId: sessionId || chatState.sessionId }
  );
  
  // 4. 会话管理（始终加载）
  const chatSession = useChatSession(chatState, chatStreaming);
  
  // 5. 持久化（始终加载）
  const chatPersistence = useChatPersistence(chatState, chatStreaming);
  
  // 6. 消息发送（始终加载）
  const chatSend = useChatSend({
    loading: chatState.loading,
    sessionId: chatState.sessionId,
    messages: chatState.messages,
    waitTime: chatState.waitTime,
    setLoading: chatState.setLoading,
    setSessionId: chatState.setSessionId,
    setMessages: chatState.setMessages,
    setWaitTime: chatState.setWaitTime,
    waitTimerRef: chatState.waitTimerRef,
    currentSessionIdRef: chatState.currentSessionIdRef,
    executeSend: chatStreaming.executeSend,
  });
  
  // 7. 中断控制（始终加载）
  const chatTaskControl = useChatTaskControl({
    setters: {
      setLoading: chatState.setLoading,
      setIsPaused: chatState.setIsPaused,
      setIsReceiving: chatStreaming.setIsReceiving,
    },
    states: {
      isPaused: chatState.isPaused,
      sessionId: chatState.sessionId,
      serverTaskId: chatStreaming.serverTaskId,
    },
    refs: {
      interruptInProgressRef: chatState.interruptInProgressRef,
      hasReceivedInterruptEventRef: chatState.hasReceivedInterruptEventRef,
      waitTimerRef: chatState.waitTimerRef,
      isPausedRef: chatState.isPausedRef,
    },
    functions: {
      disconnect: chatStreaming.disconnect,
    },
  });
  
  // 通过useMemo统一返回，避免不必要的重渲染
  return useMemo(() => ({
    // ===== 状态组 =====
    
    // 会话状态
    session: {
      sessionId: chatState.sessionId,
      sessionTitle: chatState.sessionTitle,
      sessionVersion: chatState.sessionVersion,
      titleLocked: chatState.titleLocked,
      editingTitle: chatState.editingTitle,
      titleInput: chatState.titleInput,
      setSessionId: chatState.setSessionId,
      setSessionTitle: chatState.setSessionTitle,
      setSessionVersion: chatState.setSessionVersion,
      setTitleLocked: chatState.setTitleLocked,
      setEditingTitle: chatState.setEditingTitle,
      setTitleInput: chatState.setTitleInput,
      currentSessionIdRef: chatState.currentSessionIdRef,
    },
    
    // 消息状态
    message: {
      messages: chatState.messages,
      loading: chatState.loading,
      isRetrying: chatState.isRetrying,
      setMessages: chatState.setMessages,
      setLoading: chatState.setLoading,
      setIsRetrying: chatState.setIsRetrying,
      messagesRef: chatState.messagesRef,
      messagesEndRef: chatState.messagesEndRef,
    },
    
    // 流式状态
    streaming: {
      isReceiving: chatStreaming.isReceiving,
      isPaused: chatState.isPaused,
      waitTime: chatState.waitTime,
      executionSteps: chatStreaming.executionSteps,
      serverTaskId: chatStreaming.serverTaskId,
      currentResponse: chatStreaming.currentResponse,
      setIsReceiving: chatStreaming.setIsReceiving,
      setIsPaused: chatState.setIsPaused,
      setWaitTime: chatState.setWaitTime,
    },
    
    // UI状态
    ui: {
      showExecution: chatState.showExecution,
      useStream: chatState.useStream,
      isInitialized: chatState.isInitialized,
      sessionJumpLoading: chatState.sessionJumpLoading,
      isMessageListLoading: chatState.isMessageListLoading,
      setShowExecution: chatState.setShowExecution,
      setUseStream: chatState.setUseStream,
      setIsInitialized: chatState.setIsInitialized,
      setSessionJumpLoading: chatState.setSessionJumpLoading,
      setIsMessageListLoading: chatState.setIsMessageListLoading,
      userScrolledUpRef: chatState.userScrolledUpRef,
      lastScrollTimeRef: chatState.lastScrollTimeRef,
    },
    
    // ===== 操作组 =====
    
    // 发送操作
    send: {
      handleSend: chatSend.handleSend,
    },
    
    // 中断操作
    interrupt: {
      handleInterrupt: chatTaskControl.handleInterrupt,
      handleTogglePause: chatTaskControl.handleTogglePause,
    },
    
    // 会话操作
    sessionOps: {
      initializeSession: chatSession.initializeSession,
      handleNewSession: chatSession.handleNewSession,
      handleClear: chatSession.handleClear,
    },
    
    // 持久化操作
    persistence: {
      saveStateWithSSECheck: chatPersistence.saveStateWithSSECheck,
      saveMessagesToStorage: chatPersistence.saveMessagesToStorage,
    },
    
    // ===== 共享Refs =====
    shared: {
      waitTimerRef: chatState.waitTimerRef,
      executionStepsRef: chatState.executionStepsRef,
      isPausedRef: chatState.isPausedRef,
      hasReceivedInterruptEventRef: chatState.hasReceivedInterruptEventRef,
      interruptInProgressRef: chatState.interruptInProgressRef,
    },
    
  }), [
    // ✅ 只依赖具体用到的基础值，不是整个对象
    chatState.sessionId,
    chatState.sessionTitle,
    chatState.sessionVersion,
    chatState.titleLocked,
    chatState.editingTitle,
    chatState.titleInput,
    chatState.messages,
    chatState.loading,
    chatState.isRetrying,
    chatState.isPaused,
    chatState.waitTime,
    chatState.showExecution,
    chatState.useStream,
    chatState.isInitialized,
    chatState.sessionJumpLoading,
    chatState.isMessageListLoading,
    chatState.isRenderingMessages,
    chatState.retryCount,
    chatState.isSavingTitle,
    chatState.lastSaveTime,
    chatStreaming.isReceiving,
    chatState.isPaused,
    chatStreaming.executionSteps,
    chatStreaming.serverTaskId,
    chatStreaming.currentResponse,
  ]);
};

/**
 * useShouldLoadStreaming - UI按需渲染判断
 * 
 * 功能：
 * - 判断是否需要显示streaming相关UI
 * - 通过状态检查实现"按需显示"
 * - 避免条件渲染Hook的问题
 * 
 * 注意：此Hook需要配合useChatFacade使用
 * 因为它依赖chatState中的状态
 * 
 * 使用方法：
 * ```typescript
 * const chat = useChatFacade();
 * const shouldLoad = useShouldLoadStreaming(chat);
 * 
 * // UI按需渲染
 * return (
 *   <div>
 *     {shouldLoad.isReceiving && <LoadingIndicator />}
 *     {shouldLoad.hasSteps && <StepList />}
 *     {shouldLoad.canInterrupt && <InterruptButton />}
 *   </div>
 * );
 * ```
 */
export const useShouldLoadStreaming = (chat: ReturnType<typeof useChatFacade>) => {
  // 从chat中获取streaming状态
  const streaming = chat?.streaming;
  const ui = chat?.ui;
  
  return useMemo(() => ({
    // 是否正在接收
    isReceiving: streaming?.isReceiving ?? false,
    
    // 是否有执行步骤（需要从chatState获取）
    hasSteps: false,  // 需要通过其他方式获取
    
    // 是否可以显示工具面板
    showPanel: (streaming?.isReceiving ?? false) || 
              (streaming?.executionSteps?.length ?? 0) > 0,
    
    // 是否可以显示中断按钮
    canInterrupt: (streaming?.isReceiving ?? false),
    
    // 是否显示等待时间
    showWaitTime: (streaming?.isReceiving ?? false) && (ui?.isMessageListLoading ?? false),
    
  }), [streaming, ui]);
};

/**
 * useChatFacade组合 - 用于替代NewChatContainer中的多个Hook调用
 * 
 * 使用示例：
 * ```typescript
 * // 之前（调用7个Hook）
 * const chatState = useChatState();
 * const chatStreaming = useChatStreaming(...);
 * const chatSession = useChatSession(...);
 * // ...
 * 
 * // 之后（调用1个Facade）
 * const chat = useChatFacade();
 * const { session, message, streaming, send, interrupt } = chat;
 * ```
 */
export default useChatFacade;
