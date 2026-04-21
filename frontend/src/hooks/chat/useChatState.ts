/**
 * useChatState Hook - 统一状态管理
 *
 * 功能：
 * - 集中管理NewChatContainer的所有状态和Refs
 * - 提供状态同步机制，确保Refs与状态一致
 * - 作为其他Hook的基础依赖
 *
 * 设计原则：
 * 1. 单一数据源：所有状态集中管理
 * 2. 状态同步：使用useEffect同步Refs和状态
 * 3. 类型安全：完整的TypeScript类型定义
 * 4. 性能优化：避免不必要的重渲染
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-21
 */

import { useState, useRef, useEffect } from "react";
import type { Message } from "../../types/chat";
import type { ExecutionStep } from "../../utils/sse";

// ============================================================================
// 类型定义
// ============================================================================

/**
 * SaveStatus - 保存状态类型
 */
type SaveStatus = "idle" | "saving" | "saved" | "error";

/**
 * LogFlags - 日志标记类型
 */
interface LogFlags {
  chunkFirstDone: boolean;
  showStepsFalseDone: boolean;
  showStepsTrueDone: boolean;
}

/**
 * useChatState Hook返回值
 */
export interface UseChatStateReturn {
  // ==================== 状态 ====================
  
  // 消息相关状态
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  loading: boolean;
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 等待时间状态
  waitTime: number;
  setWaitTime: React.Dispatch<React.SetStateAction<number>>;
  
  // 重试状态
  isRetrying: boolean;
  setIsRetrying: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 暂停状态
  isPaused: boolean;
  setIsPaused: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 会话相关状态
  sessionId: string | null;
  setSessionId: React.Dispatch<React.SetStateAction<string | null>>;
  sessionTitle: string;
  setSessionTitle: React.Dispatch<React.SetStateAction<string>>;
  sessionVersion: number;
  setSessionVersion: React.Dispatch<React.SetStateAction<number>>;
  titleLocked: boolean;
  setTitleLocked: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 标题编辑状态
  editingTitle: boolean;
  setEditingTitle: React.Dispatch<React.SetStateAction<boolean>>;
  titleInput: string;
  setTitleInput: React.Dispatch<React.SetStateAction<string>>;
  lastSavedTitle: string;
  setLastSavedTitle: React.Dispatch<React.SetStateAction<string>>;
  
  // 显示相关状态
  showExecution: boolean;
  setShowExecution: React.Dispatch<React.SetStateAction<boolean>>;
  useStream: boolean;
  setUseStream: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 初始化状态
  isInitialized: boolean;
  setIsInitialized: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 保存状态
  saveStatus: SaveStatus;
  setSaveStatus: React.Dispatch<React.SetStateAction<SaveStatus>>;
  
  // 会话跳转加载状态
  sessionJumpLoading: boolean;
  setSessionJumpLoading: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 消息列表加载状态
  isMessageListLoading: boolean;
  setIsMessageListLoading: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 重试计数
  retryCount: Record<string, number>;
  setRetryCount: React.Dispatch<React.SetStateAction<Record<string, number>>>;
  
  // 保存标题状态
  isSavingTitle: boolean;
  setIsSavingTitle: React.Dispatch<React.SetStateAction<boolean>>;
  
  // 最后保存时间
  lastSaveTime: number;
  setLastSaveTime: React.Dispatch<React.SetStateAction<number>>;
  
  // ==================== Refs ====================
  
  // 定时器Refs
  waitTimerRef: React.MutableRefObject<number | null>;
  
  // DOM Refs
  messagesEndRef: React.MutableRefObject<HTMLDivElement | null>;
  
  // 会话Refs
  currentSessionIdRef: React.MutableRefObject<string | null>;
  messagesCountRef: React.MutableRefObject<number>;
  
  // 消息Refs
  messagesRef: React.MutableRefObject<Message[]>;
  replyUserMessageIdRef: React.MutableRefObject<number | null>;
  
  // 暂停相关Refs
  displayBufferRef: React.MutableRefObject<any[]>;
  isPausedRef: React.MutableRefObject<boolean>;
  
  // SSE相关Refs
  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;
  streamingContentRef: React.MutableRefObject<string>;
  streamingStepsRef: React.MutableRefObject<ExecutionStep[]>;
  
  // 滚动相关Refs
  userScrolledUpRef: React.MutableRefObject<boolean>;
  lastScrollTimeRef: React.MutableRefObject<number>;
  
  // 加载状态Refs
  isLoadingHistoryRef: React.MutableRefObject<boolean>;
  
  // 日志标记Refs
  logFlagsRef: React.MutableRefObject<LogFlags>;
  
