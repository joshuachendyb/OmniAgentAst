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
  displayName?: string;
}

/**
 * 执行步骤类型 - 与后端字段完全对应，便于调试和理解
 */
export interface ExecutionStep {
  // === 通用字段 ===
  type: "thought" | "action" | "observation" | "chunk" | "final" | "error" | "interrupted" | "start" | "paused" | "resumed";
  content?: string;        // 思考内容/错误信息（type=thought/observation/final都有）
  
  // === type=action/observation 字段 ===
  step?: number;          // 步骤序号（type=action/observation有）—— 与后端一致
  thought?: string;       // Agent.thought的值（type=observation有）
  action?: string;        // Agent.action的值，执行动作名称（如"read_file"）
  observation?: any;      // Agent.observation原始对象（保留，用于调试）
  tool?: string;          // = action，与后端保持一致
  result?: string;        // simplify_observation处理后的文本（显示用这个，不要用observation！）
  
  // === type=action 字段 ===
  action_input?: Record<string, any>;  // 工具调用参数
  
  // === type=chunk/final/start 字段 ===
  model?: string;         // AI模型
  provider?: string;      // AI提供商
  display_name?: string;  // 显示名称
  displayName?: string;   // 兼容字段
  
  // === type=chunk 新增：思考过程字段 ===
  is_reasoning?: boolean;  // 是否是思考过程
  reasoning?: string;       // 思考过程内容

  // === type=error 字段 ===
  error?: string;         // 错误信息
  
  // === 前端额外字段 ===
  timestamp: number;      // 前端生成的时间戳
  contentStart?: number;  // content起始位置（用于流式定位）
  contentEnd?: number;    // content结束位置
}

/**
 * 流式消息类型
 */
export interface StreamMessage {
  type: "start" | "step" | "chunk" | "complete" | "error";
  data?: ExecutionStep | string;
  messageId?: string;
  error?: string;
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
  onShowSteps?: (show: boolean) => void  // 新增：控制步骤显示/隐藏
): UseSSEReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isReceiving, setIsReceiving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
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
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
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
              onStep,
              onChunk,
              onComplete,
              onError,
              onPaused,
              onResumed,
              onShowSteps,
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
            onStep,
            onChunk,
            onComplete,
            onError,
            onPaused,
            onResumed,
            onShowSteps,
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
      
      await sendMessageInternal(content, sessionId);
      
      // 请求结束后重置
      isProcessingRef.current = false;
    },
    [config, disconnect, clearSteps, onStep, onChunk, onComplete, onError]
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
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string, isReasoning?: boolean, reasoning?: string) => void;
    onComplete?: (fullResponse: string, model?: string) => void;
    onError?: (error: string) => void;
    onPaused?: () => void;
    onResumed?: () => void;
    onShowSteps?: (show: boolean) => void;
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
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onShowSteps,
    setCurrentResponse,
    responseBufferRef,
    setIsReceiving,
    setIsConnected,
    disconnect,
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
      content: rawData.content || rawData.error || "",
      step: rawData.step || 1,           // 与后端一致：step
      thought: rawData.thought,          // Agent.thought的值
      action: rawData.action,            // 执行动作名称，与后端一致
      observation: rawData.observation,  // 保留原始对象，用于调试
      tool: rawData.tool || rawData.action,  // = action
      result: rawData.result,            // simplify_observation处理后的文本（显示用这个！）
      action_input: rawData.action_input, // 工具调用参数
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
          displayName: displayName,
          display_name: displayName,
        };

        setExecutionSteps((prev) => [...prev, startStep]);
        onStep?.(startStep);
        break;
      }

      case "thought":
      case "action":
      case "observation": {
        step.contentStart = responseBufferRef.current.length;
        step.contentEnd = step.contentStart;
        setExecutionSteps((prev) => [...prev, step]);
        onStep?.(step);
        break;
      }

      case "chunk": {
        responseBufferRef.current += rawData.content || "";
        setCurrentResponse(responseBufferRef.current);
        // 【小沈修复】收到chunk时关闭步骤UI，开始显示回复内容
        onShowSteps?.(false);
        // 传递 is_reasoning 和 reasoning 区分思考过程和最终答案
        onChunk?.(rawData.content || "", rawData.is_reasoning || false, rawData.reasoning || "");
        break;
      }

      case "final": {
        if (step.content) {
          if (!responseBufferRef.current) {
            responseBufferRef.current = step.content;
            setCurrentResponse(responseBufferRef.current);
            onChunk?.(step.content);
          }
        }

        const displayName = rawData.display_name || rawData.displayName;
        onComplete?.(responseBufferRef.current, {
          model: rawData.model,
          provider: rawData.provider,
          displayName,
        } as SSEMetadata);

        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case "error": {
        const errorMsg = rawData.content || rawData.error || "未知错误";
        onError?.(errorMsg);
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case "interrupted": {
        onComplete?.(responseBufferRef.current, undefined);
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case "paused": {
        onPaused?.();
        break;
      }

      case "resumed": {
        onResumed?.();
        break;
      }
    }
  } catch (error) {
    console.error("[SSE] 解析数据失败:", error);
  }
};

export default useSSE;
