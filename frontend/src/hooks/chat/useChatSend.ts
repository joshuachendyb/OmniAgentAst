/**
 * useChatSend Hook - 消息发送逻辑
 * 
 * 功能：
 * - 消息验证（空消息、长度限制）
 * - 网络连接检查
 * - 乐观更新（先显示用户消息）
 * - 创建会话
 * - 发送消息
 * - 错误处理和回滚
 * 
 * @author 小沈
 * @version 1.0.0
 * @since 2026-04-23
 */

import { useCallback, useRef } from "react";
import { handleError, ErrorType } from "../../utils/errorHandler";
import { checkNetworkConnection } from "../../utils/network";
import { showNetworkError } from "../../utils/chatMessages";
import { sessionApi, API_BASE_URL } from "../../services/api";
import { logUserSend } from "../../utils/chatLogger";
import type { Message } from "../../types/chat";

interface UseChatSendOptions {
  // 状态
  loading: boolean;
  sessionId: string | null;
  messages: Message[];
  waitTime: number;
  // 设置方法
  setLoading: React.Dispatch<React.SetStateAction<boolean>>;
  setSessionId: React.Dispatch<React.SetStateAction<string | null>>;
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  setWaitTime: React.Dispatch<React.SetStateAction<number>>;
  // Refs
  waitTimerRef: React.MutableRefObject<ReturnType<typeof setTimeout> | null>;
  currentSessionIdRef: React.MutableRefObject<string | null>;
  // 发送方法
  executeSend: (userMessage: Message) => Promise<void>;
}

interface UseChatSendReturn {
  handleSend: (messageContent: string) => Promise<void>;
}

/**
 * useChatSend Hook
 */
export const useChatSend = (options: UseChatSendOptions): UseChatSendReturn => {
  const {
    loading,
    sessionId,
    messages,
    setLoading,
    setSessionId,
    setMessages,
    setWaitTime,
    waitTimerRef,
    currentSessionIdRef,
    executeSend,
  } = options;

  // 临时存储新创建的消息ID，用于错误回滚
  const pendingMessageIdRef = useRef<string | null>(null);

  const handleSend = useCallback(async (messageContent: string) => {
    console.log("🔍 [handleSend] 函数开始执行");
    console.log("  messageContent:", messageContent);
    console.log("  loading:", loading);

    // 1. 基础验证
    if (!messageContent.trim() || loading) return;

    // 2. 消息长度验证
    if (messageContent.trim().length > 5000) {
      handleError({ 
        message: "消息过长，请精简到5000字符以内", 
        error_type: ErrorType.CONTENT_TOO_LONG 
      });
      return;
    }

    // 3. 设置加载状态
    setLoading(true);

    // 4. 网络连接检查
    try {
      console.log("🔍 [handleSend] 开始检查网络连接...");
      const isNetworkOK = await checkNetworkConnection(API_BASE_URL);
      if (!isNetworkOK) {
        console.error("❌ [handleSend] 网络连接异常");
        showNetworkError();
        setLoading(false);
        // 停止等待计时器
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

    // 5. 创建用户消息（乐观更新）
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user" as const,
      content: messageContent.trim(),
      timestamp: new Date(),
    };
    pendingMessageIdRef.current = userMessage.id;

    // 6. 乐观更新：立即添加到状态显示给用户
    setMessages((prev) => [...prev, userMessage]);
    logUserSend(userMessage.content);

    try {
      // 7. 创建会话（如果需要）
      let currentSessionId = sessionId;
      if (!currentSessionId) {
        const newSession = await sessionApi.createSession(
          messageContent.trim().substring(0, 50)
        );
        currentSessionId = newSession.session_id;
        setSessionId(currentSessionId);
        currentSessionIdRef.current = currentSessionId;
        console.log("创建新会话:", currentSessionId);
      } else {
        currentSessionIdRef.current = currentSessionId;
      }

      // 8. 发送消息
      await executeSend(userMessage);

      // 9. 发送成功，不需要额外操作（用户消息已在列表中）

    } catch (error) {
      // 10. 发送失败，更新消息状态为failed（不移除消息）
      console.error("❌ [handleSend] 发送失败:", error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === userMessage.id
            ? { ...msg, sendStatus: "failed" as const }
            : msg
        )
      );
      handleError(error, { source: "api" });
    } finally {
      // 11. 清理状态
      setLoading(false);
      // 停止等待计时器
      if (waitTimerRef.current) {
        clearInterval(waitTimerRef.current);
        waitTimerRef.current = null;
      }
      setWaitTime(0);
      pendingMessageIdRef.current = null;
    }
  }, [
    loading,
    sessionId,
    setLoading,
    setSessionId,
    setMessages,
    setWaitTime,
    waitTimerRef,
    currentSessionIdRef,
    executeSend,
  ]);

  return {
    handleSend,
  };
};

export default useChatSend;
