/**
 * NewChatContainer组件 - 升级版对话容器
 *
 * 功能：
 * - 完整会话管理（新建会话、编辑标题、历史记录加载）
 * - SSE流式输出 + 执行步骤可视化
 * - 安全检测v2.0（基于score的4级响应）
 * - 任务中断控制
 * - 标题管理优化（版本控制、锁定状态、来源标记）
 *
 * @author 小新
 * @version 3.1.0
 * @since 2026-02-23
 * @update 2026-02-25 新增版本号控制、标题锁定状态、409冲突处理
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

// ⭐ 常量配置
const SESSION_EXPIRY_TIME = 5 * 60 * 1000; // 5分钟

// ⭐ 防抖函数（简单实现，不依赖lodash）
const debounce = <T extends (...args: any[]) => any>(
  func: T,
  delay: number
): ((...args: Parameters<T>) => void) => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return (...args: Parameters<T>): void => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
      timeoutId = null;
    }, delay);
  };
};

interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
  executionSteps?: ExecutionStep[];
  isStreaming?: boolean;
  isError?: boolean; // 前端小新代修改：是否为错误消息
  errorType?: string; // 前端小新代修改：错误类型
  model?: string;
  provider?: string; // 前端小新代修改：提供商
  display_name?: string; // 前端小新代修改：显示名称（如"OpenAI (GPT-4)"）
  is_reasoning?: boolean; // 【小沈修复】是否为思考过程（用于样式区分）
}

/**
 * NewChatContainer - 升级版对话容器
 *
 * 整合功能：
 * - Chat/index.tsx: 会话管理、安全检测、状态持久化
 * - ChatContainer: useSSE hook、ExecutionPanel、流式开关
 *
 * @author 小新
 * @version 3.0.0
 */
