/**
 * SSE 工具模块 V2 - Server-Sent Events 流式处理
 *
 * 功能：建立 SSE 连接、接收流式数据、处理执行步骤
 * 改进：增加自动重连、错误分类、友好提示
 *
 * 错误处理说明：
 * - 所有SSE错误统一使用 errorHandler.handleSSEError() 处理
 * - 禁止直接调用 message.error/warning/success/info
 * - 连接重连、错误去重、提示样式由 errorHandler 统一管理
 *
 * @author 小新
 * @version 2.0.0
 * @since 2026-03-04
 */

import { useState, useCallback, useRef, useEffect } from "react";
// import { message } from "antd";  // 已迁移到errorHandler统一处理
import type { SecurityCheck } from "../types/chat";
import { handleSSEError as errorHandlerHandleSSE, ErrorType } from "./errorHandler";

// 【小强修复 2026-03-18】sessionStorage key - 用于长时间隐藏页面时备份数据
// 场景：用户切换到其他应用→页面隐藏→SSE 连接不断开→后端数据持续发送
// 问题：浏览器降频导致回调延迟执行，标签页可能被丢弃
// 解决：同时保存到 ref + sessionStorage，即使标签页丢弃数据也不会丢失
const SSE_STORAGE_KEY = "sse_execution_steps_backup";

/**
 * SSE错误类型 - 用于 onError 回调函数参数
 * 文档：API-chat-stream.md
 * 【小沈修改2026-04-15】删除code和message字段，统一使用error_message
 */
