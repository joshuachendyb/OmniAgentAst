/**
 * 状态分组类型定义
 * 
 * 功能：按功能将状态分为5组，便于按需加载和代码分离
 * 
 * 设计说明：
 * - 渐进式迁移：不改变现有Hook结构，只创建分组类型
 * - 前瞻性设计：为后续按需加载预留接口
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-24
 */

import type { Message } from "../../types/chat";
import type { ExecutionStep } from "../../utils/sse";

// ============================================================================
// 类型定义（直接定义，不从Hook导入）
// ============================================================================

/**
 * SaveStatus - 保存状态类型
 */
export type SaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * LogFlags - 日志标记类型
 */
export interface LogFlags {
  chunkFirstDone: boolean;
  showStepsFalseDone: boolean;
  showStepsTrueDone: boolean;
}

// ============================================================================
// 会话组类型（SessionGroup）
// ============================================================================

export interface SessionGroupState {
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  titleLocked: boolean;
  editingTitle: boolean;
  titleInput: string;
  lastSavedTitle: string;
}

export interface SessionGroupRefs {
  currentSessionIdRef: React.MutableRefObject<string | null>;
}

export type SessionGroupReturn = SessionGroupState & SessionGroupRefs & {
  setSessionId: React.Dispatch<React.SetStateAction<string | null>>;
  setSessionTitle: React.Dispatch<React.SetStateAction<string>>;
  setSessionVersion: React.Dispatch<React.SetStateAction<number>>;
  setTitleLocked: React.Dispatch<React.SetStateAction<boolean>>;
  setEditingTitle: React.Dispatch<React.SetStateAction<boolean>>;
  setTitleInput: React.Dispatch<React.SetStateAction<string>>;
  setLastSavedTitle: React.Dispatch<React.SetStateAction<string>>;
};

// ============================================================================
// 消息组类型（MessageGroup）
// ============================================================================

export interface MessageGroupState {
  messages: Message[];
  loading: boolean;
  isRetrying: boolean;
}

export interface MessageGroupRefs {
  messagesRef: React.MutableRefObject<Message[]>;
  messagesEndRef: React.MutableRefObject<HTMLDivElement | null>;
  messagesCountRef: React.MutableRefObject<number>;
  replyUserMessageIdRef: React.MutableRefObject<number | null>;
}

export type MessageGroupReturn = MessageGroupState & MessageGroupRefs & {
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setIsRetrying: React.Dispatch<React.SetStateAction<boolean>>;
};

// ============================================================================
// 流式组类型（StreamingGroup）
// ============================================================================

export interface StreamingGroupState {
  isReceiving: boolean;
  isPaused: boolean;
  waitTime: number;
  executionSteps: ExecutionStep[];
  serverTaskId: string | null;
  currentResponse: string;
}

export interface StreamingGroupRefs {
  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
  streamingContentRef: React.MutableRefObject<string>;
  displayBufferRef: React.MutableRefObject<unknown[]>;
  isPausedRef: React.MutableRefObject<boolean>;
  streamingStepsRef: React.MutableRefObject<ExecutionStep[]>;
  waitTimerRef: React.MutableRefObject<number | null>;
}

export type StreamingGroupReturn = StreamingGroupState & StreamingGroupRefs & {
  setIsReceiving: (v: boolean) => void;
  setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;
  setWaitTime: React.Dispatch<React.SetStateAction<number>>;
  sendMessage: (content: string, sessionId?: string) => Promise<void>;
  disconnect: (stopServer?: boolean, force?: boolean, callback?: () => void) => void;
  clearSteps: () => void;
  executeSend: (userMessage: Message) => Promise<void>;
};

// ============================================================================
// UI组类型（UIGroup）
// ============================================================================

export interface UIGroupState {
  showExecution: boolean;
  useStream: boolean;
  isInitialized: boolean;
  saveStatus: "idle" | "saving" | "saved" | "error";
  sessionJumpLoading: boolean;
  isMessageListLoading: boolean;
  isRenderingMessages: boolean;
  retryCount: Record<string, number>;
  isSavingTitle: boolean;
  lastSaveTime: number;
}

export interface UIGroupRefs {
  userScrolledUpRef: React.MutableRefObject<boolean>;
  lastScrollTimeRef: React.MutableRefObject<number>;
  isLoadingHistoryRef: React.MutableRefObject<boolean>;
  logFlagsRef: React.MutableRefObject<{
    chunkFirstDone: boolean;
    showStepsFalseDone: boolean;
    showStepsTrueDone: boolean;
  }>;
}

export type UIGroupReturn = UIGroupState & UIGroupRefs & {
  setShowExecution: React.Dispatch<React.SetStateAction<boolean>>;
  setUseStream: React.Dispatch<React.SetStateAction<boolean>>;
  setIsInitialized: React.Dispatch<React.SetStateAction<boolean>>;
  setSaveStatus: React.Dispatch<React.SetStateAction<"idle" | "saving" | "saved" | "error">>;
  setSessionJumpLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setIsMessageListLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setIsRenderingMessages: React.Dispatch<React.SetStateAction<boolean>>;
  setRetryCount: React.Dispatch<React.SetStateAction<Record<string, number>>>;
  setIsSavingTitle: React.Dispatch<React.SetStateAction<boolean>>;
  setLastSaveTime: React.Dispatch<React.SetStateAction<number>>;
};

// ============================================================================
// 中断组类型（InterruptGroup）
// ============================================================================

export interface InterruptGroupRefs {
  hasReceivedInterruptEventRef: React.MutableRefObject<boolean>;
  interruptInProgressRef: React.MutableRefObject<boolean>;
}

export type InterruptGroupReturn = InterruptGroupRefs & {
  handleInterrupt: () => Promise<void>;
  handleTogglePause: () => Promise<void>;
};

// ============================================================================
// 按需加载配置
// ============================================================================

export interface ChatGroupLoadOptions {
  immediate?: boolean;
  lazy?: boolean;
}

export const DEFAULT_LOAD_OPTIONS: ChatGroupLoadOptions = {
  immediate: true,
  lazy: false,
};