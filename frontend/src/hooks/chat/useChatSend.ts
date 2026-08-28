// 编辑历史: 2026-08-26 小欧 - 参与P1-P7: 发送逻辑对齐CommandPanel/TaskType/contextLink(8.12/8.14)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 8.5-15 删pendingMessageIdRef(回滚靠userMessage.id)
// 编辑历史: 2026-08-27 小欧 - hooks修复#9: executeSend抛错清理isStreaming占位幽灵消息
// 编辑历史: 2026-08-28 小强 - hooks修复#12: 防重由loading state改isSendingRef(useRef同步), 消除双击竞态
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

import { useCallback, useRef } from "react"; // 2026-08-28 小强: 加回useRef(isSendingRef同步防重)
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
  executeSend: (userMessage: Message, contextLinkMode?: 'linked' | 'independent') => Promise<void>;
}

interface UseChatSendReturn {
  handleSend: (messageContent: string, contextLinkMode?: 'linked' | 'independent') => Promise<void>;
}

/**
 * useChatSend Hook
 */
export const useChatSend = (options: UseChatSendOptions): UseChatSendReturn => {
  const {
    loading: _loading, // 2026-08-28 小强: 保留接口兼容, 实际用isSendingRef防重
    sessionId,
    setLoading,
    setSessionId,
    setMessages,
    setWaitTime,
    waitTimerRef,
    currentSessionIdRef,
    executeSend,
  } = options;

  // 2026-08-27 小欧 三堂会审: 回滚改靠userMessage.id, 删pendingMessageIdRef
  // 2026-08-28 小强 修复#12: useRef同步防重, 消除Boolean state异步绕过竞态
  const isSendingRef = useRef(false);

  const handleSend = useCallback(
    async (messageContent: string, contextLinkMode?: 'linked' | 'independent') => {
    // 1. 基础验证
    if (!messageContent.trim() || isSendingRef.current) return;
    isSendingRef.current = true;

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
      const isNetworkOK = await checkNetworkConnection(API_BASE_URL);
      if (!isNetworkOK) {
        console.error("[handleSend] 网络连接异常");
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
    } catch (error) {
      console.warn("[handleSend] 网络检查异常:", error);
    }

    // 5. 创建用户消息（乐观更新）
    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user" as const,
      content: messageContent.trim(),
      timestamp: new Date(),
    };
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
      } else {
        currentSessionIdRef.current = currentSessionId;
      }

      // 8. 发送消息
      await executeSend(userMessage, contextLinkMode);

      // 9. 发送成功，不需要额外操作（用户消息已在列表中）

    } catch (error) {
      // 10. 发送失败，更新消息状态为failed（不移除消息）
      console.error("[handleSend] 发送失败:", error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === userMessage.id
            ? { ...msg, sendStatus: "failed" as const }
            : msg
        )
      );
      // 2026-08-27 小欧 修复#9: 清理 executeSend 抛错残留的 isStreaming 占位 assistant 消息(幽灵消息), 避免会话卡"思考中"
      setMessages((prev) =>
        prev.filter(
          (msg) => !(msg.role === "assistant" && msg.isStreaming === true)
        )
      );
      handleError(error, { source: "api" });
    } finally {
      // 11. 清理状态
      setLoading(false);
      isSendingRef.current = false; // 2026-08-28 小强 修复#12: 重置防重标记
      // 停止等待计时器
      if (waitTimerRef.current) {
        clearInterval(waitTimerRef.current);
        waitTimerRef.current = null;
      }
      setWaitTime(0);
    }
  }, [
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