export interface SSEError {
  // 必填字段（3个）
  type: string;           // 固定值: error
  error_type: string;     // 错误类型
  error_message: string; // 用户友好的错误信息 【修改2026-04-15】message → error_message
  // 必填字段（1个）
  timestamp: string;      // 时间戳
  // 可选字段（8个）
  model?: string;         // 模型名称
  provider?: string;      // 提供商名称
  details?: string;       // 详细错误信息
  stack?: string;        // 堆栈信息
  retryable?: boolean;   // 是否可重试
  retry_after?: number;  // 重试等待秒数
  recoverable?: boolean; // 是否可恢复 【新增2026-04-15】
  context?: {            // 错误上下文 【新增2026-04-15】
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

/**
 * SSE 元数据
 */
export interface SSEMetadata {
  model?: string;
  provider?: string;
  display_name?: string;
}

/**
 * 执行步骤类型 - 与后端字段完全对应，便于调试和理解
 * 【小新重构2026-03-09】适配新API字段名
 * 
 * 【重要】8种type说明：
 * - 内容步骤：start（开始）、chunk（AI流式回复的内容片段）、final（最终回答）
 *   【chunk是AI流式输出的内容片段，不是执行步骤，显示在AI回复区域，不在步骤列表】
 * - 执行步骤：thought（思考）、action_tool（工具调用）、observation（工具结果）
 * - 异常步骤：error（错误）、incident（中断）
 */
export interface ExecutionStep {
  // === 通用字段 ===
  // ⭐ 新增action_tool类型，替换原来的action
  // 【小沈修复2026-03-28】后端type固定为'incident'，通过incident_value区分具体类型
  type: "thought" | "action_tool" | "observation" | "chunk" | "final" | "error" | "incident" | "interrupted" | "start" | "paused" | "resumed" | "retrying";
  content?: string;        // 前端显示用：根据type使用不同字段填充小查修复202
  
  // 【6-03-09】添加task_id字段，用于分页请求
  task_id?: string;      // 任务ID，用于分页请求
  
  // 【小强添加 2026-03-24】用户消息前40字
  user_message?: string;  // 用户发送的消息内容预览
  
  // === 思考/动作提示字段（后端字段拆分） ===
  thinking_prompt?: string;    // thought 类型的提示文本
  action_description?: string; // action_tool 类型的描述文本
  
  // 【小新重构2026-03-09】thought类型需要的字段
  // 【小健建议2026-03-23】明确用途：LLM思考后决定的下一步动作
  tool_name?: string;        // 【thought类型】LLM思考后决定的下一步动作
  tool_params?: Record<string, any>; // 【thought类型】LLM思考后决定的参数
  
  // === 保留字段（不变）===
  
  // === 保留字段（不变）===
  // observation 相关
  step?: number;
  thought?: string;
  action?: string;  // 兼容旧字段
  observation?: any;
  result?: string;
  
  // === 【小新重构】type=action_tool 新字段（与thought类型共用tool_name/tool_params）===
  execution_status?: 'success' | 'error' | 'warning'; // 执行状态（新）
  summary?: string;             // 执行摘要（新）
  execution_result?: Record<string, any> | null; // 执行结果 【修改2026-04-15】raw_data → execution_result
  execution_time_ms?: number;   // 执行耗时 【新增2026-04-15】
  action_retry_count?: number;  // 重试次数（新）
  
  // === type=observation 字段（精简版，2026-04-07 小资修改） ===
  // 后端删除第二次LLM调用后，observation只保留基础字段
  // 工具执行结果已在 action_tool 阶段完整显示（execution_status/summary/execution_result）
  // 【注意】obs_* 字段已删除，如需使用工具结果请从 action_tool 阶段获取
  // tool_name 已在上面 action_tool 字段定义（第97行），此处不再重复

  // === type=action 旧字段（兼容） ===
  action_input?: Record<string, any>;  // 工具调用参数（旧）
  
  // === type=chunk/final/start 字段 ===
  model?: string;         // AI模型
  provider?: string;      // AI提供商
  display_name?: string;  // 显示名称
  
  // === type=final 字段 【新增2026-04-15】===
  response?: string;       // 最终回答内容
  is_streaming?: boolean;  // 是否流式输出
  is_finished?: boolean;   // 是否已完成
  
  // === type=observation 字段 【新增2026-04-15】===
  return_direct?: boolean;  // 是否直接返回
  
  // === 思考过程与正式内容区分字段（统一使用 is_reasoning snake_case）===
  is_reasoning?: boolean;  // 是否为思考过程（true=思考过程，false=正式内容）
  reasoning?: string;       // 思考过程内容（当 is_reasoning=true 时使用）
  
  // === 错误/中断字段 ===
  // 【小沈修复2026-03-28】后端incident类型使用incident_value区分具体类型
  incident_value?: string;    // incident 类型的具体值（interrupted/paused/resumed/retrying）
  error_message?: string;      // error 类型的错误信息 【修改2026-04-15】优先使用error_message
  message?: string;           // interrupted 类型的中断信息

  // 【小新修复 2026-03-14】error类型完整字段（避免使用 as any）
  // 【小沈修改2026-04-15】删除code字段，统一使用error_message
  error_type?: string;        // 业务错误类型（如 empty_response）
  details?: string;           // 详细错误信息
  stack?: string;             // 堆栈信息
  retryable?: boolean;        // 是否可重试
  retry_after?: number;       // 重试等待秒数
  recoverable?: boolean;       // 是否可恢复 【新增2026-04-15】
  context?: {                 // 错误上下文 【新增2026-04-15】
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
  wait_time?: number;         // 等待时间（秒）

  // === 前端额外字段 ===
  timestamp: number;      // 前端生成的时间戳
  contentStart?: number;  // content起始位置（用于流式定位）
  contentEnd?: number;    // content结束位置
  
  // === 安全检查字段 ===
  security_check?: SecurityCheck;
}

/**
 * SSE连接配置
 */
export interface SSEConfig {
  baseURL: string;
  sessionId: string;
  token?: string;
  taskId?: string;
}

/**
 * SSE重连配置
 */
export interface ReconnectConfig {
  enabled: boolean;
  maxAttempts: number;
  baseDelay: number;
  maxDelay: number;
}

/**
 * SSE Hook返回值
 */
export interface UseSSEReturn {
  isConnected: boolean;
  isReceiving: boolean;
  executionSteps: ExecutionStep[];
  currentResponse: string;
  sendMessage: (content: string, sessionId?: string) => void;
  disconnect: (manualDisconnect?: boolean) => void;
  clearSteps: () => void;
  serverTaskId?: string | null;
  setServerTaskId?: (taskId: string | null) => void;
  /** 重连状态 */
  reconnectStatus: "idle" | "connecting" | "reconnecting" | "failed";
  /** 手动重连 */
  reconnect: () => void;
  /** 性能指标 */
  performanceMetrics?: PerformanceMetrics | null;
}

/**
 * SSE性能指标
 * 【小强添加 2026-03-18】用于追踪用户体验
 */
export interface PerformanceMetrics {
  ttft: number;            // Time To First Token 首token时间（毫秒）
  totalTokens: number;     // 估算总token数
  tokensPerSecond: number; // 每秒token数
  totalTime: number;      // 总响应时间（毫秒）
  chunkCount: number;     // chunk数量
}

/**
 * 错误类型分类
 * 【小强修复 2026-04-11】使用统一错误处理中心
 */
type SSEErrorType = "idle_timeout" | "request_timeout" | "network" | "server" | "unknown" | "empty_response" | "connection_refused" | "http_500";

/**
 * 分类错误类型 - 适配errorHandler的分类结果
 * 【小强修复 2026-04-09】细分超时类型
 * 【小强修复 2026-04-11】增加 connection_refused 和 http_500，映射到统一ErrorType
 */
const classifyError = (error: any): SSEErrorType => {
  // 使用errorHandler的分类结果进行映射
  const unifiedType = errorHandlerHandleSSE(error, { reconnectAttempts: 0 }).errorType;
  
  // 映射到SSE本地错误类型
  switch (unifiedType) {
    case ErrorType.IDLE_TIMEOUT:
      return "idle_timeout";
    case ErrorType.REQUEST_TIMEOUT:
      return "request_timeout";
    case ErrorType.NETWORK_ERROR:
    case ErrorType.WEAK_NETWORK:
      return "network";
    case ErrorType.CONNECTION_REFUSED:
    case ErrorType.CONNECTION_RESET:
      return "connection_refused";
    case ErrorType.SERVER_500:
      return "http_500";
    case ErrorType.SERVER_502:
    case ErrorType.SERVER_503:
      return "server";
    case ErrorType.BACKEND_ERROR:
      return "empty_response";
    case ErrorType.REQUEST_ABORT:
      return "request_timeout";
    default:
      return "unknown";
  }
};

/**
 * 错误配置 - 定义每种错误类型的处理方式
 * 【小强修复 2026-04-11】使用统一错误处理中心errorHandler
 */
interface ErrorConfig {
  retryable: boolean;        // 是否可重试
  maxRetries: number;         // 最大重试次数
  retryDelay: number;         // 重试延迟(毫秒)
  showMessage: string;        // 显示的消息
  stopAction?: () => void;    // 停止后的操作
}

/**
 * 统一错误处理函数
 * 【小强添加 2026-04-11】使用统一错误处理中心errorHandler
 * 【小强修复 2026-04-11】重构：使用errorHandler.handleSSEError
 */
const handleSSEError = (params: {
  error: any;
  errorType: SSEErrorType;
  reconnectAttempts: number;
  reconnectConfig: ReconnectConfig;
  pendingMessage: { content: string; sessionId?: string } | null;
  onReconnect: () => void;
  onSetReconnectStatus: (status: "idle" | "connecting" | "reconnecting" | "failed") => void;
  onSetIsConnected: (connected: boolean) => void;
  onSetIsReceiving: (receiving: boolean) => void;
  onError: ((error: SSEError) => void) | undefined;
  reconnectTimeoutRef: React.MutableRefObject<number | null>;
}) => {
  const {
    error,
    errorType,
    reconnectAttempts,
    reconnectConfig,
    pendingMessage,
    onReconnect,
    onSetReconnectStatus,
    onSetIsConnected,
    onSetIsReceiving,
    onError,
    reconnectTimeoutRef,
  } = params;

  // 使用统一错误处理中心
  const result = errorHandlerHandleSSE(error, {
    reconnectAttempts,
    maxRetries: reconnectConfig.maxAttempts,
    onReconnect: () => {
      onSetReconnectStatus("reconnecting");
      reconnectTimeoutRef.current = window.setTimeout(() => {
        onReconnect();
      }, reconnectConfig.baseDelay);
    },
  });

  if (!result.handled) {
    return;
  }

  // 如果不可重试或已超过最大次数
  const canRetry = reconnectAttempts < reconnectConfig.maxAttempts && pendingMessage;
  
  if (!canRetry) {
    console.error(`[SSE] 超过最大重试次数(${reconnectConfig.maxAttempts})，停止重连`);
    onSetReconnectStatus("failed");
    onSetIsConnected(false);
    onSetIsReceiving(false);
    
    // 调用错误回调
    onError?.({
      type: "error",
      error_type: errorType,
      error_message: result.errorType ? ERROR_CONFIG_MAP[errorType]?.showMessage || "连接失败" : "连接失败",  // 【小沈修改2026-04-15】message → error_message
      timestamp: new Date().toISOString()
    });
  }
};

/**
 * 获取错误配置 - 兼容SSE本地类型
 */
const ERROR_CONFIG_MAP: Record<SSEErrorType, ErrorConfig> = {
  idle_timeout: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: "空闲超时（长时间无数据），连接可能已断开",
  },
  request_timeout: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: "请求等待超时，服务器响应过慢",
  },
  network: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: "网络连接失败，请检查网络后重试",
  },
  server: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: "服务器错误",
  },
  empty_response: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: "模型未能生成有效回复，请尝试更换问题或稍后重试",
  },
  connection_refused: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: "服务器连接被拒绝，请检查后端服务是否运行",
  },
  http_500: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 3000,  // 500错误等待3秒
    showMessage: "服务器内部错误，请稍后重试",
  },
  unknown: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    showMessage: "发生未知错误",
  },
};

