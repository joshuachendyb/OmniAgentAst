/**
 * SSE工具模块 V2 - Server-Sent Events流式处理
 *
 * 功能：建立SSE连接、接收流式数据、处理执行步骤
 * 改进：增加自动重连、错误分类、友好提示
 *
 * @author 小新
 * @version 2.0.0
 * @since 2026-03-04
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { message } from "antd";

/**
 * SSE 错误对象
 */
export interface SSEError {
  type: string;
  message: string;
  rawMessage: string;
  model?: string;
  provider?: string;
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
 */
export interface ExecutionStep {
  // === 通用字段 ===
  // ⭐ 新增action_tool类型，替换原来的action
  type: "thought" | "action_tool" | "observation" | "chunk" | "final" | "error" | "interrupted" | "start" | "paused" | "resumed" | "retrying";
  content?: string;        // 前端显示用：根据type使用不同字段填充小查修复202
  
  // 【6-03-09】添加task_id字段，用于分页请求
  task_id?: string;      // 任务ID，用于分页请求
  
  // === 思考/动作提示字段（后端字段拆分） ===
  thinking_prompt?: string;    // thought 类型的提示文本
  action_description?: string; // action_tool 类型的描述文本
  
  // 【小新重构2026-03-09】thought类型需要的字段
  action_tool?: string;        // thought类型的下一步动作
  params?: Record<string, any>; // thought类型的参数
  
  // === AI回复字段（后端字段拆分） ===
  answer_content?: string;    // chunk/final 类型的AI回复
  
  // === 错误/中断字段（后端字段拆分） ===
  error_message?: string;      // error 类型的错误信息
  message?: string;           // interrupted 类型的中断信息
  
  // === 保留字段（不变）===
  // observation 相关
  step?: number;
  thought?: string;
  action?: string;  // 兼容旧字段
  observation?: any;
  result?: string;
  // 【小查修复2026-03-09】添加is_finished字段
  is_finished?: boolean;  // observation类型的是否完成标志
  
  // === 【小新重构】type=action_tool 新字段 ===
  tool_name?: string;           // 工具名称（新）
  tool_params?: Record<string, any>; // 工具参数（新）
  execution_status?: 'success' | 'error' | 'warning'; // 执行状态（新）
  summary?: string;             // 执行摘要（新）
  raw_data?: Record<string, any> | null; // 原始数据（新）
  action_retry_count?: number;  // 重试次数（新）
  
  // === type=action 旧字段（兼容） ===
  action_input?: Record<string, any>;  // 工具调用参数（旧）
  
  // === type=chunk/final/start 字段 ===
  model?: string;         // AI模型
  provider?: string;      // AI提供商
  display_name?: string;  // 显示名称
  
  // === 思考过程与正式内容区分字段（后端新增）===
  is_reasoning?: boolean;  // 是否为思考过程（true=思考过程，false=正式内容）
  reasoning?: string;       // 思考过程内容（当 is_reasoning=true 时使用）
  
  // === 前端额外字段 ===
  timestamp: number;      // 前端生成的时间戳
  contentStart?: number;  // content起始位置（用于流式定位）
  contentEnd?: number;    // content结束位置
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
  disconnect: () => void;
  clearSteps: () => void;
  setTaskId: (taskId: string) => void;
  serverTaskId?: string | null;
  setServerTaskId?: (taskId: string | null) => void;
  /** 重连状态 */
  reconnectStatus: "idle" | "connecting" | "reconnecting" | "failed";
  /** 手动重连 */
  reconnect: () => void;
}

/**
 * 错误类型分类
 */
type ErrorType = "network" | "timeout" | "server" | "unknown";

/**
 * 分类错误类型
 */
const classifyError = (error: any): ErrorType => {
  if (error.name === "AbortError") return "timeout";
  if (error.message?.includes("fetch") || error.message?.includes("network")) return "network";
  if (error.message?.includes("HTTP")) return "server";
  return "unknown";
};

/**
 * 获取友好的错误消息
 */
const getFriendlyErrorMessage = (errorType: ErrorType, originalMessage: string): string => {
  switch (errorType) {
    case "timeout":
      return "请求超时，请检查网络或稍后重试";
    case "network":
      return "网络连接失败，请检查网络后重试";
    case "server":
      return `服务器错误: ${originalMessage}`;
    default:
      return `连接异常: ${originalMessage}`;
  }
};

/**
 * 计算重连延迟（指数退避）
 */
const calculateReconnectDelay = (attempt: number, baseDelay: number, maxDelay: number): number => {
  const delay = Math.min(baseDelay * Math.pow(2, attempt), maxDelay);
  return delay + Math.random() * 1000; // 添加随机抖动
};

export const useSSE = (
  config: SSEConfig,
  onStep?: (step: ExecutionStep) => void,
  onChunk?: (chunk: string, isReasoning?: boolean, reasoning?: string) => void,
  onComplete?: (fullResponse: string, metadata?: string | SSEMetadata) => void,
  onError?: (error: string | SSEError) => void,
  onPaused?: () => void,
  onResumed?: () => void,
  onShowSteps?: (show: boolean) => void,  // 新增：控制步骤显示/隐藏
  // ⭐ 新增：重试回调
  onRetry?: (message: string) => void
): UseSSEReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isReceiving, setIsReceiving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  
  // 【小新修复】用 ref 追踪上一次的 is_reasoning 值
  const lastChunkIsReasoningRef = useRef<boolean | null>(null);
  
