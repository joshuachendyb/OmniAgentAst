/**
 * NewChatContainer 改进版 V2
 * 
 * 改进内容：
 * 1. 抽离重试逻辑为独立函数
 * 2. 错误消息友好化
 * 3. 加载状态指示器
 * 4. 保存状态管理
 * 
 * @author 小新
 * @version 3.2.0
 * @since 2026-03-04
 */

import React, { useState, useRef, useEffect, useCallback } from "react";
import {
  Input,
  Button,
  Card,
  List,
  Tag,
  Space,
  message,
  Badge,
  Tooltip,
} from "antd";
import {
  SendOutlined,
  RobotOutlined,
  PlusOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ThunderboltOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  InfoCircleOutlined,
  LockOutlined,
  LoadingOutlined,
} from "@ant-design/icons";
import { useSearchParams } from "react-router-dom";
import { sessionApi, ChatMessage, API_BASE_URL } from "../../services/api";
import { securityApi } from "../../services/api";
import MessageItem from "./MessageItem";
import DangerConfirmModal from "../DangerConfirmModal";
import SecurityAlert from "../SecurityAlert";
import { showSecurityNotification } from "../SecurityNotification";
import { getRiskLevel } from "../../types/security";
import { useSSE, ExecutionStep } from "../../utils/sse";

const { TextArea } = Input;

// 常量配置
const SESSION_EXPIRY_TIME = 5 * 60 * 1000; // 5分钟

// 保存状态类型
type SaveStatus = "idle" | "saving" | "saved" | "error";

// 错误类型分类
type ErrorType = "network" | "timeout" | "server" | "unknown";

/**
 * 分类错误类型
 */
const classifyError = (errorMsg: string): ErrorType => {
  if (!errorMsg) return "unknown"; // 【修复小查问题】添加空值检查
  if (errorMsg.includes("timeout") || errorMsg.includes("超时")) return "timeout";
  if (errorMsg.includes("fetch") || errorMsg.includes("network") || errorMsg.includes("网络")) return "network";
  if (errorMsg.includes("HTTP") || errorMsg.includes("500") || errorMsg.includes("服务器")) return "server";
  return "unknown";
};

/**
 * 获取友好的错误消息
 */
const getFriendlyErrorMessage = (errorType: ErrorType): string => {
  switch (errorType) {
    case "timeout":
      return "请求超时，请检查网络或稍后重试";
    case "network":
      return "网络连接失败，请检查网络后重试";
    case "server":
      return "服务器繁忙，请稍后重试";
    default:
      return "响应失败，请稍后重试";
  }
};

/**
 * 保存AI回复（抽离为独立函数）
 */
const saveAIResponse = async (
  sessionId: string,
  finalResponse: string,
  onSuccess?: () => void,
  onError?: (error: any) => void
): Promise<boolean> => {
  // 【修复小查问题】参数验证
  if (!sessionId || !finalResponse) {
    console.error("保存失败：缺少必要参数");
    message.error("保存失败，请刷新页面重试");
    onError?.(new Error("缺少参数"));
    return false;
  }
  
  const maxRetries = 3;
  let retryCount = 0;
  
  while (retryCount < maxRetries) {
    try {
      retryCount++;
      await sessionApi.saveMessage(sessionId, {
        role: "assistant",
        content: finalResponse,
      });
      onSuccess?.();
      return true;
    } catch (error: any) {
      // 检查是否是409版本冲突
      if (error?.response?.status === 409) {
        message.error("会话数据冲突，请刷新页面");
        onError?.(error);
        return false;
      }
      
      if (retryCount < maxRetries) {
        message.warning({
          content: `保存失败，${maxRetries - retryCount}秒后重试...`,
          duration: 1.5,
        });
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
    }
  }
  
  // 达到最大重试次数，尝试本地缓存
  message.error("保存失败，已暂存到本地");
  // 【修复小查问题】添加本地缓存清理机制（保留24小时内）
  try {
    const cacheKey = `unsaved_ai_responses_${sessionId}`;
    const cached = JSON.parse(localStorage.getItem(cacheKey) || "[]");
    // 清理24小时前的旧数据
    const validCache = cached.filter(
      (item: any) => Date.now() - item.timestamp < 24 * 60 * 60 * 1000
    );
    validCache.push({ assistant: finalResponse, timestamp: Date.now() });
    localStorage.setItem(cacheKey, JSON.stringify(validCache));
  } catch {
    console.error("本地缓存失败");
  }
  
  onError?.(new Error("保存失败"));
  return false;
};

interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
  executionSteps?: ExecutionStep[];
  isStreaming?: boolean;
  isError?: boolean;
  errorType?: string;
  model?: string;
  provider?: string;
  displayName?: string;
}

