/**
 * SSE工具模块 - Server-Sent Events流式处理
 *
 * 功能：建立SSE连接、接收流式数据、处理执行步骤
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-02-17
 */

import { useState, useCallback, useRef, useEffect } from "react";
import { message } from "antd";

/**
 * 执行步骤类型
 */
export interface ExecutionStep {
  /** 步骤类型 */
  type:
    | "thought"
    | "action"
    | "observation"
    | "final"
    | "error"
    | "interrupted"
    | "chunk"
    | "start";
  /** 步骤内容 */
  content?: string;
  /** 工具名称 */
  tool?: string;
  /** 工具参数 */
  params?: Record<string, any>;
  /** action参数（action_input） - 前端小新代修改 */
  action_input?: Record<string, any>;
  /** 执行结果 */
  result?: any;
  /** observation（观察结果） - 前端小新代修改 */
  observation?: any;
  /** 时间戳 */
  timestamp: number;
  /** 步骤序号 */
  stepNumber?: number;
  /** 模型名称 - 前端小新代修改 */
  model?: string;
  /** 关联的内容起始位置 - 前端小新代修改：用于追溯思考过程 */
  contentStart?: number;
  /** 关联的内容结束位置 - 前端小新代修改：用于追溯思考过程 */
  contentEnd?: number;
}

/**
 * 流式消息类型
 */
export interface StreamMessage {
  /** 消息类型 */
  type: "start" | "step" | "chunk" | "complete" | "error";
  /** 消息数据 */
  data?: ExecutionStep | string;
  /** 完整消息ID */
  messageId?: string;
  /** 错误信息 */
  error?: string;
}

/**
 * SSE连接配置
 */
export interface SSEConfig {
  /** API基础URL */
  baseURL: string;
  /** 会话ID */
  sessionId: string;
  /** 认证Token */
  token?: string;
  /** 任务ID（用于中断） */
  taskId?: string;
}

/**
 * SSE Hook返回值
 */
export interface UseSSEReturn {
  /** 是否连接中 */
  isConnected: boolean;
  /** 是否正在接收 */
  isReceiving: boolean;
  /** 执行步骤列表 */
  executionSteps: ExecutionStep[];
  /** 当前AI回复内容 */
  currentResponse: string;
  /** 发送消息 */
  sendMessage: (content: string) => void;
  /** 断开连接 */
  disconnect: () => void;
  /** 清空步骤 */
  clearSteps: () => void;
  /** 设置任务ID - 前端小新代修改 */
  setTaskId: (taskId: string) => void;
  /** 后端返回的任务ID - 前端小新代修改 */
  serverTaskId?: string | null;
  /** 设置后端返回的任务ID - 前端小新代修改 */
  setServerTaskId?: (taskId: string) => void;
}

/**
 * SSE Hook - 用于组件中流式通信
 *
 * @param config - SSE配置
 * @param onStep - 执行步骤回调
 * @param onChunk - 消息片段回调
 * @param onComplete - 完成回调
 * @param onError - 错误回调
 * @returns SSE控制对象
 */