const NewChatContainer: React.FC = () => {
  const [searchParams] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [loading, setLoading] = useState(false);
  // ⭐ 新增：等待时间计时器（正计时）
  const [waitTime, setWaitTime] = useState(0);
  const waitTimerRef = useRef<number | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);  // ⭐ 新增：重试状态
  const [isPaused, setIsPaused] = useState(false);
  const [currentTaskId, setCurrentTaskId] = useState<string | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessionTitle, setSessionTitle] = useState<string>("新会话");
  const [sessionVersion, setSessionVersion] = useState<number>(1); // ⭐ 新增：会话版本号
  const [titleLocked, setTitleLocked] = useState<boolean>(false); // ⭐ 新增：标题锁定状态
  // 【小新第二修复 2026-03-02】title_source 是后端根据 title_locked 动态计算的，
  // 不需要前端维护状态，直接使用 titleLocked 即可
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleInput, setTitleInput] = useState("");
  const [lastSavedTitle, setLastSavedTitle] = useState<string>(""); // ⭐ 新增：记录最后保存的标题
  const messagesEndRef = useRef<HTMLDivElement>(null);
  // 【小新第二修复 2026-03-02】用于保存当前会话ID，确保onComplete时使用正确的ID
  const currentSessionIdRef = useRef<string | null>(null);
  // 【小新第二修复 2026-03-02】用于同步跟踪消息数量，确保保存时能获取准确值
  const messagesCountRef = useRef<number>(0);
  // 【小新第三修复 2026-03-02】用于同步存储pendingMessage，解决React闭包陷阱
  const pendingMessageRef = useRef<Message | null>(null);

  // ⭐ 暂停功能缓冲区：暂存暂停期间接收的数据
  const displayBufferRef = useRef<any[]>([]);
  // ⭐ 暂停状态ref，用于在回调中同步访问
  const isPausedRef = useRef(false);

  // 流式输出相关状态
  const [showExecution, setShowExecution] = useState(true);
  const [useStream, setUseStream] = useState(true); // 默认使用流式

  // 安全检测v2.0状态
  const [dangerModalVisible, setDangerModalVisible] = useState(false);
  const [dangerCommand, setDangerCommand] = useState("");
  const [dangerScore, setDangerScore] = useState(0);
  const [dangerMessage, setDangerMessage] = useState("");
  const [pendingMessage, setPendingMessage] = useState<Message | null>(null);
  const [checkingDanger, setCheckingDanger] = useState(false);
  const [blockedCommand, setBlockedCommand] = useState<{
    command: string;
    score: number;
    message: string;
  } | null>(null);
  const [isInitialized, setIsInitialized] = useState(false);

  // P1级别优化：新增状态变量
  type SaveStatus = "idle" | "saving" | "saved" | "error";
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const [_sessionJumpLoading, setSessionJumpLoading] = useState(false);
  const [retryCount, setRetryCount] = useState<Record<string, number>>({});
  const [_lastSaveTime, setLastSaveTime] = useState<number>(0);
  const [_isSavingTitle, setIsSavingTitle] = useState(false);

  // SSE Hook配置（用于流式输出）
  const {
    isReceiving,
    executionSteps,
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
    setTaskId,
    serverTaskId,
  } = useSSE(
    {
      baseURL: "http://localhost:8000/api/v1",
      sessionId: sessionId || "default-session",
    },
    // onStep - 收到执行步骤
    useCallback((step: ExecutionStep) => {
      // ⭐ 暂停时存入缓冲区，不直接显示
      if (isPausedRef.current) {
        console.log("⏸️ [onStep] 暂停中，存入缓冲区, type:", step.type);
        displayBufferRef.current.push({ type: "step", step });
        return;
      }
      
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        // 【修复问题 7】如果是 start 步骤，创建占位消息
        if (step.type === "start") {
          console.log("🔍 onStep 收到 start 事件: step=", JSON.stringify(step, null, 2));
          console.log("🔍 step.display_name 值:", step.display_name);
          console.log("🔍 step.display_name 值:", step.display_name);
          console.log("🔍 step.model 值:", step.model);
          console.log("🔍 step.provider 值:", step.provider);
          
          // 检查是否已有消息
          if (!lastMessage || lastMessage.role !== "assistant") {
            // 提取display_name
            const extractedDisplay_name = step.display_name;
            console.log("🔍 提取的display_name:", extractedDisplay_name);
            
            // 如果 extractedDisplay_name 为空，尝试从其他字段构建
            let finalDisplay_name = extractedDisplay_name;
            if (!finalDisplay_name && step.model && step.provider) {
              finalDisplay_name = `${step.provider} (${step.model})`;
              console.log("🔍 从model/provider构建display_name:", finalDisplay_name);
            }
            
            const newAssistantMessage: Message = {
              id: (Date.now() + 1).toString(),
              role: "assistant",
              content: step.content || "🤔 AI 正在思考...",
              timestamp: new Date(),
              executionSteps: [step],
              isStreaming: true,  // 确保是 true
              model: step.model,
              provider: step.provider,
              display_name: finalDisplay_name, // 直接使用后端返回的 display_name
            };
            console.log("🔍 创建新AI助手消息: display_name=", newAssistantMessage.display_name, "isStreaming=", newAssistantMessage.isStreaming);
            console.log("🔍 完整消息对象:", JSON.stringify(newAssistantMessage, null, 2));
            return [...prev, newAssistantMessage];
          } else {
            // 已有assistant消息，更新display_name
            console.log("🔍 已有assistant消息，更新display_name, 当前isStreaming=", lastMessage.isStreaming);
            // 提取display_name
            const extractedDisplay_name = step.display_name;
            let finalDisplay_name = extractedDisplay_name;
            if (!finalDisplay_name && step.model && step.provider) {
              finalDisplay_name = `${step.provider} (${step.model})`;
            }
            // 更新最后一条消息的display_name
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMessage,
              display_name: finalDisplay_name || lastMessage.display_name,
              model: step.model || lastMessage.model,
              provider: step.provider || lastMessage.provider,
            };
            console.log("🔍 更新后的display_name=", updated[updated.length - 1].display_name);
            return updated;
          }
        }
        // 普通步骤：追加到 executionSteps
        if (
          lastMessage &&
          lastMessage.role === "assistant" &&
          lastMessage.isStreaming
        ) {
          const updatedSteps = [...(lastMessage.executionSteps || []), step];
          const updated = [...prev];
          updated[updated.length - 1] = {
            ...lastMessage,
            executionSteps: updatedSteps,
          };
          return updated;
        }
        return prev;
      });
    }, []),
    // onChunk - 收到内容片段 【小沈修复】添加 isReasoning 参数支持思考过程样式区分
    useCallback((chunk: string, isReasoning?: boolean, reasoningContent?: string) => {
      console.log("🔍 [onChunk] 收到内容片段:", JSON.stringify(chunk).substring(0, 100), "isReasoning:", isReasoning);
      
      // ⭐ 暂停时存入缓冲区，不直接显示
      if (isPausedRef.current) {
        console.log("⏸️ [onChunk] 暂停中，存入缓冲区");
        displayBufferRef.current.push({ type: "chunk", content: chunk, isReasoning });
        return;
      }
      
      setMessages((prev) => {
        const lastMessage = prev[prev.length - 1];
        if (
          lastMessage &&
          lastMessage.role === "assistant" &&
          lastMessage.isStreaming
        ) {
          const updated = [...prev];
          // 【小沈修复】如果是思考过程，设置 is_reasoning 标记
          const newIsReasoning = isReasoning ? true : lastMessage.is_reasoning;
          updated[updated.length - 1] = {
            ...lastMessage,
            content: lastMessage.content + chunk,
            is_reasoning: newIsReasoning,
          };
          return updated;
        }
        return prev;
      });
    }, []),
    // onComplete - 流式完成 - 前端小新代修改：适配后端新格式
    useCallback(
      async (
        fullResponse: string,
        metadata?:
          | string
          | {
              model?: string;
              provider?: string;
              display_name?: string;
            }
      ) => {
        // ✅ 支持旧格式（model 字符串）和新格式（metadata 对象）
        const metadataObj =
          typeof metadata === "string" ? { model: metadata } : metadata || {};

        // 🔴 修复：处理 AI 返回空内容的情况
        let finalResponse = fullResponse;
        let isError = false;
        if (!finalResponse || !finalResponse.trim()) {
          finalResponse = "抱歉，我暂时无法回答这个问题。请您稍后再尝试，或者换个方式提问。";
          isError = true; // 标记为错误类型，以便显示红色样式
          console.warn("⚠️ AI 返回了空内容，已使用默认回复");
        }

        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === "assistant") {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMessage,
              content: finalResponse,
              isStreaming: false,
              isError: isError, // 传递错误标记
              model: metadataObj.model || lastMessage.model,
              provider: metadataObj.provider || lastMessage.provider,
              display_name: metadataObj.display_name || lastMessage.display_name,
            };
            return updated;
          }
          return prev;
        });

        // 保存AI回复到会话
        // 【小沈修复2026-03-03】现在只保存AI回复消息，用户消息已在发送前保存
        // 这样更加健壮，即使AI响应失败，用户消息也已保存
        const currentSessionId = currentSessionIdRef.current || sessionId;
        const currentPending = pendingMessageRef.current || pendingMessage;
        if (currentSessionId && finalResponse && finalResponse.trim()) {
          // 🔴 修复：添加详细的调试日志
          console.log("🔍 保存AI回复:");
          console.log("  ref中的sessionId:", currentSessionIdRef.current);
          console.log("  state中的sessionId:", sessionId);
          console.log("  最终使用的sessionId:", currentSessionId);
          console.log("  currentPending:", currentPending);
          console.log("  finalResponse length:", finalResponse.length);

          try {
            // 保存AI回复（API会自动处理消息计数）
            // 用户消息已在调用 /chat/stream 之前保存
            await sessionApi.saveMessage(currentSessionId, {
              role: "assistant",
              content: finalResponse,
              // 不传递 message_count，让后端自动处理
              // 不传递 display_name，后端从缓存自动获取（小沈优化 2026-03-03）
            });

            // ⭐ 【小新修复 2026-03-04】保存AI回复后不再调用 ensureTitlePersisted
            // 原因：标题应该在用户修改时立即保存，避免版本冲突
            // 如果需要同步最新数据，应该在用户修改标题时处理
            console.log("✅ AI回复保存成功");
          } catch (saveError) {
            console.error("保存AI回复或标题失败:", saveError);
            console.error("使用的sessionId:", currentSessionId);
            // 修复：正确的错误处理，重试保存AI回复
            let retryCount = 0;
            const maxRetries = 3;

            const retrySave = async () => {
              while (retryCount < maxRetries) {
                retryCount++;
                message.warning({
                  content: `保存AI回复失败，正在重试 (${retryCount}/${maxRetries})...`,
                  duration: 2,
                });
                await new Promise(resolve => setTimeout(resolve, 1000));

                try {
                  // 保存AI回复
                  await sessionApi.saveMessage(currentSessionId, {
                    role: "assistant",
                    content: finalResponse,
                    // 不传递 message_count，让后端自动处理
                  });

                  // ⭐ 【小新修复 2026-03-04】重试保存AI回复时也不再调用 ensureTitlePersisted
                  // 原因：标题应该在用户修改时立即保存，避免版本冲突
                  message.success("AI回复保存成功");
                  return;
                  } catch (error: any) {
                    // 检查是否是409版本冲突或其他错误
                   if (error?.response?.status === 409) {
                    message.error("会话数据冲突，请刷新页面");
                    break; // 版本冲突不重试
                  } else if (retryCount === maxRetries) {
                    message.error({
                      content: "AI回复保存失败，请刷新页面重试",
                      duration: 5,
                    });
                    // 本地缓存AI回复（防止丢失）
                    try {
                      const cacheKey = `unsaved_ai_responses_${currentSessionId}`;
                      const cached = JSON.parse(
                        localStorage.getItem(cacheKey) || "[]"
                      );
                      // 避免重复缓存
                       const exists = cached.some(
                        (msg: any) =>
                          msg.assistant === finalResponse
                      );
                      if (!exists) {
                        cached.push({
                          assistant: finalResponse,
                          timestamp: Date.now(),
                        });
                        localStorage.setItem(cacheKey, JSON.stringify(cached));
                        message.info("AI回复已暂存到本地");
                      }
                    } catch (cacheError) {
                      console.error("本地缓存失败:", cacheError);
                    }
                    break; // 达到最大重试次数
                  }
                }
              }
            };

            retrySave();
          }
        } else {
          console.warn("⚠️ 无法保存AI回复：缺少sessionId或fullResponse");
          console.log("  currentSessionId:", currentSessionId);
          console.log("  fullResponse exists:", !!fullResponse);
        }

         console.log("🔍 [onComplete] SSE流完成，设置loading=false");
         setLoading(false);
         // ⭐ 停止等待计时器
         if (waitTimerRef.current) {
           clearInterval(waitTimerRef.current);
           waitTimerRef.current = null;
         }
         setWaitTime(0);
         setIsRetrying(false);
         // 【小新第三修复 2026-03-02】清理ref和state
         pendingMessageRef.current = null; // 同步清理
         setPendingMessage(null); // 异步清理
         console.log("✅ [onComplete] 处理完成");
       },
      [sessionId, pendingMessage]
    ),
    // onError - 流式错误 - 前端小新代修改：适配后端新格式
    useCallback(
      (
        error:
          | string
          | {
              type: string;
              message: string;
              rawMessage: string;
              model?: string;
              provider?: string;
            }
      ) => {
        // ✅ 支持字符串和对象两种格式
        const errorObj =
          typeof error === "string"
            ? { type: "unknown_error", message: error, rawMessage: error }
            : error;

         console.error("🔴 [onError] SSE 流式错误:", errorObj);
         console.error("  错误类型:", errorObj.type);
         console.error("  错误消息:", errorObj.message);

         // 🔴 修复：更好的用户反馈
         message.error({
           content: `AI 响应失败：${errorObj.message}`,
           duration: 5,
         });

        setMessages((prev) => {
          const lastMessage = prev[prev.length - 1];
          if (lastMessage && lastMessage.role === "assistant") {
            const updated = [...prev];
            updated[updated.length - 1] = {
              ...lastMessage,
              content: lastMessage.content || `**错误**: ${errorObj.message}`,
              isError: true, // 前端小新代修改：标记为错误消息
              isStreaming: false,
              errorType: errorObj.type, // ✅ 保存错误类型
              model: errorObj.model, // ✅ 保存模型
              provider: errorObj.provider, // ✅ 保存提供商
            };
            return updated;
          }
           return prev;
         });
        console.log("🔍 [onError] 错误处理完成，设置loading=false");
        setLoading(false);
        // ⭐ 停止等待计时器
        if (waitTimerRef.current) {
          clearInterval(waitTimerRef.current);
          waitTimerRef.current = null;
        }
        setWaitTime(0);
        setIsRetrying(false);
        console.log("✅ [onError] 处理完成");
       },
       []
    ),
    // onPaused - 暂停事件
    useCallback(() => {
      console.log("⏸️ [onPaused] 收到暂停事件");
      setIsPaused(true);
    }, []),
    // onResumed - 恢复事件
    useCallback(() => {
      console.log("▶️ [onResumed] 收到恢复事件，缓冲区长度:", displayBufferRef.current.length);
      
      // 从缓冲区按顺序显示数据
      displayBufferRef.current.forEach(data => {
        if (data.type === "chunk" && data.content) {
          // 处理 chunk 类型
          setMessages((prev) => {
            const lastMessage = prev[prev.length - 1];
            if (lastMessage && lastMessage.role === "assistant" && lastMessage.isStreaming) {
              const updated = [...prev];
              updated[updated.length - 1] = {
                ...lastMessage,
                content: lastMessage.content + data.content,
              };
              return updated;
            }
            return prev;
          });
        } else if (data.type === "step" && data.step) {
          // 处理 step 类型 - 这里简单处理，实际可能需要更复杂的逻辑
          console.log("📦 [onResumed] 处理 step 数据:", data.step.type);
        }
      });
      
      displayBufferRef.current = []; // 清空缓冲区
      setIsPaused(false);
    }, []),
    // onShowSteps - 控制步骤显示/隐藏（收到chunk时关闭步骤UI）
    useCallback((show: boolean) => {
      console.log("👁️ [onShowSteps] 设置步骤显示状态:", show);
      setShowExecution(show);
    }, []),
    // ⭐ onRetry - 重试事件
    useCallback((message: string) => {
      console.log("🔄 [onRetry] 收到重试事件:", message);
      setIsRetrying(true);  // 设置重试状态
      // 重置计时器（重新开始计时）
      setWaitTime(0);
    }, [])
  );

  // 自动滚动到底部
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  // 滚动到底部的增强版本，确保页面渲染完成后再滚动
  const scrollToBottomDelayed = () => {
    setTimeout(() => {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 100); // 延迟100ms确保DOM更新完成
  };

  // ⭐ 同步 isPaused 状态到 ref，供回调中使用
  useEffect(() => {
    isPausedRef.current = isPaused;
  }, [isPaused]);

  useEffect(() => {
    scrollToBottom();
  }, [messages, currentResponse, executionSteps]);

  // 【小新第二修复 2026-03-02】同步跟踪消息数量，用于保存消息时获取准确的值
  useEffect(() => {
    messagesCountRef.current = messages.length;
  }, [messages]);

  // 当页面从隐藏状态变为显示时也自动滚动到底部
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        // 延迟滚动以确保内容已渲染
        scrollToBottomDelayed();
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [messages, currentResponse, executionSteps]);

  // 组件卸载前保存状态（用于路由切换场景）
  useEffect(() => {
    return () => {
      // 组件卸载时保存当前状态
      // 🔴 修复：使用useState的当前值，而不是ref（因为卸载时DOM已不存在）
      if (sessionId && messages.length > 0) {
        // 从messages数组中计算滚动位置：最后一条消息
        const scrollPosition = messages.length; // 保存消息数量作为滚动标记
        const state = {
          messages,
          sessionId,
          sessionTitle,
          timestamp: Date.now(),
          scrollPosition, // 保存消息数量，而不是DOM滚动位置
          shouldScrollToBottom: true, // 标记需要滚动到底部
        };
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        console.log(
          "💾 组件卸载前保存会话状态:",
          sessionId,
          "消息数:",
          messages.length
        );
      }
    };
  }, [sessionId, messages, sessionTitle]);

  // ============================================
  // 会话状态持久化
  // ============================================
  const STORAGE_KEY = "chat_session_state";

  const saveState = () => {
    // 🔴 修复：只要有会话ID就保存，即使消息为空
    if (sessionId) {
      const state = {
        messages,
        sessionId,
        sessionTitle,
        timestamp: Date.now(),
        scrollPosition: messagesEndRef.current?.parentElement?.scrollTop || 0,
        // 保存暂停/中断状态，避免页面切换时状态丢失
        isPaused,
        isReceiving,
      };
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      console.log("💾 保存会话状态:", sessionId, sessionTitle, { isPaused, isReceiving });
    }
  };

  const restoreState = () => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        const state = JSON.parse(saved);
        // 🔴 修复：检查时间戳，避免恢复过时的状态（超过5分钟）
        const currentTime = Date.now();
        const savedTime = state.timestamp || 0;
        const timeDiff = currentTime - savedTime;

        // 只恢复5分钟内的状态
        if (timeDiff > SESSION_EXPIRY_TIME) {
          console.log("🕒 会话状态已过期，跳过恢复");
          sessionStorage.removeItem(STORAGE_KEY);
          return false;
        }

        if (state.sessionId) {
          // ⭐ 小新修复 2026-03-07：检查缓存消息是否缺少 display_name，如果是则跳过恢复，从 API 重新加载
          const hasDisplayName = state.messages?.some((m: any) => m.display_name);
          if (!hasDisplayName) {
            console.log("🕒 缓存消息缺少 display_name，跳过恢复，从 API 重新加载");
            sessionStorage.removeItem(STORAGE_KEY);
            return false;
          }
          
          setMessages(state.messages || []);
          setSessionId(state.sessionId);
          // 【小新第二修复 2026-03-02】从sessionStorage恢复时也更新ref
          currentSessionIdRef.current = state.sessionId;
          setSessionTitle(state.sessionTitle || "会话");

          // 恢复暂停/中断状态
          if (state.isPaused !== undefined) {
            setIsPaused(state.isPaused);
            isPausedRef.current = state.isPaused;
            console.log("🔄 恢复暂停状态:", state.isPaused);
          }
          // 注意：isReceiving 状态不需要恢复，因为页面切换回来后需要重新开始接收

          // 🔴 修复：根据保存的标记决定是否滚动到底部
          if (state.shouldScrollToBottom) {
            // 使用requestAnimationFrame确保DOM更新后再滚动
            requestAnimationFrame(() => {
              setTimeout(() => {
                scrollToBottomDelayed();
              }, 100);
            });
          } else if (state.scrollPosition !== undefined) {
            // 恢复之前的滚动位置
            setTimeout(() => {
              if (messagesEndRef.current?.parentElement) {
                messagesEndRef.current.parentElement.scrollTop =
                  state.scrollPosition;
              }
            }, 100);
          }

          console.log(
            "🔄 恢复会话状态:",
            state.sessionId,
            state.sessionTitle,
            "消息数:",
            state.messages?.length
          );
          return true;
        }
      } catch (e) {
        console.warn("恢复会话状态失败:", e);
        sessionStorage.removeItem(STORAGE_KEY); // 🔴 修复：清除损坏的数据
      }
    }
    return false;
  };

  // 页面可见性变化时保存和恢复状态
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.hidden) {
        // 页面隐藏时：保存当前状态并断开SSE连接
        saveState();
        // 断开SSE连接，避免后台持续消耗资源
        if (isReceiving) {
          disconnect();
          console.log("🔌 页面隐藏，断开SSE连接");
        }
      } else {
        // 页面重新可见时：不再重新请求API，避免覆盖当前消息
        // 改为从sessionStorage恢复状态，如果缓存有效的话
        const urlSessionId = new URLSearchParams(window.location.search).get(
          "session_id"
        );
        if (urlSessionId && urlSessionId === sessionId) {
          // 先尝试从缓存恢复
          const saved = sessionStorage.getItem(STORAGE_KEY);
          if (saved) {
            try {
              const state = JSON.parse(saved);
              const currentTime = Date.now();
              const savedTime = state.timestamp || 0;
              const timeDiff = currentTime - savedTime;
              
              // 缓存有效（5分钟内），且当前有消息，则恢复缓存状态
              if (timeDiff <= SESSION_EXPIRY_TIME && state.messages && state.messages.length > 0) {
                console.log("🔄 从缓存恢复会话状态，消息数:", state.messages.length);
                setMessages(state.messages);
                if (state.sessionTitle) {
                  setSessionTitle(state.sessionTitle);
                }
                // 恢复暂停状态
                if (state.isPaused !== undefined) {
                  setIsPaused(state.isPaused);
                  isPausedRef.current = state.isPaused;
                  console.log("🔄 恢复暂停状态:", state.isPaused);
                }
                // 滚动到底部
                scrollToBottomDelayed();
                return; // 不再请求API
              }
            } catch (e) {
              console.warn("恢复缓存失败:", e);
            }
          }
          
          // 缓存无效或为空时，才从API加载（仅首次加载时）
          if (messages.length === 0) {
            console.log("🔄 首次加载，从API获取会话数据");
            setTimeout(async () => {
              try {
                const sessionData = await sessionApi.getSessionMessages(
                  sessionId
                );
                if (sessionData.messages && sessionData.messages.length > 0) {
                  setMessages(
                    sessionData.messages.map((m: any) => {
                      let executionSteps: ExecutionStep[] = [];
                      if (m.execution_steps && Array.isArray(m.execution_steps)) {
                        executionSteps = m.execution_steps;
                      } else if (m.executionSteps && Array.isArray(m.executionSteps)) {
                        executionSteps = m.executionSteps;
                      }
                      return {
                        id: m.id?.toString() || Date.now().toString(),
                        role: m.role || "assistant",
                        content: m.content || "",
                        timestamp: new Date(m.timestamp || Date.now()),
                        executionSteps,
                        display_name: m.display_name,
                        model: m.model || undefined,
                        provider: m.provider || undefined,
                      };
                    })
                  );
                  const title = sessionData.title || "会话";
                  setSessionTitle(title);
                  if (sessionData.version !== undefined) {
                    setSessionVersion(sessionData.version);
                  }
                  if (sessionData.title_locked !== undefined) {
                    setTitleLocked(sessionData.title_locked);
                  }
                }
              } catch (error) {
                console.warn("加载会话数据失败:", error);
              }
            }, 100);
          }
        }
      }
    };
    document.addEventListener("visibilitychange", handleVisibilityChange);
    return () => {
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [messages, sessionId, sessionTitle, isReceiving]);

  // P1级别优化：状态验证和同步机制
  useEffect(() => {
    if (!sessionId || !isInitialized) return;

    const validateAndSyncState = async () => {
      try {
        // 验证前端状态与后端一致性
        const sessionData = await sessionApi.getSessionMessages(sessionId);

        // 获取后端返回的正确标题
        const backendTitle = sessionData.title || "会话";

        // 如果前端标题与后端不一致，强制同步
        if (backendTitle !== sessionTitle && backendTitle !== "会话") {
          console.warn("🔄 标题不一致，强制同步:", {
            frontend: sessionTitle,
            backend: backendTitle,
          });
          setSessionTitle(backendTitle);
        }

        // 验证消息数量
        if (sessionData.messages && sessionData.messages.length > 0) {
          const frontendMsgCount = messages.filter(
            (m) => m.role !== "system"
          ).length;
          const backendMsgCount = sessionData.messages.length;

          if (Math.abs(frontendMsgCount - backendMsgCount) > 2) {
            console.warn("🔄 消息数量差异较大，建议刷新页面");
          }
        }
      } catch (error) {
        console.warn("状态验证失败:", error);
        // 状态验证失败不影响用户体验，静默处理
      }
    };

    // 每2分钟验证一次状态一致性
    const intervalId = setInterval(() => {
      validateAndSyncState();
    }, 2 * 60 * 1000);

    return () => clearInterval(intervalId);
  }, [sessionId, sessionTitle, messages, isInitialized]);

  // 全局快捷键 - 前端小新代修改 UX-G02: 全局快捷键
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Enter 发送消息
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        handleSend();
      }
      // Ctrl/Cmd + K 清空对话
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault();
        handleClear();
      }
      // Ctrl/Cmd + N 新建会话
      if ((e.ctrlKey || e.metaKey) && e.key === "n") {
        e.preventDefault();
        handleNewSession();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [inputValue, loading]);

  // ============================================
  // 网络连接检查
  // ============================================

  /**
   * 检查网络连接状态
   */
  const checkNetworkConnection = async (): Promise<boolean> => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
      const response = await fetch(`${API_BASE_URL}/health`, {
        method: "GET",
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      return response.ok;
    } catch (error) {
      clearTimeout(timeoutId);
      console.warn("网络连接检查失败:", error);
      return false;
    }
  };

  // ============================================
  // 统一的标题管理函数
  // ============================================

  /**
   * 获取会话标题 - 统一管理所有标题来源
   * 优先级：1. API返回的title > 2. 用户修改过的标题 > 3. 消息内容 > 4. 默认标题
   */
  const getSessionTitle = (
    sessionData: { title?: string; messages?: any[] },
    defaultTitle: string = "会话"
  ): string => {
    // 1. 最高优先级：API返回的title字段
    if (sessionData.title && sessionData.title.trim()) {
      return sessionData.title.trim();
    }

    // 2. 次优先级：消息内容（只在没有API title时使用）
    if (sessionData.messages && sessionData.messages.length > 0) {
      const firstMessage = sessionData.messages[0];
      if (firstMessage?.content != null && firstMessage.content !== "") {
        // 只取前30个字符，避免过长，确保 content 是字符串
        const contentStr = String(firstMessage.content);
        const contentTitle = contentStr.substring(0, 30).trim();
        if (contentTitle) {
          return contentTitle;
        }
      }
    }

    // 3. 默认标题
    return defaultTitle;
  };

  /**
   * 生成新会话标题 - 智能生成有意义的标题
   * 🔄 优化：添加更多时间细分，使标题更精确
   */
  const generateNewSessionTitle = (): string => {
    const now = new Date();
    const hours = now.getHours();
    let timeOfDay = "";

    // 更精确的时间段划分
    if (hours >= 5 && hours < 8) timeOfDay = "清晨";
    else if (hours >= 8 && hours < 12) timeOfDay = "上午";
    else if (hours >= 12 && hours < 14) timeOfDay = "午间";
    else if (hours >= 14 && hours < 18) timeOfDay = "下午";
    else if (hours >= 18 && hours < 21) timeOfDay = "晚间";
    else if (hours >= 21 && hours < 24) timeOfDay = "深夜";
    else timeOfDay = "深夜"; // 0-5点

    const dateStr = `${now.getMonth() + 1}月${now.getDate()}日`;
    return `${dateStr} ${timeOfDay}会话 ${hours}:${now
      .getMinutes()
      .toString()
      .padStart(2, "0")}`;
  };

  // ⭐ 确保标题持久化到后端（带防抖、重试、版本冲突处理）
  const ensureTitlePersisted = async (sessionId: string, title: string) => {
    if (!sessionId || !title.trim()) return;

    // ⭐ 防抖检查：标题未变化时跳过保存
    if (title === lastSavedTitle) {
      console.log("标题未变化，跳过保存");
      return;
    }

    // ⭐ 防抖检查：正在保存时跳过重复请求
    if (saveStatus === "saving") {
      console.log("正在保存中，跳过重复请求");
      return;
    }

    const retryKey = `title-save-${sessionId}`;
    const currentRetry = retryCount[retryKey] || 0;

    try {
      setSaveStatus("saving");
      setIsSavingTitle(true);

      // 如果标题不是默认标题，保存到后端
      if (title !== "新会话" && title !== "会话") {
        // ⭐ 直接使用状态中的版本号
        const response = await sessionApi.updateSession(
          sessionId,
          title.trim(),
          sessionVersion
        );

        // ⭐ 更新本地版本号
        if (response.version) {
          setSessionVersion(response.version);
        }

        // ⭐ 更新最后保存的标题
        setLastSavedTitle(title);

        console.log(
          "💾 标题持久化成功:",
          sessionId,
          title,
          "版本:",
          sessionVersion
        );
      }

      // 更新本地sessionStorage
      saveState();

      // 保存成功
      setSaveStatus("saved");
      setIsSavingTitle(false);
      setLastSaveTime(Date.now());
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));

      // 2秒后恢复到idle状态
      setTimeout(() => {
        setSaveStatus("idle");
      }, 2000);
      } catch (error: any) {
        console.warn("标题持久化失败:", error);

       // ⭐ 处理409版本冲突错误
       if (error?.response?.status === 409) {
        const errorMsg =
          error.response.data?.detail || "版本冲突，该会话已被其他人修改";
        message.error(errorMsg);

        // ⭐ 从服务器重新获取最新数据
        try {
          const sessionData = await sessionApi.getSessionMessages(sessionId);
          if (sessionData.version) {
            setSessionVersion(sessionData.version);
          }
          if (sessionData.title) {
            setSessionTitle(sessionData.title);
          }
          if (sessionData.title_locked !== undefined) {
            setTitleLocked(sessionData.title_locked);
          }
          // 【小新第二修复 2026-03-02】title_source 由后端动态计算，前端不需要读取

          message.info("已自动同步最新数据，请重试");
        } catch (syncError) {
          console.error("同步最新数据失败:", syncError);
        }

        setSaveStatus("error");
        setIsSavingTitle(false);
        return;
      }

      // 其他错误：重试机制 - 最多3次
      setSaveStatus("error");
      setIsSavingTitle(false);

      if (currentRetry < 3) {
        const newRetry = currentRetry + 1;
        setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));
        message.warning(`保存失败，正在重试 (${newRetry}/3)...`);

        // 延迟1秒后重试
        setTimeout(() => {
          debouncedSaveTitle(sessionId, title);
        }, 1000);
      } else {
        // 超过重试次数，显示错误
        message.error("保存失败，请检查网络后重试");
        setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
      }
    }
  };

  // ⭐ 防抖版本的保存标题函数
  const debouncedSaveTitle = useCallback(
    debounce(async (sessionId: string, title: string) => {
      await ensureTitlePersisted(sessionId, title);
    }, 1000),
    []
  );

  // ============================================
  // 加载历史会话
  // ============================================
  useEffect(() => {
    const loadSession = async () => {
      const urlSessionId = searchParams.get("session_id");

      // 🔴 修复1: URL参数绝对优先 - 清除旧的sessionStorage
      if (urlSessionId) {
        // P1级别优化：添加会话跳转加载状态
        setSessionJumpLoading(true);
        message.loading({
          content: "正在加载会话...",
          key: "session-load",
          duration: 0,
        });

        // 🔴 修复：不要清除sessionStorage
        // 原因：用户从历史页面点击会话后，如果清除了sessionStorage
        // 返回聊天页面时无法恢复之前的会话状态
        // 改为：加载URL会话后，也会更新sessionStorage（在下面代码中）
        // sessionStorage.removeItem(STORAGE_KEY);

        const retryKey = `session-load-${urlSessionId}`;
        const currentRetry = retryCount[retryKey] || 0;

        try {
          const sessionData = await sessionApi.getSessionMessages(urlSessionId);
          if (sessionData.messages && sessionData.messages.length > 0) {
            setSessionId(urlSessionId);
            // 【小新第二修复 2026-03-02】加载会话时也更新ref
            currentSessionIdRef.current = urlSessionId;
            setMessages(
              sessionData.messages.map((m: any) => {
                // 安全地处理 executionSteps 字段
                let executionSteps: ExecutionStep[] = [];
                if (m.execution_steps && Array.isArray(m.execution_steps)) {
                  executionSteps = m.execution_steps;
                } else if (
                  m.executionSteps &&
                  Array.isArray(m.executionSteps)
                ) {
                  executionSteps = m.executionSteps;
                }

                return {
                  id: m.id?.toString() || Date.now().toString(),
                  role: m.role || "assistant", // 修复：确保 role 有效
                  content: m.content || "", // 修复：确保 content 不为 undefined
                  timestamp: new Date(m.timestamp || Date.now()), // 修复：确保 timestamp 有效
                  executionSteps,
                  display_name: m.display_name,
                  model: m.model || undefined,
                  provider: m.provider || undefined,
                };
              })
            );

            // ⭐ 2026-02-25 更新：加载新增字段
            const title = getSessionTitle(sessionData, "会话");
            setSessionTitle(title);

            // ⭐ 设置新字段
            if (sessionData.version !== undefined) {
              setSessionVersion(sessionData.version);
            }
            if (sessionData.title_locked !== undefined) {
              setTitleLocked(sessionData.title_locked);
            }
            // 【小新第二修复 2026-03-02】title_source 由后端动态计算，前端不需要读取

            // 加载成功
            setSessionJumpLoading(false);
            message.success({ content: "会话加载成功", key: "session-load" });
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));

            console.log(
              "🔵 从URL加载会话:",
              urlSessionId,
              "标题:",
              title,
              "版本:",
              sessionData.version
            );
            return;
          } else {
            // 【小新第四修复 2026-03-02 15:45:30】URL会话加载失败（没有消息），清理状态避免混乱
            console.warn(
              "🔴 URL会话没有消息，清理状态并跳过加载:",
              urlSessionId
            );
            setSessionId(null);
            currentSessionIdRef.current = null; // 同步清理ref
            setMessages([]);
            setSessionTitle("新会话");
            setSessionVersion(1);
            setTitleLocked(false);
            setSessionJumpLoading(false);
            message.destroy("session-load");
            return;
          }
        } catch (error) {
          console.warn("加载URL会话失败:", error);

          // 重试机制 - 最多3次
          if (currentRetry < 3) {
            const newRetry = currentRetry + 1;
            setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));
            message.warning({
              content: `加载失败，正在重试 (${newRetry}/3)...`,
              key: "session-load",
              duration: 0,
            });

            // 延迟1秒后重试
            setTimeout(() => {
              loadSession();
            }, 1000);
          } else {
            // 超过重试次数，显示错误
            setSessionJumpLoading(false);
            message.error({
              content: "加载会话失败，请检查网络后重试",
              key: "session-load",
            });
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
          }
        }
      }

      // 🔴 修复3: 只有在没有URL参数时才考虑sessionStorage
      if (!urlSessionId) {
        const restored = restoreState();
        if (restored) {
          console.log("🟢 从缓存恢复会话状态");
          // 如果是从缓存恢复，也要关闭加载状态
          setSessionJumpLoading(false);
          message.destroy("session-load");
          return;
        }
      }

      // 【小新第二修复 2026-03-02】只有在没有URL参数时才加载最近会话
      if (urlSessionId) {
        console.warn("🔴 有URL参数，不加载最近会话:", urlSessionId);
        setSessionJumpLoading(false);
        message.destroy("session-load");
        return;
      }

      // 🔴 修复4: 如果都没有，加载最近的会话（只获取最近的1个，直接加载，不筛选消息数量）
      try {
        const response = await sessionApi.listSessions(1, 1, undefined, true); // ⭐ 只加载有效会话
        if (response.sessions && response.sessions.length > 0) {
          const latestSession = response.sessions[0];
          const sessionData = await sessionApi.getSessionMessages(
            latestSession.session_id
          );
          setSessionId(latestSession.session_id);
          // 【小新第二修复 2026-03-02】加载最近会话时也更新ref
          currentSessionIdRef.current = latestSession.session_id;

          // 🔴 修复5: 使用统一的标题管理函数
          const title = getSessionTitle(
            {
              title: latestSession.title, // 优先使用listSessions返回的title
              messages: sessionData.messages,
            },
            "会话"
          );
          setSessionTitle(title);

          // ⭐ 2026-02-25 更新：加载新增字段
          if (latestSession.version !== undefined) {
            setSessionVersion(latestSession.version);
          }
          if (latestSession.title_locked !== undefined) {
            setTitleLocked(latestSession.title_locked);
          }
          // 【小新第二修复 2026-03-02】title_source 由后端动态计算，前端不需要读取

          if (sessionData.messages && sessionData.messages.length > 0) {
            setMessages(
              sessionData.messages.map((m: any) => {
                // 安全地处理 executionSteps 字段
                let executionSteps: ExecutionStep[] = [];
                if (m.execution_steps && Array.isArray(m.execution_steps)) {
                  executionSteps = m.execution_steps;
                } else if (
                  m.executionSteps &&
                  Array.isArray(m.executionSteps)
                ) {
                  executionSteps = m.executionSteps;
                }

                return {
                  id: m.id?.toString() || Date.now().toString(),
                  role: m.role || "assistant", // 修复：确保 role 有效
                  content: m.content || "", // 修复：确保 content 不为 undefined
                  timestamp: new Date(m.timestamp || Date.now()), // 修复：确保 timestamp 有效
                  executionSteps,
                  display_name: m.display_name, // ⭐ 小新修复 2026-03-07：添加 display_name
                  model: m.model || undefined,
                  provider: m.provider || undefined,
                };
              })
            );
          }
          console.log(
            "🟡 加载最近会话:",
            latestSession.session_id,
            "标题:",
            title,
            "版本:",
            latestSession.version
          );

          // 关闭加载状态
          setSessionJumpLoading(false);
          message.destroy("session-load");
        } else {
          // 如果没有获取到会话，显示提示信息
          console.log("🟡 没有找到任何会话，显示新会话界面");
          setSessionTitle("新会话");
          setMessages([]);
          setSessionId(null);
          setSessionJumpLoading(false);
          message.destroy("session-load");
        }
      } catch (error) {
        console.warn("加载最近会话失败:", error);
        // 即使失败也关闭加载状态
        setSessionJumpLoading(false);
        message.destroy("session-load");
        // 在错误情况下也可以显示默认的新会话界面
      }

      // 标记初始化完成
      setIsInitialized(true);
    };

    loadSession();
  }, [searchParams]);

  // ============================================
  // 消息发送逻辑
  // ============================================

  /**
   * 执行流式消息发送（使用useSSE hook）
   *
   * @update 2026-02-23 修复：添加assistant消息占位，确保onStep/onChunk能正确更新
   */
  const executeStreamSend = async (userMessage: Message) => {
    console.log("🔍 [executeStreamSend] 开始执行流式发送");
    console.log("  userMessage:", userMessage);
    
    setLoading(true);
    // ⭐ 启动等待计时器
    setWaitTime(0);
    setIsRetrying(false);
    if (waitTimerRef.current) {
      clearInterval(waitTimerRef.current);
    }
    waitTimerRef.current = setInterval(() => {
      setWaitTime(t => t + 1);
    }, 1000);
    clearSteps();

    // 【修复问题2】生成taskId用于中断功能
    const taskId = crypto.randomUUID();
    console.log("🔍 [executeStreamSend] 生成的taskId:", taskId);
    setCurrentTaskId(taskId);
    setTaskId(taskId);

    // 【关键修复】先创建assistant消息占位，设置isStreaming=true
    const assistantMessage: Message = {
      id: (Date.now() + 1).toString(),
      role: "assistant",
      content: "🤔 AI 正在思考...", // 【修复问题 2】显示占位文本，避免空白气泡
      timestamp: new Date(),
      executionSteps: [],
      isStreaming: true,
      model: undefined, // 前端小新代修改：明确设置可选属性
    };
    console.log("🔍 [executeStreamSend] 创建assistant占位消息:", assistantMessage);
    setMessages((prev) => [...prev, assistantMessage]);

    // 保存待发送消息到ref（同步）和state（异步）
    pendingMessageRef.current = userMessage; // 同步更新，立即生效 ✅
    setPendingMessage(userMessage);

    // 【小沈修复2026-03-03】在调用 /chat/stream 之前先保存用户消息
    // 这样即使AI响应失败，用户消息也不会丢失
    const currentSessionId = currentSessionIdRef.current || sessionId;
    console.log("🔍 [executeStreamSend] 使用的sessionId:", currentSessionId);
    
    if (currentSessionId) {
      try {
        console.log("🔍 在调用AI之前先保存用户消息:", userMessage);
        await sessionApi.saveMessage(currentSessionId, {
          role: "user",
          content: userMessage.content,
        });
        console.log("✅ 用户消息保存成功");
      } catch (error) {
        console.error("❌ 保存用户消息失败:", error);
        message.error("用户消息保存失败，但AI请求将继续发送");
      }
    } else {
      console.warn("⚠️ 未找到sessionId，无法保存用户消息:", userMessage.id);
    }

    console.log("🔍 [executeStreamSend] 准备调用sendStreamMessage...");
    console.log("  content:", userMessage.content);
    console.log("  sessionId:", currentSessionIdRef.current || sessionId);
    
    // 发送流式请求 - 【小沈添加 2026-03-03】传递sessionId用于后端缓存display_name
    sendStreamMessage(userMessage.content, currentSessionIdRef.current ?? sessionId ?? undefined);
    console.log("✅ [executeStreamSend] sendStreamMessage已调用");
  };

  /**
   * 任务中断处理 - 前端小新代修改
   */
  const handleInterrupt = async () => {
    const taskIdToCancel = serverTaskId || currentTaskId;
    if (taskIdToCancel) {
      try {
        message.info("正在中断任务...");
        await fetch(`${API_BASE_URL}/chat/stream/cancel/${taskIdToCancel}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
        });
        message.success("任务中断请求已发送");
      } catch (error) {
        message.error("发送中断请求失败: " + (error as Error).message);
      }
    }
  };

  /**
   * 任务暂停/继续
   */
  const handleTogglePause = async () => {
    if (!serverTaskId) {
      message.warning("当前没有进行中的任务");
      return;
    }

    try {
      if (!isPaused) {
        // 暂停：发送暂停请求
        const response = await fetch(
          `http://localhost:8000/api/v1/chat/stream/pause/${serverTaskId}`,
          { method: "POST" }
        );
        if (response.ok) {
          console.log("⏸️ 已发送暂停请求");
        } else {
          message.error("暂停请求失败");
        }
      } else {
        // 继续：发送恢复请求
        const response = await fetch(
          `http://localhost:8000/api/v1/chat/stream/resume/${serverTaskId}`,
          { method: "POST" }
        );
        if (response.ok) {
          console.log("▶️ 已发送恢复请求");
        } else {
          message.error("恢复请求失败");
        }
      }
    } catch (error) {
      console.error("❌ 暂停/继续请求失败:", error);
      message.error("暂停/继续请求失败: " + (error as Error).message);
    }
  };

  /**
   * 发送消息（带安全检测v2.0）
    */
   const handleSend = async () => {
     console.log("🔍 [handleSend] 函数开始执行");
     console.log("  inputValue:", inputValue);
     console.log("  loading:", loading);
     
     if (!inputValue.trim() || loading) return;

     // 🔴 修复：添加输入长度限制和验证
     if (inputValue.trim().length > 5000) {
       message.warning("消息过长，请精简到5000字符以内");
       return;
     }

     // 🔴 修复：网络连接检查 - 移除过早的setLoading(false)
     setLoading(true);
     try {
       console.log("🔍 [handleSend] 开始检查网络连接...");
       const isNetworkOK = await checkNetworkConnection();
        if (!isNetworkOK) {
          console.error("❌ [handleSend] 网络连接异常");
          message.error("网络连接异常，请检查网络后重试");
          setLoading(false);
          // ⭐ 停止等待计时器
          if (waitTimerRef.current) {
            clearInterval(waitTimerRef.current);
            waitTimerRef.current = null;
          }
          setWaitTime(0);
          return;
        }
       console.log("✅ [handleSend] 网络连接正常");
     } catch (error) {
       console.warn("⚠️ [handleSend] 网络检查异常:", error);
     }

    let currentSessionId = sessionId;
    if (!currentSessionId) {
      try {
        const newSession = await sessionApi.createSession(
          inputValue.trim().substring(0, 50)
        );
        currentSessionId = newSession.session_id;
        setSessionId(currentSessionId);
        // 【小新第二修复 2026-03-02】保存到ref，确保onComplete时使用正确的ID
        currentSessionIdRef.current = currentSessionId;
        console.log("创建新会话:", currentSessionId);
      } catch (error) {
        const errMsg = error instanceof Error ? error.message : "网络错误";
        message.error(`创建会话失败: ${errMsg}`);
        console.error("创建会话失败:", error);
        return; // 🔴 修复：创建会话失败时停止发送
      }
    } else {
      // 【小新第二修复 2026-03-02】已有会话时也保存到ref
      currentSessionIdRef.current = currentSessionId;
    }

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: inputValue.trim(),
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setBlockedCommand(null);

    // 安全检测v2.0
    setCheckingDanger(true);
    try {
      const checkResult = await securityApi.checkCommand(userMessage.content);
      setCheckingDanger(false);

      if (!checkResult.success || !checkResult.data) {
        console.warn("安全检测失败:", checkResult.error);
        await executeStreamSend(userMessage);
        return;
      }

      const { score, message: riskMessage } = checkResult.data;
      const riskLevel = getRiskLevel(score);

      switch (riskLevel.level) {
        case "SAFE":
          await executeStreamSend(userMessage);
          break;
        case "MEDIUM":
          showSecurityNotification(userMessage.content, score, riskMessage);
          await executeStreamSend(userMessage);
          break;
        case "HIGH":
          setDangerCommand(userMessage.content);
          setDangerScore(score);
          setDangerMessage(riskMessage);
          // 【小新第三修复 2026-03-02】同步更新ref
          pendingMessageRef.current = userMessage;
          setPendingMessage(userMessage);
          setDangerModalVisible(true);
          break;
        case "CRITICAL":
          setBlockedCommand({
            command: userMessage.content,
            score,
            message: riskMessage,
          });
          setMessages((prev) =>
            prev.filter((msg) => msg.id !== userMessage.id)
          );
          message.error("危险操作已被系统拦截");
          break;
      }
    } catch (error) {
      console.warn("安全检测异常:", error);
      setCheckingDanger(false);
      // 🔴 修复：更好的错误处理和用户反馈
      message.warning({
        content: "安全检测服务暂时不可用，将以普通模式发送消息",
        duration: 3,
      });
      await executeStreamSend(userMessage);
    }
  };

  /**
   * 危险命令确认执行
   */
  const handleDangerConfirm = async () => {
    // 【小新第五修复 2026-03-02】优先使用ref中的pendingMessage，确保获取正确的值
    const messageToProcess = pendingMessageRef.current || pendingMessage;
    if (messageToProcess) {
      setDangerModalVisible(false);
      await executeStreamSend(messageToProcess);
    }
  };

  /**
   * 危险命令取消执行
   */
  const handleDangerCancel = () => {
    setDangerModalVisible(false);
    // 【小新第五修复 2026-03-02】优先使用ref中的pendingMessage
    const messageToCancel = pendingMessageRef.current || pendingMessage;
    if (messageToCancel) {
      setMessages((prev) =>
        prev.filter((msg) => msg.id !== messageToCancel.id)
      );
      message.info("已取消危险命令的执行");
    }
    // 【小新第五修复 2026-03-02】同步清理ref和state
    pendingMessageRef.current = null;
    setPendingMessage(null);
  };

  /**
   * 新建会话 - 内部实现，支持重试机制
   */
  const handleNewSessionInternal = async (retry: number = 0) => {
    const retryKey = "new-session";
    const maxRetries = 3;

    setLoading(true);
    try {
      // 生成智能标题
      const newTitle = generateNewSessionTitle();
      const newSession = await sessionApi.createSession(newTitle);
      setSessionId(newSession.session_id);
      // 【小新第二修复 2026-03-02】新建会话时也更新ref
      currentSessionIdRef.current = newSession.session_id;
      setSessionTitle(newTitle);
      setMessages([]);

      // 🔴 修复：清除旧的sessionStorage
      sessionStorage.removeItem(STORAGE_KEY);

      // 添加系统提示消息 - 新会话提示
      const systemMessage: Message = {
        id: (Date.now() + 1000).toString(),
        role: "system",
        content: "💡 新会话已创建！开始与AI助手对话吧。",
        timestamp: new Date(),
      };
      setMessages([systemMessage]);

      clearSteps();
      disconnect();
      window.history.pushState({}, "", `/?session_id=${newSession.session_id}`);

      // 🎨 优化：添加更丰富的反馈
      message.success({
        content: `已创建新会话: ${newTitle}`,
        duration: 3,
        style: { marginTop: "50vh" },
      });

      // 重置重试计数
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
    } catch (error) {
      // P1级别优化：重试机制
      if (retry < maxRetries) {
        const newRetry = retry + 1;
        setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));

        message.warning({
          content: `创建会话失败，正在重试 (${newRetry}/${maxRetries})...`,
          duration: 2,
        });

        // 延迟1秒后重试
        setTimeout(() => {
          handleNewSessionInternal(newRetry);
        }, 1000);
        return;
      }

      // 🔴 修复：更好的错误处理
      const errMsg = error instanceof Error ? error.message : "未知错误";
      message.error({
        content: `创建会话失败: ${errMsg}`,
        duration: 5,
      });
      console.error("创建会话失败:", error);

      // 重置重试计数
      setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
    } finally {
      setLoading(false);
      // ⭐ 停止等待计时器
      if (waitTimerRef.current) {
        clearInterval(waitTimerRef.current);
        waitTimerRef.current = null;
      }
      setWaitTime(0);
    }
  };

  /**
   * 新建会话 - 按钮点击处理函数
   */
  const handleNewSession = () => {
    handleNewSessionInternal(0);
  };

  /**
   * 清空对话
   */
  const handleClear = () => {
    setMessages([]);
    clearSteps();
    disconnect();
  };

  return (
    <Card
      headStyle={{ padding: "4px 4px 2px 4px" }}
      bodyStyle={{ padding: "0 4px 4px 4px" }}
      title={
        <Space>
          <RobotOutlined />
          <span>AI对话助手</span>
          {isReceiving && <Badge status="processing" text="接收中..." />}
          {sessionId &&
            (editingTitle ? (
              <Space>
                <Input
                  value={titleInput}
                  onChange={(e) => setTitleInput(e.target.value)}
                  onPressEnter={async (e) => {
                    e.preventDefault();
                    if (titleInput.trim() && sessionId) {
                      try {
                        // 🔴 修复：回车时保存
                        await sessionApi.updateSession(
                          sessionId,
                          titleInput.trim(),
                          sessionVersion
                        );
                         setSessionTitle(titleInput.trim());
                        setTitleLocked(true); // 【小新第二修复 2026-03-02】用户修改标题后锁定
                         message.success("标题已保存");
                       } catch (error: any) {
                         // ⭐ 处理 409 版本冲突
                        if (error?.response?.status === 409) {
                          message.error("会话已被其他用户修改，请刷新页面");
                          // 尝试重新获取最新的会话信息
                          try {
                            const sessionData =
                              await sessionApi.getSessionMessages(sessionId);
                            if (sessionData.version) {
                              setSessionVersion(sessionData.version);
                            }
                            if (sessionData.title) {
                              setSessionTitle(sessionData.title);
                            }
                          } catch (refreshError) {
                            console.error("刷新会话数据失败:", refreshError);
                          }
                        } else {
                          console.warn("保存标题失败:", error);
                          message.error("保存标题失败，请重试");
                        }
                      }
                    }
                    setEditingTitle(false);
                  }}
                  onBlur={async () => {
                    if (titleInput.trim() && sessionId) {
                      try {
                        // 🔴 修复：失去焦点时也保存
                        await sessionApi.updateSession(
                          sessionId,
                          titleInput.trim(),
                          sessionVersion
                        );
                         setSessionTitle(titleInput.trim());
                        setTitleLocked(true); // 【小新第二修复 2026-03-02】用户修改标题后锁定
                         message.success("会话标题已更新");
                       } catch (error: any) {
                         // ⭐ 处理 409 版本冲突
                        if (error?.response?.status === 409) {
                          message.error("会话已被其他用户修改，请刷新页面");
                          // 尝试重新获取最新的会话信息
                          try {
                            const sessionData =
                              await sessionApi.getSessionMessages(sessionId);
                            if (sessionData.version) {
                              setSessionVersion(sessionData.version);
                            }
                            if (sessionData.title) {
                              setSessionTitle(sessionData.title);
                            }
                          } catch (refreshError) {
                            console.error("刷新会话数据失败:", refreshError);
                          }
                        } else {
                          message.error("更新标题失败");
                        }
                      }
                    }
                    setEditingTitle(false);
                  }}
                  style={{ width: 200 }}
                  autoFocus
                  placeholder="输入会话标题"
                />
              </Space>
            ) : (
              <span
                style={{
                  cursor: "pointer",
                  color: titleLocked ? "#000" : "#666", // 【小新第二修复 2026-03-02】使用 titleLocked 替代 titleSource
                  fontSize: titleLocked ? "16px" : "14px",
                  fontWeight: titleLocked ? "bold" : "normal",
                }}
                onClick={() => setEditingTitle(true)}
              >
                {sessionTitle || "未命名会话"}
                {!titleLocked && ( // 【小新第二修复 2026-03-02】使用 titleLocked 替代 titleSource
                  <Tooltip title="AI自动生成的标题">
                    <InfoCircleOutlined
                      style={{ fontSize: 12, marginLeft: 4, color: "#999" }}
                    />
                  </Tooltip>
                )}
                {titleLocked && (
                  <Tooltip title="标题已锁定，防止自动覆盖">
                    <LockOutlined
                      style={{ fontSize: 12, marginLeft: 4, color: "#1890ff" }}
                    />
                  </Tooltip>
                )}
              </span>
            ))}
        </Space>
      }
      extra={
        <Space>
          {/* 新建会话按钮 */}
          <Button
            icon={<PlusOutlined />}
            onClick={handleNewSession}
            size="small"
            type="primary"
          >
            新建会话
          </Button>

          {/* 流式开关（同时控制显示过程） */}
          <Tag.CheckableTag
            checked={useStream}
            onChange={(checked) => {
              setUseStream(checked);
              if (!checked) {
                setShowExecution(false);
              }
            }}
          >
            <ThunderboltOutlined /> {useStream ? "流式关闭" : "流式开启"}
          </Tag.CheckableTag>

          {/* 执行过程显示开关（仅在流式模式下显示） */}
          {useStream && (
            <Button
              size="small"
              icon={showExecution ? <EyeOutlined /> : <EyeInvisibleOutlined />}
              onClick={() => setShowExecution(!showExecution)}
            >
              {showExecution ? "隐藏过程" : "显示过程"}
            </Button>
          )}

          <Button onClick={handleClear} size="small">
            清空对话
          </Button>
        </Space>
      }
    >
      {/* AI思考过程面板已移至MessageItem内部 - 前端小新代修改 */}

      {/* 消息列表 - 前端小新代修改 UX-C04: 时间分隔线 */}
      <div
        style={{
          height: 500,
          overflowY: "auto",
          border: "1px solid #f0f0f0",
          borderRadius: 8,
          padding: "0 2px 2px 0",
          marginBottom: 0,
          backgroundColor: "#fafafa",
        }}
      >
        {messages.length === 0 ? (
          <div style={{ textAlign: "center", color: "#999", marginTop: 50 }}>
            <RobotOutlined style={{ fontSize: 48, marginBottom: 16 }} />
            <p>开始与 AI 助手对话</p>
            <p style={{ fontSize: 12 }}>
              {useStream
                ? "流式模式已开启 - 可实时查看 AI 思考过程"
                : "普通模式 - 一次性返回完整回复"}
            </p>
          </div>
        ) : (
          <div>
            {(() => {
              // 时间分隔线
              const elements: React.ReactNode[] = [];
              let lastDate: string | null = null;

              for (let i = 0; i < messages.length; i++) {
                const item = messages[i];
                const currentDate = new Date(item.timestamp).toLocaleDateString(
                  "zh-CN"
                );

                if (lastDate !== currentDate) {
                  elements.push(
                    <div
                      key={`date-${i}`}
                      style={{
                        textAlign: "center",
                        margin: "1px 0",
                        position: "relative",
                      }}
                    >
                      <div
                        style={{
                          position: "absolute",
                          top: "50%",
                          left: 0,
                          right: 0,
                          height: 1,
                          backgroundColor: "#e8e8e8",
                        }}
                      />
                      <span
                        style={{
                          background: "#fafafa",
                          padding: "0 16px",
                          color: "#999",
                          fontSize: 12,
                          position: "relative",
                          zIndex: 1,
                        }}
                      >
                        {currentDate}
                      </span>
                    </div>
                  );
                  lastDate = currentDate;
                }

                elements.push(
                  <List.Item
                    key={item.id}
                    style={{
                      justifyContent:
                        item.role === "user" ? "flex-end" : "flex-start",
                      border: "none",
                      padding: 0,
                      width: "100%",
                    }}
                  >
                    <MessageItem message={item} showExecution={showExecution} />
                  </List.Item>
                );
              }

              return elements;
            })()}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <Space direction="vertical" style={{ width: "100%" }}>
        {/* ⭐ 等待时间显示（正计时） */}
        {loading && waitTime > 0 && (
          <div style={{ marginTop: 8, marginBottom: 4 }}>
            <Tag color={waitTime > 30 ? "error" : waitTime > 15 ? "warning" : "processing"}>
              {isRetrying ? "🔄 正在重试..." : `⏱️ 已等待 ${waitTime} 秒`}
            </Tag>
          </div>
        )}
        {/* 中断和暂停按钮 */}
        {loading && (
          <Space style={{ marginTop: 8, marginBottom: 8 }}>
            <Button
              danger
              icon={<CloseCircleOutlined />}
              onClick={handleInterrupt}
            >
              中断
            </Button>
            <Button
              icon={isPaused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
              onClick={handleTogglePause}
            >
              {isPaused ? "继续" : "暂停"}
            </Button>
          </Space>
        )}
        <TextArea
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={
            useStream
              ? "输入消息... (流式模式可实时查看思考过程)"
              : "输入消息..."
          }
          autoSize={{ minRows: 2, maxRows: 4 }}
          onPressEnter={(e) => {
            if (!e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          disabled={loading || isReceiving}
          style={{
            borderColor: '#a8a8a8', // 加深输入框边框颜色
            boxShadow: 'none',
          }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={loading || isReceiving || checkingDanger}
          disabled={!inputValue.trim()}
          block
          style={{
            backgroundColor: !inputValue.trim() ? '#e6e6e6' : '#0066cc', // disabled 时加深，active 时柔和蓝
            borderColor: !inputValue.trim() ? '#d0d0d0' : '#0066cc',
            color: !inputValue.trim() ? 'rgba(0,0,0,0.4)' : '#fff',
            fontWeight: 500,
          }}
        >
          {isReceiving
            ? "接收中..."
            : checkingDanger
            ? "安全检查中..."
            : "发送消息"}
        </Button>
      </Space>

      {/* 被拦截的命令警告 */}
      {blockedCommand && (
        <SecurityAlert
          command={blockedCommand.command}
          score={blockedCommand.score}
          message={blockedCommand.message}
        />
      )}

      {/* 危险命令确认弹窗 */}
      <DangerConfirmModal
        visible={dangerModalVisible}
        command={dangerCommand}
        score={dangerScore}
        message={dangerMessage}
        onConfirm={handleDangerConfirm}
        onCancel={handleDangerCancel}
        loading={loading}
      />
    </Card>
  );
};

export default NewChatContainer;