  const [currentResponse, setCurrentResponse] = useState("");
  const [reconnectStatus, setReconnectStatus] = useState<"idle" | "connecting" | "reconnecting" | "failed">("idle");

  const eventSourceRef = useRef<EventSource | null>(null);
  const responseBufferRef = useRef("");
  const isProcessingRef = useRef(false);
  const [taskId, setTaskId] = useState<string | null>(null);
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

  /**
   * 断开连接
   */
  const disconnect = useCallback(() => {
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
  }, []);

  /**
   * 清空执行步骤
   */
  const clearSteps = useCallback(() => {
    setExecutionSteps([]);
    setCurrentResponse("");
    responseBufferRef.current = "";
  }, []);

  /**
   * 执行重连
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
      message.error("连接失败，请刷新页面重试");
      return;
    }

    const attempt = reconnectAttemptsRef.current;
    const delay = calculateReconnectDelay(attempt, config.baseDelay, config.maxDelay);
    
    setReconnectStatus("reconnecting");
    message.warning(`正在重新连接 (${attempt + 1}/${config.maxAttempts})...`);
    
    console.log(`[SSE] 准备重连，attempt=${attempt + 1}, delay=${delay}ms`);

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptsRef.current++;
      // 调用 sendMessage 进行重连
      sendMessageInternal(content, sessionId);
    }, delay);
  }, []);

  /**
   * 内部发送消息函数（用于重连）
   */
  const sendMessageInternal = async (content: string, sessionId?: string) => {
    disconnect();
    clearSteps();

    setIsReceiving(true);
    setIsConnected(true);
    setReconnectStatus("connecting");

    try {
      const url = `${config.baseURL}/chat/stream`;
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
          task_id: taskId || undefined,
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

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          if (buffer.trim()) {
            processSSEData(buffer, {
              setExecutionSteps,
              executionSteps,
              lastChunkIsReasoningRef,
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

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          processSSEData(line, {
            setExecutionSteps,
            executionSteps,
            lastChunkIsReasoningRef,
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
      
      // ═══════════════════════════════════════════════════════════
      // ═══════════════════════ 消息结束 ═══════════════════════
      // ═══════════════════════════════════════════════════════════
      console.log("%c╔═════╗", "color: #FF9800; font-weight: bold");
      console.log("%c║ ✅ 消息结束 │ " + new Date().toLocaleTimeString() + "      ║", "color: #FF9800; font-weight: bold");
      console.log("%c╚═════╝", "color: #FF9800; font-weight: bold");
      // ═══════════════════════════════════════════════════════════
    } catch (error: any) {
      console.error("[SSE] 请求错误:", error);
      setIsConnected(false);
      setIsReceiving(false);
      
      const errorType = classifyError(error);
      const friendlyMessage = getFriendlyErrorMessage(errorType, error.message);
      
      // 检查是否需要重连
      if (reconnectConfigRef.current.enabled && errorType !== "unknown") {
        const config = reconnectConfigRef.current;
        const attempt = reconnectAttemptsRef.current;
        const delay = calculateReconnectDelay(attempt, config.baseDelay, config.maxDelay);
        
        message.warning(friendlyMessage + `，${delay/1000}秒后尝试重连...`);
        // 保存待重连的消息
        pendingMessageRef.current = { content, sessionId };
        // 触发重连，使用指数退避延迟
        reconnectTimeoutRef.current = setTimeout(() => {
          reconnect();
        }, delay);
      } else {
        setReconnectStatus("failed");
        message.error(friendlyMessage);
        onError?.(friendlyMessage);
      }
    }
  };

  /**
   * 发送消息建立SSE连接
   */
  const sendMessage = useCallback(
    async (content: string, sessionId?: string) => {
      // 【修复小查问题】防止并发调用
      if (isProcessingRef.current) {
        console.warn("[SSE] 已有进行中的请求，等待完成后重试");
        message.warning("请求处理中，请稍后再试");
        return;
      }
      isProcessingRef.current = true;
      
      // 保存待重连的消息
      pendingMessageRef.current = { content, sessionId };
      reconnectAttemptsRef.current = 0;
      
      // ═══════════════════════════════════════════════════════════
      // ═══════════════════════ 新消息开始 ═══════════════════════
      // ═══════════════════════════════════════════════════════════
      const userMsgPreview = content.length > 50 ? content.substring(0, 50) + "..." : content;
      console.log("%c╔═════╗", "color: #4CAF50; font-weight: bold");
      console.log("%c║ 🆕 新消息  │ " + new Date().toLocaleTimeString() + "      ║", "color: #4CAF50; font-weight: bold");
      console.log("%c║ 👤 " + userMsgPreview + " ║", "color: #2196F3; font-weight: bold");
      console.log("%c╚═════╝", "color: #4CAF50; font-weight: bold");
      // ═══════════════════════════════════════════════════════════
      
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
    setTaskId,
    serverTaskId,
    setServerTaskId,
    reconnectStatus,
    reconnect,
  };
};

/**
  * 处理单行SSE数据
  */
const processSSEData = (
  line: string,
  handlers: {
    setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
    executionSteps: ExecutionStep[];
    lastChunkIsReasoningRef: React.MutableRefObject<boolean | null>;
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string, isReasoning?: boolean, reasoning?: string) => void;
    onComplete?: (fullResponse: string, metadata?: string | SSEMetadata) => void;
    onError?: (error: string) => void;
    onPaused?: () => void;
    onResumed?: () => void;
    onShowSteps?: (show: boolean) => void;
    onRetry?: (message: string) => void;
    setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
    responseBufferRef: React.MutableRefObject<string>;
    setIsReceiving: React.Dispatch<React.SetStateAction<boolean>>;
    setIsConnected: React.Dispatch<React.SetStateAction<boolean>>;
    disconnect: () => void;
    setServerTaskId?: (taskId: string) => void;
  },
  _isProcessingRef: React.MutableRefObject<boolean>
) => {
  const {
    setExecutionSteps,
    executionSteps,
    lastChunkIsReasoningRef,  // 【小新修复】添加
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

    const step: ExecutionStep = {
      type: rawData.type as ExecutionStep["type"],
      
      // 根据不同type使用不同字段（后端字段拆分方案）
      thinking_prompt: rawData.thinking_prompt,
      action_description: rawData.action_description,
      answer_content: rawData.answer_content,
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
      is_reasoning: rawData.is_reasoning || false,
      reasoning: rawData.reasoning || "",
      
      timestamp: Date.now(),
    };

    if (rawData.task_id && setServerTaskId) {
      setServerTaskId(rawData.task_id);
    }

    switch (rawData.type) {
      case "start": {
        let displayName = rawData.display_name;
        if (!displayName && rawData.model && rawData.provider) {
          displayName = `${rawData.provider} (${rawData.model})`;
        }

        const startStep: ExecutionStep = {
          type: "start",
          content: "🤔 AI 正在思考...",
          timestamp: Date.now(),
          model: rawData.model,
          provider: rawData.provider,
          display_name: displayName,
          // 【小新修复2026-03-10】添加task_id字段映射
          task_id: rawData.task_id,
          // 【小查修复2026-03-10】添加security_check字段处理
          raw_data: rawData.security_check ? {
            is_safe: rawData.security_check.is_safe,
            risk_level: rawData.security_check.risk_level,
            risk: rawData.security_check.risk,
            blocked: rawData.security_check.blocked,
          } : undefined,
        };

        setExecutionSteps((prev) => [...prev, startStep]);
        onStep?.(startStep);
        break;
      }

      case "thought": {
        console.log("%c--- thought ---", "color: #00BCD4");
        // 【小新修复】重置 is_reasoning 追踪
        lastChunkIsReasoningRef.current = null;
        
        step.content = rawData.content || "";
        step.reasoning = rawData.reasoning || "";
        step.action_tool = rawData.action_tool || "";
        step.params = rawData.params || {};
        // 添加到步骤数组，显示思考过程
        setExecutionSteps((prev) => [...prev, step]);
        onStep?.(step);
        break;
      }

      case "chunk": {
        const chunkContent = rawData.content || "";
        const chunkIsReasoning = rawData.is_reasoning === true;
        
        // 【新逻辑】只要收到 is_reasoning=false 的 chunk，就隐藏 thought
        const shouldHideThought = !chunkIsReasoning;
        
        // 更新 ref
        lastChunkIsReasoningRef.current = chunkIsReasoning;
        
        // 存入 step
        step.content = chunkContent;
        step.is_reasoning = chunkIsReasoning;
        
        responseBufferRef.current += chunkContent;
        setCurrentResponse(responseBufferRef.current);
        onShowSteps?.(false);
        
        const reasoning = rawData.reasoning || "";
        console.log("%c[sse.ts] 准备调用onChunk, isReasoning=", "color: #FF00FF", chunkIsReasoning);
        onChunk?.(chunkContent, chunkIsReasoning, reasoning);
        
        // 状态转换时：清除 thought，添加标记
        if (shouldHideThought) {
          const filteredSteps = executionSteps.filter(s => s.type !== "thought");
          const replyStep: ExecutionStep = {
            type: "chunk",
            content: "💬 LLM回复如下：",
            is_reasoning: false,
            timestamp: Date.now(),
          };
          setExecutionSteps([...filteredSteps, replyStep, step]);
        } else {
          setExecutionSteps([...executionSteps, step]);
        }
        
        onStep?.(step);
        break;
      }

      case "final": {
        // 后端实际返回 answer_content 字段
        step.content = rawData.answer_content || rawData.content || "";
        if (step.content) {
          if (!responseBufferRef.current) {
            responseBufferRef.current = step.content;
            setCurrentResponse(responseBufferRef.current);
            onChunk?.(step.content);
          }
        }

        const displayName = rawData.display_name;
        onComplete?.(responseBufferRef.current, {
          model: rawData.model,
          provider: rawData.provider,
          display_name: displayName,
        } as SSEMetadata);

        // 【小欧修复】不要在 final 时清空 executionSteps！
        // 让父组件自己决定何时清空（需要在保存到数据库之后再清空）
        // setExecutionSteps([]);
        
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case "error": {
        const errorMsg = rawData.message || "未知错误";
        step.content = errorMsg;
        step.error_message = errorMsg;
        if (rawData.code) {
          (step as any).code = rawData.code;
        }
        if (rawData.error_type) {
          (step as any).error_type = rawData.error_type;
        }
        // 【小查修复2026-03-10】添加设计文档要求的字段
        if (rawData.details) {
          (step as any).details = rawData.details;
        }
        if (rawData.stack) {
          (step as any).stack = rawData.stack;
        }
        if (rawData.retryable !== undefined) {
          (step as any).retryable = rawData.retryable;
        }
        if (rawData.retry_after !== undefined) {
          (step as any).retry_after = rawData.retry_after;
        }
        onError?.(errorMsg);
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      // 【小查修复2026-03-10】新增：status类型处理（后端发送type='status'，status_value字段）
      case "status": {
        const statusValue = rawData.status_value;
        const statusMessage = rawData.message || "";
        step.type = statusValue as ExecutionStep["type"];
        step.content = statusMessage;
        
        // 根据status_value调用对应的回调
        switch (statusValue) {
          case "interrupted":
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
            onRetry?.(statusMessage || "正在重试...");
            break;
          default:
            console.warn("[SSE] 未知的status_value:", statusValue);
        }
        break;
      }

      case "interrupted": {
        // 使用 message 填充 content
        step.content = step.message || "";
        onComplete?.(responseBufferRef.current, undefined);
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case "paused": {
        // 使用 message 填充 content
        step.content = step.message || "";
        onPaused?.();
        break;
      }

      case "resumed": {
        // 使用 message 填充 content
        step.content = step.message || "";
        onResumed?.();
        break;
      }

      // ⭐ 新增：重试状态处理
      case "retrying": {
        // 使用 message 填充 content
        step.content = step.message || "正在重试...";
        onRetry?.(step.message || "正在重试...");
        break;
      }
    }
  } catch (error) {
    console.error("[SSE] 解析数据失败:", error);
  }
};

export default useSSE;