export const useSSE = (
  config: SSEConfig,
  onStep?: (step: ExecutionStep) => void,
  onChunk?: (chunk: string) => void,
  onComplete?: (fullResponse: string, model?: string) => void,
  onError?: (error: string) => void
): UseSSEReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isReceiving, setIsReceiving] = useState(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const [currentResponse, setCurrentResponse] = useState("");

  const eventSourceRef = useRef<EventSource | null>(null);
  const responseBufferRef = useRef("");
  const isProcessingRef = useRef(false);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [serverTaskId, setServerTaskId] = useState<string | null>(null);

  /**
   * 断开连接
   */
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setIsConnected(false);
    setIsReceiving(false);
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
   * 发送消息建立SSE连接（使用fetch + ReadableStream，支持POST请求）
   *
   * 【修复】EventSource只支持GET请求，无法向后端发送message参数
   * 改用fetch + ReadableStream，支持POST请求和流式数据解析
   */
  const sendMessage = useCallback(
    async (content: string) => {
      console.log("[SSE sendMessage] 函数被调用, content:", content);
      // 断开已有连接
      disconnect();
      clearSteps();

      setIsReceiving(true);
      setIsConnected(true);

      try {
        // 构建请求 - 使用POST方法，message放在body中
        const url = `${config.baseURL}/chat/stream`;

        // 使用AbortController支持取消
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 60000); // 60秒超时

        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(config.token
              ? { Authorization: `Bearer ${config.token}` }
              : {}),
          },
          body: JSON.stringify({
            messages: [{ role: "user", content: content }],
            stream: true,
            task_id: taskId || undefined,
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

        // 使用ReadableStream读取流式数据
        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        let buffer = "";

        console.log("[SSE] 开始接收流式数据...");

        // eslint-disable-next-line no-constant-condition
        while (true) {
          const { done, value } = await reader.read();

          if (done) {
            // 处理剩余的buffer数据
            if (buffer.trim()) {
              processSSEData(
                buffer,
                {
                  setExecutionSteps,
                  onStep,
                  onChunk,
                  onComplete,
                  onError,
                  setCurrentResponse,
                  responseBufferRef,
                  setIsReceiving,
                  setIsConnected,
                  disconnect,
                  setServerTaskId,
                },
                isProcessingRef
              );
            }
            console.log("[SSE] 流式接收完成");
            break;
          }

          // 解码数据块
          buffer += decoder.decode(value, { stream: true });

          // 按行分割，处理SSE格式
          const lines = buffer.split("\n");
          buffer = lines.pop() || ""; // 保留最后一个不完整的行

          for (const line of lines) {
            processSSEData(
              line,
              {
                setExecutionSteps,
                onStep,
                onChunk,
                onComplete,
                onError,
                setCurrentResponse,
                responseBufferRef,
                setIsReceiving,
                setIsConnected,
                disconnect,
                setServerTaskId,
              },
              isProcessingRef
            );
          }
        }
      } catch (error: any) {
        console.error("[SSE] 请求错误:", error);
        setIsConnected(false);
        setIsReceiving(false);

        if (error.name === "AbortError") {
          message.warning("请求超时");
          onError?.("请求超时");
        } else {
          message.error(`连接异常: ${error.message}`);
          onError?.(error.message);
        }
      }
    },
    [config, disconnect, clearSteps, onStep, onChunk, onComplete, onError]
  );

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      disconnect();
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
  };
};
/**
 * 处理单行SSE数据
 *
 * 解析后端的SSE格式数据，触发相应的回调
 * 支持6种事件类型：thought/action/observation/final/error/interrupted
 */