  // 中断相关Refs
  hasReceivedInterruptEventRef: React.MutableRefObject<boolean>;
  interruptInProgressRef: React.MutableRefObject<boolean>;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatState - 统一状态管理Hook
 * 
 * 迁移自：NewChatContainer.tsx 中的所有状态和Refs
 * 
 * 设计说明：
 * 1. 集中管理所有状态，避免状态分散
 * 2. 使用useEffect同步Refs和状态，确保一致性
 * 3. 提供完整的类型定义，提高代码可维护性
 * 
 * @returns 所有状态和Refs的集合
 */
export const useChatState = (): UseChatStateReturn => {
  // ==================== 状态定义 ====================
  
  // 消息相关状态
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  
  // 等待时间状态
  const [waitTime, setWaitTime] = useState(0);
  
  // 重试状态
  const [isRetrying, setIsRetrying] = useState(false);
  
  // 暂停状态
  const [isPaused, setIsPaused] = useState(false);
  
  // 会话相关状态
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string>("新会话");
  const [sessionVersion, setSessionVersion] = useState<number>(1);
  const [titleLocked, setTitleLocked] = useState<boolean>(false);
  
  // 标题编辑状态
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const [lastSavedTitle, setLastSavedTitle] = useState<string>("");
  
  // 显示相关状态
  const [showExecution, setShowExecution] = useState(true);
  const [useStream, setUseStream] = useState(true);
  
  // 初始化状态
  const [isInitialized, setIsInitialized] = useState(false);
  
  // 保存状态
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  
  // 会话跳转加载状态
  const [sessionJumpLoading, setSessionJumpLoading] = useState(false);
  
  // 消息列表加载状态
  const [isMessageListLoading, setIsMessageListLoading] = useState(true);
  
  // 重试计数
  const [retryCount, setRetryCount] = useState<Record<string, number>>({});
  
  // 保存标题状态
  const [isSavingTitle, setIsSavingTitle] = useState(false);
  
  // 最后保存时间
  const [lastSaveTime, setLastSaveTime] = useState<number>(0);
  
  // ==================== Refs定义 ====================
  
  // 定时器Refs
  const waitTimerRef = useRef<number | null>(null);
  
  // DOM Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  
  // 会话Refs
  const currentSessionIdRef = useRef<string | null>(null);
  const messagesCountRef = useRef<number>(0);
  
  // 消息Refs
  const messagesRef = useRef<Message[]>([]);
  const replyUserMessageIdRef = useRef<number | null>(null);
  
  // 暂停相关Refs
  const displayBufferRef = useRef<any[]>([]);
  const isPausedRef = useRef(false);
  
  // SSE相关Refs
  const executionStepsRef = useRef<ExecutionStep[]>([]);
  const streamingContentRef = useRef('');
  const streamingStepsRef = useRef<ExecutionStep[]>([]);
  
  // 滚动相关Refs
  const userScrolledUpRef = useRef(false);
  const lastScrollTimeRef = useRef(0);
  
  // 加载状态Refs
  const isLoadingHistoryRef = useRef(false);
  
  // 日志标记Refs
  const logFlagsRef = useRef<LogFlags>({
    chunkFirstDone: false,
    showStepsFalseDone: false,
    showStepsTrueDone: false,
  });
  
  // 中断相关Refs
  const hasReceivedInterruptEventRef = useRef(false);
  const interruptInProgressRef = useRef(false);
  
  // ==================== 状态同步 ====================
  
  // 同步messages到messagesRef
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);
  
  // 同步sessionId到currentSessionIdRef
  useEffect(() => {
    currentSessionIdRef.current = sessionId;
  }, [sessionId]);
  
  // 同步isPaused到isPausedRef
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);
  
  // 同步messagesCountRef
  useEffect(() => {
    messagesCountRef.current = messages.length;
  }, [messages.length]);
  
  // ==================== 返回值 ====================
  
  return {
    // 状态
    messages,
    setMessages,
    loading,
    setLoading,
    waitTime,
    setWaitTime,
    isRetrying,
    setIsRetrying,
    isPaused,
    setIsPaused,
    sessionId,
    setSessionId,
    sessionTitle,
    setSessionTitle,
    sessionVersion,
    setSessionVersion,
    titleLocked,
    setTitleLocked,
    editingTitle,
    setEditingTitle,
    titleInput,
    setTitleInput,
    lastSavedTitle,
    setLastSavedTitle,
    showExecution,
    setShowExecution,
    useStream,
    setUseStream,
    isInitialized,
    setIsInitialized,
    saveStatus,
    setSaveStatus,
    sessionJumpLoading,
    setSessionJumpLoading,
    isMessageListLoading,
    setIsMessageListLoading,
    retryCount,
    setRetryCount,
    isSavingTitle,
    setIsSavingTitle,
    lastSaveTime,
    setLastSaveTime,
    
    // Refs
    waitTimerRef,
    messagesEndRef,
    currentSessionIdRef,
    messagesCountRef,
    messagesRef,
    replyUserMessageIdRef,
    displayBufferRef,
    isPausedRef,
    executionStepsRef,
    streamingContentRef,
    streamingStepsRef,
    userScrolledUpRef,
    lastScrollTimeRef,
    isLoadingHistoryRef,
    logFlagsRef,
    hasReceivedInterruptEventRef,
    interruptInProgressRef,
  };
};