/**
 * 计算重连延迟（指数退避 + Full Jitter）
 * 【小强修复 2026-03-18】增强重试策略，使用Full Jitter算法
 * 
 * Full Jitter公式：delay = random(0, min(baseDelay * 2^attempt, maxDelay))
 * 优点：避免多客户端同时重连造成"惊群效应"
 */
const calculateReconnectDelay = (attempt: number, baseDelay: number, maxDelay: number): number => {
  // 指数退避
  const exponentialDelay = baseDelay * Math.pow(2, attempt);
  // Full Jitter：在[0, exponentialDelay]范围内随机
  const jitter = Math.random() * exponentialDelay;
  // 最终延迟不超过maxDelay
  return Math.min(jitter, maxDelay);
};

export const useSSE = (
  config: SSEConfig,
  onStep?: (step: ExecutionStep) => void,
  onChunk?: (chunk: string, is_reasoning?: boolean) => void,
  onComplete?: (fullResponse: string, metadata?: string | SSEMetadata, executionSteps?: ExecutionStep[]) => void,
  onError?: (error: string | SSEError) => void,
  onPaused?: () => void,
  onResumed?: () => void,
  onShowSteps?: (show: boolean) => void,  // 新增：控制步骤显示/隐藏
  // ⭐ 新增：重试回调 - 【小查修复2026-03-13】添加wait_time参数
  onRetry?: (message: string, waitTime?: number) => void
): UseSSEReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isReceiving, setIsReceiving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const executionStepsRef = useRef<ExecutionStep[]>([]);
  const [currentResponse, setCurrentResponse] = useState("");
  const [reconnectStatus, setReconnectStatus] = useState<"idle" | "connecting" | "reconnecting" | "failed">("idle");

  const eventSourceRef = useRef<EventSource | null>(null);
  const responseBufferRef = useRef("");
  const isProcessingRef = useRef(false);
  const [serverTaskId, setServerTaskId] = useState<string | null>(null);
  
  // 重连相关
  const reconnectConfigRef = useRef<ReconnectConfig>({
    enabled: true,
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 10000,
  });
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pendingMessageRef = useRef<{ content: string; sessionId?: string } | null>(null);

  // 【小强添加 2026-03-18】性能指标相关
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const ttftRef = useRef<number>(0);  // 存储 TTFT 值
  const requestStartTimeRef = useRef<number>(0);
  const chunkCountRef = useRef<number>(0);
  
  // 【小强修复 2026-03-18】SSE 空闲超时检测 - 解决页面隐藏后连接断开问题
  // 【小强修复 2026-04-09】重命名为 IDLE_TIMEOUT，更准确反映语义
  const lastDataTimeRef = useRef<number>(0);  // 最后收到数据的时间
  const idleTimeoutRef = useRef<number | null>(null);  // 空闲超时检测
  const IDLE_TIMEOUT = 60000;  // 60 秒无数据判定为断开

  // 【小强添加 2026-03-18】sessionStorage 备份相关
  // 恢复：组件初始化时检查是否有备份数据
  useEffect(() => {
    const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
    const savedSteps = sessionStorage.getItem(storageKey);
    if (savedSteps) {
      try {
        const parsedSteps = JSON.parse(savedSteps);
        if (Array.isArray(parsedSteps) && parsedSteps.length > 0) {
          console.log(`[SSE] 从 sessionStorage 恢复 ${parsedSteps.length} 个步骤`);
          executionStepsRef.current = parsedSteps;
          setExecutionSteps(parsedSteps);
        }
      } catch (e) {
        console.warn("[SSE] 解析 sessionStorage 备份失败:", e);
        sessionStorage.removeItem(storageKey);
      }
    }
  }, [config.sessionId]);  // 仅在 sessionId 变化时检查

  // 保存到 sessionStorage 的辅助函数
  const saveStepsToStorage = useCallback((steps: ExecutionStep[]) => {
    if (steps.length > 0 && config.sessionId) {
      const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
      try {
        sessionStorage.setItem(storageKey, JSON.stringify(steps));
      } catch (e) {
        console.warn("[SSE] 保存到 sessionStorage 失败:", e);
      }
    }
  }, [config.sessionId]);

  // 清空 sessionStorage 的辅助函数
  const clearStepsFromStorage = useCallback(() => {
    const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
    sessionStorage.removeItem(storageKey);
  }, [config.sessionId]);

  /**
   * 断开连接
   * @param manualDisconnect - 是否是手动中断（手动中断不允许重连）
   * @param clearStorage - 是否清空 sessionStorage（重连时设为 false，保留数据）
   */
  const disconnect = useCallback((manualDisconnect: boolean = false, clearStorage: boolean = true) => {
    // 清空 sessionStorage 备份（除非重连时明确指定不清空）
    if (clearStorage) {
      clearStepsFromStorage();
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
    setIsReceiving(false);
    setReconnectStatus("idle");
    reconnectAttemptsRef.current = 0;
    
    // 手动中断时清除 pendingMessage 并阻止重连
    if (manualDisconnect) {
      pendingMessageRef.current = null;
      reconnectConfigRef.current.enabled = false;
      // 3秒后恢复重连功能（避免永久禁用）
      setTimeout(() => {
        reconnectConfigRef.current.enabled = true;
      }, 3000);
    }
  }, []);

   /**
    * 软清理执行步骤（用于重连时保留已有步骤）
    * 只清理运行时状态，不清空已收到的 steps
    */
  const softClearSteps = useCallback(() => {
    setCurrentResponse("");
    responseBufferRef.current = "";
  }, []);

  /**
   * 清空执行步骤（完全重置，用于新对话）
   */
  const clearSteps = useCallback(() => {
    setExecutionSteps([]);
    executionStepsRef.current = [];
    setCurrentResponse("");
    responseBufferRef.current = "";
    // 【小强添加 2026-03-18】同时清空 sessionStorage 备份
    clearStepsFromStorage();
  }, [clearStepsFromStorage]);

  /**
    * 内部发送消息函数（用于重连）
    * 【小强修复 2026-04-09】重连时使用软清理，保留已收到的 steps
    */
  const sendMessageInternal = async (content: string, sessionId?: string) => {
    const connectStartTime = new Date().toLocaleTimeString();
    console.log(`[SSE] [连接建立] 时间=${connectStartTime}`);
    disconnect(false, false);  // 重连时：非手动断开 + 不清空 sessionStorage
    softClearSteps();  // 软清理：保留 steps，只清理运行时状态

    // 【小强添加 2026-03-18】重置性能指标并记录开始时间
    requestStartTimeRef.current = Date.now();
    ttftRef.current = 0;
    chunkCountRef.current = 0;
    setPerformanceMetrics(null);

    setIsReceiving(true);
    setIsConnected(true);
    setReconnectStatus("connecting");

    try {
      // 多意图重构配置: 0=旧端点, 1=新端点(v2)
      const USE_NEW_ROUTER = 1; // 可配置：0 或 1
      const url = USE_NEW_ROUTER 
        ? `${config.baseURL}/chat/stream/v2`
        : `${config.baseURL}/chat/stream`;
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 60000);

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(config.token ? { Authorization: `Bearer ${config.token}` } : {}),
        },
        body: JSON.stringify({
          messages: [{ role: "user", content: content }],
          stream: true,
          task_id: undefined,
          session_id: sessionId || undefined,
        }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error("响应体为空");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let buffer = "";
      
      // 【小强修复 2026-03-18】初始化最后数据时间
      lastDataTimeRef.current = Date.now();

      // eslint-disable-next-line no-constant-condition
      while (true) {
        // 【小强修复 2026-04-09】使用 IDLE_TIMEOUT，更准确的命名
        if (idleTimeoutRef.current) {
          clearTimeout(idleTimeoutRef.current);
        }
        idleTimeoutRef.current = window.setTimeout(() => {
          const timeSinceLastData = Date.now() - lastDataTimeRef.current;
          if (timeSinceLastData > IDLE_TIMEOUT && isReceiving) {
            console.warn(`[SSE] 空闲超时：已经${timeSinceLastData/1000}秒未收到数据，判定连接断开`);
            throw new Error("SSE 空闲超时：长时间未收到数据");
          }
        }, IDLE_TIMEOUT);
        
        const { done, value } = await reader.read();

        if (done) {
          if (buffer.trim()) {
            processSSEData(buffer, {
              setExecutionSteps,
              getCurrentExecutionSteps: () => executionStepsRef.current,
              executionStepsRef,
              saveStepsToStorage,
              onStep,
              onChunk,
              onComplete,
              onError,
              onPaused,
              onResumed,
              onShowSteps,
              onRetry,
              setCurrentResponse,
              responseBufferRef,
              setIsReceiving,
              setIsConnected,
              disconnect,
              setServerTaskId,
            }, isProcessingRef);
          }
          break;
        }

        // 【小强修复 2026-03-18】更新最后数据时间
        lastDataTimeRef.current = Date.now();
        
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          processSSEData(line, {
            setExecutionSteps,
            getCurrentExecutionSteps: () => executionStepsRef.current,
            executionStepsRef,
            saveStepsToStorage,
            onStep,
            onChunk,
            onComplete,
            onError,
            onPaused,
            onResumed,
            onShowSteps,
            onRetry,
            setCurrentResponse,
            responseBufferRef,
            setIsReceiving,
            setIsConnected,
            disconnect,
            setServerTaskId,
          }, isProcessingRef);
        }
      }
      
      // 成功，重置重连状态
      setReconnectStatus("idle");
      reconnectAttemptsRef.current = 0;
    } catch (error: any) {
      console.error("[SSE] 请求错误:", error);
      
      // 使用统一的错误处理中心
      handleSSEError({
        error,
        errorType: classifyError(error),
        reconnectAttempts: reconnectAttemptsRef.current,
        reconnectConfig: reconnectConfigRef.current,
        pendingMessage: pendingMessageRef.current,
        onReconnect: () => {
          reconnectAttemptsRef.current++;
          sendMessageInternal(content, sessionId);
        },
        onSetReconnectStatus: setReconnectStatus,
        onSetIsConnected: setIsConnected,
        onSetIsReceiving: setIsReceiving,
        onError,
        reconnectTimeoutRef,
      });
      
      // 保存待重连的消息（用于下次重连）
      if (pendingMessageRef.current) {
        // 消息已由 handleSSEError 处理
      }
    }
  };

  /**
   * 重连函数
   * 【小强修复 2026-04-09】重新添加缺失的 reconnect 函数，移到 sendMessageInternal 之后避免变量未定义问题
   */
  const reconnect = useCallback(() => {
    if (!pendingMessageRef.current) {
      console.warn("[SSE] 没有待重连的消息");
      return;
    }

    const { content, sessionId } = pendingMessageRef.current;
    const config = reconnectConfigRef.current;
    
    if (reconnectAttemptsRef.current >= config.maxAttempts) {
      console.error("[SSE] 超过最大重连次数");
      setReconnectStatus("failed");
      // 使用errorHandler统一处理
      const error = { message: "SSE连接失败，请刷新页面重试", name: "ConnectionError" };
      errorHandlerHandleSSE(error, { reconnectAttempts: config.maxAttempts, maxRetries: config.maxAttempts, onReconnect: undefined });
      return;
    }

    const attempt = reconnectAttemptsRef.current;
    const delay = calculateReconnectDelay(attempt, config.baseDelay, config.maxDelay);
    
    setReconnectStatus("reconnecting");
    // 使用errorHandler统一处理（显示重试警告）
    const retryWarningError = { message: `正在重新连接 (${attempt + 1}/${config.maxAttempts})...`, name: "RetryWarning" };
    errorHandlerHandleSSE(retryWarningError, { reconnectAttempts: attempt, maxRetries: config.maxAttempts, onReconnect: undefined });
    
    console.log(`[SSE] 准备重连，attempt=${attempt + 1}, delay=${delay}ms`);

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptsRef.current++;
      sendMessageInternal(content, sessionId);
    }, delay);
  }, [sendMessageInternal]);

  /**
   * 发送消息建立SSE连接
   */
  const sendMessage = useCallback(
    async (content: string, sessionId?: string) => {
      // 【修复小查问题】防止并发调用
      if (isProcessingRef.current) {
        console.warn("[SSE] 已有进行中的请求，等待完成后重试");
        // 使用errorHandler统一处理
        const error = { message: "请求处理中，请稍后再试", name: "DuplicateClick" };
        errorHandlerHandleSSE(error, { reconnectAttempts: 0, maxRetries: 0, onReconnect: undefined });
        return;
      }
      isProcessingRef.current = true;
      
      // 保存待重连的消息
      pendingMessageRef.current = { content, sessionId };
      reconnectAttemptsRef.current = 0;
      
      await sendMessageInternal(content, sessionId);

      // 请求结束后重置
      isProcessingRef.current = false;
    },
    [config, disconnect, clearSteps, onStep, onChunk, onComplete, onError, onRetry]
  );

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      disconnect();
      // 【修复小查问题】清理 pendingMessageRef 避免内存泄漏
      pendingMessageRef.current = null;
      // 【小新修复 2026-03-14】额外确保 reconnectTimeoutRef 被清理
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [disconnect]);

  return {
    isConnected,
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage,
    disconnect,
    clearSteps,
    serverTaskId,
    setServerTaskId,
    reconnectStatus,
    reconnect,
    performanceMetrics,  // 【小强添加 2026-03-18】性能指标
  };
};