const processSSEData = (
  line: string,
  handlers: {
    setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string) => void;
    onComplete?: (fullResponse: string, model?: string) => void;
    onError?: (error: string) => void;
    setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
    responseBufferRef: React.MutableRefObject<string>;
    setIsReceiving: React.Dispatch<React.SetStateAction<boolean>>;
    setIsConnected: React.Dispatch<React.SetStateAction<boolean>>;
    disconnect: () => void;
    setServerTaskId?: (taskId: string) => void;
  },
  // 前端小新代修改 VIS-S02: 修复 ESLint 未使用参数警告
  // 原因: 原参数 isProcessingRef 未被使用，但函数调用处仍传入该参数
  // 解决: 在参数名前加下划线 _ 表示故意未使用，保持函数签名兼容
  _isProcessingRef: React.MutableRefObject<boolean>
) => {
  const {
    setExecutionSteps,
    onStep,
    onChunk,
    onComplete,
    onError,
    setCurrentResponse,
    responseBufferRef,
    setIsReceiving,
    setIsConnected,
    disconnect,
    setServerTaskId,
  } = handlers;

  // 跳过空行
  if (!line.trim() || !line.startsWith("data: ")) {
    return;
  }

  try {
    // 解析 SSE 数据（去掉 "data: " 前缀）
    const rawData = JSON.parse(line.slice(6));

    console.log("[SSE] 收到数据:", rawData.type, rawData);

    // 构建 ExecutionStep 对象
    const step: ExecutionStep = {
      type: rawData.type as ExecutionStep["type"],
      content: rawData.content || rawData.error || "",
      tool: rawData.action, // action 作为工具名
      params: rawData.action_input, // action_input 作为参数
      result: rawData.observation, // observation 作为结果
      timestamp: Date.now(),
      stepNumber: rawData.step || 1,
    };

    switch (rawData.type) {
      case "start": {
        // 【修复问题 7】收到 start 事件，保存后端返回的所有信息
        console.log("[SSE] 收到 start 事件:", rawData);
        if (rawData.task_id && setServerTaskId) {
          setServerTaskId(rawData.task_id);
        }
        // 【修复问题 7】保存 model、provider 和 display_name 信息
        if (rawData.model) {
          (responseBufferRef.current as any)._model = rawData.model;
        }
        if (rawData.provider) {
          (responseBufferRef.current as any)._provider = rawData.provider;
        }
        if (rawData.display_name) {
          (responseBufferRef.current as any)._displayName = rawData.display_name;
        }
        // 【修复问题 7】发送 start 步骤，用于创建占位消息
        const startStep: ExecutionStep = {
          type: "start",
          content: "🤔 AI 正在思考...",
          timestamp: Date.now(),
          model: rawData.model,
          provider: rawData.provider,
        };
        setExecutionSteps((prev) => [...prev, startStep]);
        onStep?.(startStep);
        break;
      }

      case "thought":
        // 思考步骤
        console.log("[SSE] 思考:", step.content);
        // 【修复问题 3】添加内容位置信息
        step.contentStart = responseBufferRef.current.length;
        step.contentEnd = step.contentStart;
        setExecutionSteps((prev) => [...prev, step]);
        onStep?.(step);
        break;

      case "action":
        // 行动步骤
        console.log("[SSE] 行动:", step.content);
        // 【修复问题 3】添加内容位置信息
        step.contentStart = responseBufferRef.current.length;
        step.contentEnd = step.contentStart;
        setExecutionSteps((prev) => [...prev, step]);
        onStep?.(step);
        break;

      case "observation":
        // 观察结果 - 包含 ReAct 三要素
        console.log("[SSE] 观察:", step.result);
        // 【修复问题 3】添加内容位置信息
        step.contentStart = responseBufferRef.current.length;
        step.contentEnd = step.contentStart;
        setExecutionSteps((prev) => [...prev, step]);
        onStep?.(step);
        break;

      case "chunk": {
        // 流式内容片段 - 逐 token 返回
        console.log("[SSE] 内容片段:", rawData.content);
        const contentLength = (rawData.content || "").length;
        const contentStart = responseBufferRef.current.length;
        const contentEnd = contentStart + contentLength;
        responseBufferRef.current += rawData.content || "";
        setCurrentResponse(responseBufferRef.current);
        // 【修复问题 3】传递内容位置信息
        onChunk?.(rawData.content || "", contentStart, contentEnd);
        break;
      }
      case "final": {
        // 最终结果 - 前端小新代修改
        console.log("[SSE] 最终结果:", step.content);
        // 优化判断逻辑：优先使用后端返回的content，避免忽略有效内容
        if (step.content) {
          // 如果已有累积内容，不覆盖；如果没有，则用后端返回的
          if (!responseBufferRef.current) {
            responseBufferRef.current = step.content;
            setCurrentResponse(responseBufferRef.current);
            onChunk?.(step.content);
          }
        }
        // 获取model字段
        const model = rawData.model;
        console.log("[SSE] 当前模型:", model);
        console.log("[SSE] 准备调用onComplete, model:", model);
        setIsReceiving(false);
        setIsConnected(false);
        disconnect();
        if (onComplete) {
          console.log("[SSE] onComplete存在，调用它");
          onComplete(responseBufferRef.current, model);
        } else {
          console.log("[SSE] onComplete不存在！");
        }
        break;
      }
      case "interrupted": {
        // 中断
        setIsReceiving(false);
        setIsConnected(false);
        disconnect();
        const interruptMsg = step.content || "任务被中断";
        message.warning(interruptMsg);
        onError?.(interruptMsg);
        console.log("[SSE] 中断:", interruptMsg);
        break;
      }
      case "error": {
        // 错误
        setIsReceiving(false);
        setIsConnected(false);
        disconnect();
        const errorMsg = step.content || "未知错误";
        message.error(`流式传输错误: ${errorMsg}`);
        onError?.(errorMsg);
        console.error("[SSE] 错误:", errorMsg);
        break;
      }

      default:
        console.log("[SSE] 未知类型:", rawData.type);
    }
  } catch (err) {
    console.error(
      "[SSE] 解析数据失败:",
      err,
      "原始内容:",
      line,
      "行长度:",
      line.length
    );
  }
};