const NewChatContainer: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pendingMessage, setPendingMessage] = useState<string | null>(null);
  const [isFinished, setIsFinished] = useState(false);
  const [editingTitle, setEditingTitle] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentSessionIdRef = useRef<string | null>(null);
  const pendingMessageRef = useRef<string | null>(null);
  const isNetworkOk = useRef(true);

  // SSE 相关
  const {
    isConnected,
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage,
    disconnect,
    clearSteps,
    serverTaskId,
    setTaskId,
    setServerTaskId,
    reconnectStatus,
  } = useSSE(
    { baseURL: API_BASE_URL, sessionId: sessionId || "" },
    handleStep,
    handleChunk,
    handleComplete,
    handleError
  );

  /**
   * 处理执行步骤
   */
  function handleStep(step: ExecutionStep) {
    console.log("🔍 onStep 收到步骤:", step.type);
    
    if (step.type === "start") {
      // 创建新的AI消息
      const newMessage: Message = {
        id: `msg_${Date.now()}`,
        role: "assistant",
        content: step.content || "🤔 AI 正在思考...",
        timestamp: new Date(),
        isStreaming: true,
        model: step.model,
        provider: step.provider,
        displayName: step.displayName || step.display_name,
      };
      
      setMessages((prev) => [...prev, newMessage]);
    } else if (step.type === "thought" || step.type === "action" || step.type === "observation") {
      // 更新最后一条消息
      setMessages((prev) => {
        const updated = [...prev];
        const lastMessage = updated[updated.length - 1];
        if (lastMessage && lastMessage.role === "assistant") {
          updated[updated.length - 1] = {
            ...lastMessage,
            executionSteps: [...(lastMessage.executionSteps || []), step],
          };
        }
        return updated;
      });
    }
  }

  /**
   * 处理内容片段
   */
  function handleChunk(chunk: string) {
    setMessages((prev) => {
      const updated = [...prev];
      const lastMessage = updated[updated.length - 1];
      if (lastMessage && lastMessage.role === "assistant") {
        updated[updated.length - 1] = {
          ...lastMessage,
          content: lastMessage.content + chunk,
        };
      }
      return updated;
    });
  }

  /**
   * 处理完成
   */
  const handleComplete = useCallback(
    async (fullResponse: string, metadata?: any) => {
      const currentSessionId = currentSessionIdRef.current || sessionId;
      
      if (currentSessionId && fullResponse) {
        setSaveStatus("saving");
        
        // 使用改进的保存函数
        await saveAIResponse(
          currentSessionId,
          fullResponse,
          () => {
            setSaveStatus("saved");
            setTimeout(() => setSaveStatus("idle"), 3000);
          },
          () => {
            setSaveStatus("error");
            // 【修复小查问题】5秒后自动恢复idle状态
            setTimeout(() => setSaveStatus("idle"), 5000);
          }
        );
      }
      
      setLoading(false);
      setIsFinished(true);
    },
    [sessionId]
  );

  /**
   * 处理错误
   */
  const handleError = useCallback(
    (error: string | { type: string; message: string; model?: string; provider?: string }) => {
      const errorObj = typeof error === "string" 
        ? { type: "unknown", message: error } 
        : error;
      
      // 分类错误并获取友好消息
      const errorType = classifyError(errorObj.message);
      const friendlyMessage = getFriendlyErrorMessage(errorType, errorObj.message);
      
      // 显示友好错误消息
      message.error({
        content: friendlyMessage,
        duration: 4,
      });
      
      setLoading(false);
    },
    []
  );

  // 自动滚动
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentResponse]);

  // 加载会话
  const loadSession = useCallback(async () => {
    // ... 省略，保留原有逻辑
  }, []);

  // 发送消息
  const handleSend = useCallback(async () => {
    if (!inputValue.trim() || loading) return;
    
    // 检查网络
    if (!isNetworkOk.current) {
      message.warning("网络不可用，请检查网络连接");
      return;
    }

    // ... 省略，保留原有逻辑
  }, [inputValue, loading]);

  // 渲染保存状态指示器
  const renderSaveStatusIndicator = () => {
    switch (saveStatus) {
      case "saving":
        return <Tag icon={<LoadingOutlined />} color="processing">保存中...</Tag>;
      case "saved":
        return <Tag icon={<span>✓</span>} color="success">已保存</Tag>;
      case "error":
        return <Tag icon={<span>⚠</span>} color="error">保存失败</Tag>;
      default:
        return null;
    }
  };

  // 渲染连接状态指示器
  const renderConnectionStatus = () => {
    if (loading) {
      if (reconnectStatus === "reconnecting") {
        return <Tag color="warning">重连中...</Tag>;
      }
      return <Tag icon={<LoadingOutlined />} color="processing">AI思考中</Tag>;
    }
    if (isConnected) {
      return <Tag color="success">已连接</Tag>;
    }
    return null;
  };

  return (
    <div className="new-chat-container">
      <div className="chat-messages">
        {messages.map((msg) => (
          <MessageItem key={msg.id} message={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>
      
      <div className="chat-input-area">
        <div className="status-indicators">
          {renderConnectionStatus()}
          {renderSaveStatusIndicator()}
        </div>
        <Space.Compact style={{ width: "100%" }}>
          <TextArea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onPressEnter={(e) => {
              if (!e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="输入消息，Shift+Enter 换行"
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={loading}
          />
          <Button
            type="primary"
            icon={<SendOutlined />}
            onClick={handleSend}
            loading={loading}
          >
            发送
          </Button>
        </Space.Compact>
      </div>
    </div>
  );
};

export default NewChatContainer;