/**
 * 处理单行SSE数据
 */
const processSSEData = (
  line: string,
  handlers: {
    setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
    getCurrentExecutionSteps: () => ExecutionStep[];
    executionStepsRef: React.MutableRefObject<ExecutionStep[]>;  // 【小新添加 2026-03-15】用于同步更新 ref
    saveStepsToStorage?: (steps: ExecutionStep[]) => void;  // 【小强添加 2026-03-18】保存到 sessionStorage
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string, is_reasoning?: boolean) => void;
    onComplete?: (fullResponse: string, metadata?: string | SSEMetadata, executionSteps?: ExecutionStep[]) => void;
    onError?: (error: string | SSEError) => void;
    onPaused?: () => void;
    onResumed?: () => void;
    onShowSteps?: (show: boolean) => void;
    onRetry?: (message: string, waitTime?: number) => void;
    setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
    responseBufferRef: React.MutableRefObject<string>;
    setIsReceiving: React.Dispatch<React.SetStateAction<boolean>>;
    setIsConnected: React.Dispatch<React.SetStateAction<boolean>>;
    disconnect: (manualDisconnect?: boolean) => void;
    setServerTaskId?: (taskId: string) => void;
  },
  _isProcessingRef: React.MutableRefObject<boolean>
) => {
  const {
    setExecutionSteps,
    saveStepsToStorage,
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onShowSteps,
    onRetry,
    setCurrentResponse,
    responseBufferRef,
    setIsReceiving,
    setIsConnected,
    disconnect: _disconnect,
    setServerTaskId,
  } = handlers;

  if (!line.trim() || !line.startsWith("data: ")) {
    return;
  }

  try {
    let jsonStr = line.slice(6);
    jsonStr = jsonStr.trim();
    const rawData = JSON.parse(jsonStr);

    // 【小强修复 2026-03-18】统一处理timestamp转换
    // 后端有些字段返回字符串格式timestamp，前端需要转换为毫秒数
    let timestampValue = Date.now();
    if (rawData.timestamp) {
      if (typeof rawData.timestamp === 'number') {
        timestampValue = rawData.timestamp;
      } else if (typeof rawData.timestamp === 'string') {
        // 尝试解析字符串时间戳
        const parsed = Date.parse(rawData.timestamp);
        timestampValue = isNaN(parsed) ? Date.now() : parsed;
      }
    }
    
    const step: ExecutionStep = {
      type: rawData.type as ExecutionStep["type"],
      
      // 根据不同type使用不同字段（后端字段拆分方案）
      thinking_prompt: rawData.thinking_prompt,
      action_description: rawData.action_description,
      content: rawData.content,
      error_message: rawData.error_message,
      message: rawData.message,
      
      // 保留字段
      step: rawData.step || 1,           // 与后端一致：step
      thought: rawData.thought,          // Agent.thought的值
      action: rawData.action,            // 执行动作名称，与后端一致
      observation: rawData.observation,  // 保留原始对象，用于调试
      result: rawData.result,            // simplify_observation处理后的文本
      action_input: rawData.action_input, // 工具调用参数
      
      // 【小沈修复】思考过程与正式内容区分字段
        // 【小查修复】统一使用 snake_case: is_reasoning
        is_reasoning: rawData.is_reasoning === true || rawData.is_reasoning === 'true' || rawData.is_reasoning === 1 || rawData.is_reasoning === 'true',
        // reasoning: rawData.reasoning || "",  // 【小强删除 2026-04-08】reasoning与content重复，后端已删除
        
      timestamp: timestampValue,
    };

    if (rawData.task_id && setServerTaskId) {
      setServerTaskId(rawData.task_id);
    }

    switch (rawData.type) {
      case "start": {
        const stepNum = rawData.step || 1;
        console.log(`%c[STEP] [type=start] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`, 'color: red; font-weight: bold;');
        let displayName = rawData.display_name;
        if (!displayName && rawData.model && rawData.provider) {
          displayName = `${rawData.provider} (${rawData.model})`;
        }

        const startStep: ExecutionStep = {
          type: "start",
          content: "🤔 AI 正在思考...",
          // 【小资修复 2026-03-18】使用后端返回的timestamp，而不是前端生成
          timestamp: timestampValue,
          model: rawData.model,
          provider: rawData.provider,
          display_name: displayName,
          // 【小新修复2026-03-10】添加task_id字段映射
          task_id: rawData.task_id,
          // 【小强添加 2026-03-24】添加user_message字段映射
          user_message: rawData.user_message || "",
          // 【小强修复 2026-03-18】添加step字段映射，后端已返回step值
          step: rawData.step || 1,
           // 【小查修复2026-03-10】添加security_check字段处理
           security_check: rawData.security_check ? {
             is_safe: rawData.security_check.is_safe,
             risk_level: rawData.security_check.risk_level,
             risk: rawData.security_check.risk,
             blocked: rawData.security_check.blocked,
           } : undefined,
        };

        // 【小新修复 2026-03-15 V2】在回调中同步更新 executionStepsRef.current
        // 根因：setExecutionSteps 更新 React state 是异步的，useEffect 依赖 executionSteps 更新
        //      但 useEffect 在 onComplete 调用时还未执行，导致 getCurrentExecutionSteps() 获取到旧值
        // 修复：在 setExecutionSteps 回调中同步更新 ref，确保其他代码立即获取到最新值
        setExecutionSteps((prev) => {
          const newSteps = [...prev, startStep];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(startStep);
        // 【小查修复】收到start时显示步骤UI（必须在onStep之后）
        onShowSteps?.(true);
        break;
      }

      case "thought": {
        const stepNum = rawData.step || 1;
        console.log(`%c[STEP] [type=thought] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`, 'color: red; font-weight: bold;');
        
        // 【小沈修改2026-04-16】使用后端字段存储
        step.step = rawData.step || 1;
        step.timestamp = rawData.timestamp || Date.now();
        // 后端有两个字段：content(完整思考内容)和thought(parsed获取的thought)
        step.content = rawData.content || "";  // 完整思考内容
        step.thought = rawData.thought || ""; // parsed的thought
        step.reasoning = rawData.reasoning || "";
        step.tool_name = rawData.tool_name || rawData.action_tool || "";  // 兼容旧字段
        step.tool_params = rawData.tool_params || rawData.params || {};    // 兼容旧字段
        // console.log("🔍 [sse thought] step对象=", JSON.stringify(step));
        // 添加到步骤数组，显示思考过程
        // 【小新修复 2026-03-15 V2】在回调中同步更新 executionStepsRef.current
        // 根因：setExecutionSteps 更新 React state 是异步的，useEffect 依赖 executionSteps 更新
        //      但 useEffect 在 onComplete 调用时还未执行，导致 getCurrentExecutionSteps() 获取到旧值
        // 修复：在 setExecutionSteps 回调中同步更新 ref，确保其他代码立即获取到最新值
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        // 【小查修复】收到thought时显示步骤UI
        onShowSteps?.(true);
        break;
      }

      case "chunk": {
        // 精简日志：chunk不打印，避免日志过多
        
        // 传递 is_reasoning 区分思考过程和最终答案
        const is_reasoning = rawData.is_reasoning === true || rawData.is_reasoning === 'true' || rawData.is_reasoning === 1 || rawData.is_reasoning === '1';
        const chunkContent = rawData.content || "";
        responseBufferRef.current += chunkContent;
        setCurrentResponse(responseBufferRef.current);
        onChunk?.(chunkContent, is_reasoning);
        
        // 【小新修复 2026-03-15 V3】chunk只保存当前小块内容，不保存累积
        // 核心原则：保存不能多也不能少，每个chunk只保存当前增量
        // 
        // 实时显示逻辑（NewChatContainer.tsx）：
        //   - content累加显示：lastMessage.content + chunk（这是正确的，需要累加才能看到完整内容）
        // 
        // 保存数据逻辑（此处）：
        //   - chunk保存当前小块：step.content = chunkContent（不是累积，只存当前块）
        //   - final保存完整内容：在final事件中保存message.content完整内容
        // 
        // 历史消息显示逻辑（MessageItem.tsx）：
        //   - 遍历所有chunk逐个显示（每个chunk只显示自己的内容）
        //   - 如果没有is_reasoning=false的chunk，则显示message.content补充
        // 
        // 错误做法会导致的问题：
        //   - 如果chunk保存累积内容 → 导出JSON每个chunk都重复 → 数据错误
        //   - 历史教训：不能为了解决刷新问题而破坏保存数据的正确性！
        step.content = chunkContent;
        
        // 【小沈带小强修改 2026-03-17】
        // 问题描述：前端导出 JSON 时只有 3 个步骤（start, thought, chunk），但数据库有 55 个步骤
        // 【小强修复 2026-04-10】使用回调函数模式，与 start/thought/action_tool/observation 保持一致
        // 问题：之前使用直接同步更新，导致 ref 和 state 不同步
        // 解决：在 setExecutionSteps 回调函数内部更新 ref，确保同步
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        // 【小查修复】收到 chunk 时关闭步骤 UI，开始显示回复内容（必须在 onStep 之后）
        // 【小强修复 2026-03-17】根据 is_reasoning 区分：true=显示步骤 UI，false=关闭步骤 UI
        if (is_reasoning) {
          onShowSteps?.(true);   // 思考过程的 chunk
        } else {
          onShowSteps?.(false);  // 最终答案的 chunk
        }
        break;
      }

      case "final": {
        const stepNum = rawData.step || 1;
        console.log(`%c[STEP] [type=final] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`, 'color: red; font-weight: bold;');
        
        // 【小沈修改2026-04-16】添加step和timestamp字段
        step.step = rawData.step || 1;
        step.timestamp = rawData.timestamp || Date.now();
        
        // 【小强修复 2026-04-15】后端final类型没有content字段，直接使用response
        // 解析后端所有字段
        step.response = rawData.response || "";
        step.is_finished = rawData.is_finished;
        step.thought = rawData.thought || "";
        step.is_streaming = rawData.is_streaming;
        step.is_reasoning = rawData.is_reasoning;
        step.content = step.response;  // content只用于前端显示，使用response的值
        
        if (step.content) {
          if (!responseBufferRef.current) {
            responseBufferRef.current = step.content;
            setCurrentResponse(responseBufferRef.current);
            onChunk?.(step.content);
          }
        }

        // 设置 display_name、model、provider 字段
        step.display_name = rawData.display_name;
        step.model = rawData.model;
        step.provider = rawData.provider;

        const displayName = rawData.display_name;
        
        // 【关键修复 2026-04-13】在回调之前先更新ref，确保onComplete获取完整数据
        // 问题：setExecutionSteps回调是异步的，导致onComplete拿到旧值
        // 解决：先直接更新ref，再调用onComplete
        const updatedSteps = [...handlers.executionStepsRef.current, step];
        handlers.executionStepsRef.current = updatedSteps;
        
        // 【小查修复】保存final到executionSteps，以便导出功能能获取到
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        // 【小强修复 2026-04-10】添加 onShowSteps?.(true)，确保直接返回 final 时步骤列表显示
        onShowSteps?.(true);

        // 【关键修复 2026-04-13】在onComplete调用前手动构建完整的steps数组
        // 问题：setExecutionSteps回调是异步的，handlers.executionStepsRef.current已更新为最新值
        // 解决：直接使用已更新的ref
        const finalStepsWithCurrent = handlers.executionStepsRef.current;

           onComplete?.(responseBufferRef.current, {
          model: rawData.model,
          provider: rawData.provider,
          display_name: displayName,
        } as SSEMetadata, finalStepsWithCurrent);
        
        console.log(`[SSE] [连接断开] 时间=${new Date().toLocaleTimeString()} 收到steps=${handlers.getCurrentExecutionSteps().length}`);
        
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case "error": {
        const stepNum = rawData.step || 1;
        console.log(`%c[STEP] [type=error] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`, 'color: red; font-weight: bold;');
        
        // 【小强修复 2026-04-15】后端error类型只有以下字段，只解析后端存在的字段
        const errorMsg = rawData.error_message || "未知错误";
        step.content = errorMsg;
        step.error_message = errorMsg;
        step.error_type = rawData.error_type || "";
        
        // 解析后端存在的字段
        if (rawData.step) {
          step.step = rawData.step;
        }
        if (rawData.model) {
          step.model = rawData.model;
        }
        if (rawData.provider) {
          step.provider = rawData.provider;
        }
        if (rawData.recoverable !== undefined) {
          step.recoverable = rawData.recoverable;
        }
        if (rawData.context) {
          step.context = {
            step: rawData.context.step,
            model: rawData.context.model,
            provider: rawData.context.provider,
            thought_content: rawData.context.thought_content,
          };
        }
        if (rawData.retry_after !== undefined) {
          step.retry_after = rawData.retry_after;
        }
        if (rawData.timestamp) {
          step.timestamp = rawData.timestamp;
        }
        // 【小沈修复 2026-03-17】先调用onStep，将error步骤添加到executionSteps
        // 问题：之前只调用onError，没有调用onStep，导致error步骤丢失
        // 【小强修复 2026-04-03】error步骤也需要保存到sessionStorage，否则页面切换后丢失
        // 【小强修复 2026-04-10】使用回调函数模式 + 添加 onShowSteps?.(true) + setTimeout延迟保存
        // 问题：之前使用直接同步更新，导致 ref 和 state 不同步
        // 解决：在 setExecutionSteps 回调函数内部更新 ref，确保同步
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        // 【小强修复 2026-04-10】添加 onShowSteps?.(true)，确保 error 步骤显示
        onShowSteps?.(true);
        // 【小沈修改2026-04-15】传递完整的错误对象，统一使用error_message，删除code字段
        onError?.({
          type: "error",
          error_type: rawData.error_type || "unknown_error",
          error_message: errorMsg,
          model: rawData.model,
          provider: rawData.provider,
          details: rawData.details,
          stack: rawData.stack,
          retryable: rawData.retryable,
          retry_after: rawData.retry_after,
          recoverable: rawData.recoverable,
          context: rawData.context,
          timestamp: rawData.timestamp || timestampValue
        });
        // 【小强修复 2026-04-09】关键：不再调用onComplete（和v0.8.75一致），error步骤由onError处理
        // v0.8.75版本没有调用onComplete，UI显示正常
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      // 【小沈修复 2026-04-11】新增：action_tool类型处理
      case "action_tool": {
        const receiveTime = Date.now();  // 【收到数据】时间
        const actionStepNum = step.step;  // step 序号
        const stepLabel = ` [type=action_tool] [step=${actionStepNum}]`;
        
        step.tool_name = rawData.tool_name || "";
        step.tool_params = rawData.tool_params || {};
        step.execution_status = rawData.execution_status;
        step.summary = rawData.summary;
        // 【小强修改2026-04-15】直接使用execution_result
        step.execution_result = rawData.execution_result || null;
        step.execution_time_ms = rawData.execution_time_ms;
        step.action_retry_count = rawData.action_retry_count;
        
        // 【红色】收到数据
        console.log(`%c[ACTION_TOOL]${stepLabel} [收到数据] 时间=${new Date(receiveTime).toLocaleTimeString()}`, 'color: red; font-weight: bold;');
        
        // 【蓝色】ExecutionSteps保存开始时间
        const execStepsStartTime = Date.now();
        console.log(`%c[ACTION_TOOL]${stepLabel} [ExecutionSteps保存开始] 时间=${new Date(execStepsStartTime).toLocaleTimeString()}`, 'color: blue;');
        
        setExecutionSteps((prev) => {
          // 【蓝色】ExecutionSteps保存完成
          const execStepsDoneTime = Date.now();
          const execStepsDuration = execStepsDoneTime - execStepsStartTime;
          console.log(`%c[ACTION_TOOL]${stepLabel} [ExecutionSteps保存完成] 完成=${new Date(execStepsDoneTime).toLocaleTimeString()} 耗时=${execStepsDuration}ms`, 'color: blue;');
          
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          
          // 【紫色】sessionStorage保存开始时间
          const storageStartTime = Date.now();
          console.log(`%c[ACTION_TOOL]${stepLabel} [sessionStorage保存开始] 时间=${new Date(storageStartTime).toLocaleTimeString()}`, 'color: #006400; font-weight: bold;');
          
          setTimeout(() => {
            try {
              // 【紫色】sessionStorage保存完成
              const storageDoneTime = Date.now();
              const storageDuration = storageDoneTime - storageStartTime;
              console.log(`%c[ACTION_TOOL]${stepLabel} [sessionStorage保存完成] 完成=${new Date(storageDoneTime).toLocaleTimeString()} 耗时=${storageDuration}ms`, 'color: #006400; font-weight: bold;');
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        
        // 【青色】渲染开始时间点
        const renderStartTime = Date.now();
        console.log(`%c[ACTION_TOOL]${stepLabel} [渲染开始] 时间=${new Date(renderStartTime).toLocaleTimeString()}`, 'color: cyan;');
        
        onStep?.(step);
        onShowSteps?.(true);
        
        // 【青色】渲染完成时间点
        const renderDoneTime = Date.now();
        const renderDuration = renderDoneTime - renderStartTime;
        console.log(`%c[ACTION_TOOL]${stepLabel} [渲染完成] 完成=${new Date(renderDoneTime).toLocaleTimeString()} 耗时=${renderDuration}ms`, 'color: cyan; font-weight: bold;');
        
        break;
      }

      // 【小沈修复 2026-04-11】新增：observation类型处理
      case "observation": {
        const stepNum = rawData.step || 1;
        console.log(`%c[STEP] [type=observation] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`, 'color: red; font-weight: bold;');
        
        // 【小沈修改2026-04-16】使用后端字段存储，不再用content中转
        step.step = rawData.step || 1;
        step.timestamp = rawData.timestamp || Date.now();
        step.tool_name = rawData.tool_name || "";
        step.tool_params = rawData.tool_params || {};
        step.return_direct = rawData.return_direct;
        // 观察内容存储在observation字段
        step.observation = rawData.observation || "";
        step.content = rawData.observation || "";  // 兼容旧代码
        
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        onShowSteps?.(true);
        break;
      }

      // 【小查修复2026-03-10】新增：incident类型处理（后端发送type='incident'，incident_value字段）
      // 【2026-03-11 重命名】status_value -> incident_value
      // 【小强优化 2026-03-18】统一调用onStep，避免重复
      case "incident": {
        const statusValue = rawData.incident_value;
        const stepNum = rawData.step || 1;
        console.log(`%c[STEP] [type=incident] [incident_type=${statusValue}] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`, 'color: red; font-weight: bold;');
        const statusMessage = rawData.message || "";
        step.type = statusValue as ExecutionStep["type"];
        step.content = statusMessage;
        
        // 统一调用onStep（所有incident类型都需要添加到executionSteps）
        // 【小强修复 2026-04-03】incident步骤也需要保存到sessionStorage，否则页面切换后丢失
        // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn("[SSE] sessionStorage 保存失败，可能容量不足:", e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        
        // 根据incident_value调用对应的回调
        switch (statusValue) {
          case "interrupted":
            // 【小强修复 2026-04-10】添加 onShowSteps?.(true)，确保中断时步骤列表显示
            onShowSteps?.(true);
            onComplete?.(responseBufferRef.current, undefined);
            setIsReceiving(false);
            setIsConnected(false);
            break;
          case "paused":
            onPaused?.();
            break;
          case "resumed":
            onResumed?.();
            break;
          case "retrying":
            // 【小查修复2026-03-13】传递wait_time给重试回调
            onRetry?.(rawData.message || "正在重试...", rawData.wait_time);
            break;
          default:
            console.warn("[SSE] 未知的incident_value:", statusValue);
        }
        // 添加timestamp字段
        if (rawData.timestamp) {
          (step as any).timestamp = rawData.timestamp;
        }
        // 【小查修复2026-03-13】添加wait_time字段（仅retrying使用）
        if (rawData.wait_time !== undefined) {
          (step as any).wait_time = rawData.wait_time;
        }
        break;
      }
    }
  } catch (error) {
    console.error("[SSE] 解析数据失败:", error);
  }
};

export default useSSE;