/**
 * 创建SSE连接（非Hook方式）
 *
 * @param url - SSE端点URL
 * @param handlers - 事件处理器
 * @returns EventSource实例
 */
export const createSSEConnection = (
  url: string,
  handlers: {
    onOpen?: () => void;
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string) => void;
    onComplete?: (fullResponse: string, model?: string) => void;
    onError?: (error: string) => void;
    onClose?: () => void;
  }
): EventSource => {
  const eventSource = new EventSource(url);
  let responseBuffer = "";

  eventSource.onopen = () => {
    console.log("[SSE] 连接已建立");
    handlers.onOpen?.();
  };

  eventSource.onmessage = (event) => {
    try {
      const data: StreamMessage = JSON.parse(event.data);

      switch (data.type) {
        case "start":
          console.log("[SSE] 开始接收:", data.messageId);
          break;

        case "step":
          if (data.data && typeof data.data === "object") {
            handlers.onStep?.(data.data as ExecutionStep);
          }
          break;

        case "chunk":
          if (typeof data.data === "string") {
            responseBuffer += data.data;
            handlers.onChunk?.(data.data);
          }
          break;

        case "complete":
          eventSource.close();
          handlers.onComplete?.(responseBuffer);
          handlers.onClose?.();
          console.log("[SSE] 接收完成");
          break;

        case "error":
          eventSource.close();
          handlers.onError?.(data.error || "未知错误");
          handlers.onClose?.();
          console.error("[SSE] 错误:", data.error);
          break;
      }
    } catch (err) {
      console.error("[SSE] 解析消息失败:", err);
    }
  };

  eventSource.onerror = (error) => {
    console.error("[SSE] 连接错误:", error);
    handlers.onError?.("连接错误");
    handlers.onClose?.();
    eventSource.close();
  };

  return eventSource;
};

/**
 * 解析执行步骤内容
 *
 * @param step - 执行步骤
 * @returns 格式化后的显示文本
 */
export const formatExecutionStep = (step: ExecutionStep): string => {
  switch (step.type) {
    case "thought":
      return step.content || "思考中...";
    case "action":
      if (step.tool) {
        return `执行工具: ${step.tool}${
          step.params ? `(${JSON.stringify(step.params)})` : ""
        }`;
      }
      return step.content || "执行动作...";
    case "observation":
      return step.result
        ? `观察结果: ${JSON.stringify(step.result)}`
        : step.content || "观察中...";
    case "final":
      return step.content || "任务完成";
    case "error":
      return `错误: ${step.content || "未知错误"}`;
    default:
      return step.content || "";
  }
};

export default useSSE;
