/**
 * 聊天历史工具函数
 * 
 * 提供历史消息加载、缓存管理等工具函数
 * 从 NewChatContainer.tsx 提取
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-03-13
 */

import { sessionApi } from "../services/api";
import type { Message, HistoryLoadResult } from "../types/chat";
import type { ExecutionStep } from "../utils/sse";

// ============================================================
// 常量配置
// ============================================================

export const SESSION_EXPIRY_TIME = 5 * 60 * 1000; // 5分钟
export const STORAGE_KEY = "chat_session_state";
export const DEBUG_LOAD_FROM_API = import.meta.env.DEV || false;

// ============================================================
// 工具函数
// ============================================================

/**
 * 防抖函数
 */
export const debounce = <T extends (...args: Parameters<T>) => void>(
  func: T,
  delay: number
): T => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return ((...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      func(...args);
    }, delay);
  }) as T;
};

/**
 * 解析单条消息
 * @update 2026-03-14: 添加错误相关字段解析（使用API文档字段名）
 */
export const parseMessage = (rawMessage: unknown): Message => {
  const msg = rawMessage as Record<string, unknown>;
  // 处理 executionSteps（兼容两种字段名）
  let executionSteps: ExecutionStep[] = [];
  if (msg.execution_steps && Array.isArray(msg.execution_steps)) {
    executionSteps = msg.execution_steps as ExecutionStep[];
  } else if (msg.executionSteps && Array.isArray(msg.executionSteps)) {
    executionSteps = msg.executionSteps as ExecutionStep[];
  }

  return {
    id: (msg.id as string)?.toString() || Date.now().toString(),
    role: (msg.role as Message["role"]) || "assistant",
    content: (msg.content as string) || "",
    timestamp: new Date((msg.timestamp as string) || Date.now()),
    executionSteps,
    display_name: msg.display_name as string | undefined,
    model: (msg.model as string) || undefined,
    provider: (msg.provider as string) || undefined,
    is_reasoning: msg.is_reasoning as boolean | undefined,
    isStreaming: (msg.is_streaming as boolean) ?? (msg.isStreaming as boolean) ?? false,
    isError: (msg.is_error as boolean) || false,
    errorType: (msg.error_type as string) || undefined,
    errorMessage: (msg.error_message as string) || (msg.message as string) || undefined,
    errorRetryAfter: msg.retry_after as number | undefined,
    errorTimestamp: (msg.timestamp as string) || undefined,
    errorRecoverable: msg.recoverable as boolean | undefined,
    errorContext: msg.context as Record<string, unknown> | undefined,
  };
};

/**
 * 加载历史消息（统一入口）
 */
export const loadHistoryMessages = async (
  sessionId: string,
  options?: { useCache?: boolean }
): Promise<HistoryLoadResult | null> => {
  console.log("%c┌───── 历史消息加载 START", "color: blue; font-weight: bold; font-size: 14px;");

  try {
    // 先尝试从缓存读取（如果启用且不在DEBUG模式）
    if (options?.useCache !== false && !DEBUG_LOAD_FROM_API) {
      const saved = sessionStorage.getItem(STORAGE_KEY);
      if (saved) {
        try {
          const state = JSON.parse(saved);
          const currentTime = Date.now();
          const savedTime = state.timestamp || 0;
          const timeDiff = currentTime - savedTime;

          // 缓存有效（5分钟内），且sessionId匹配
          if (timeDiff <= SESSION_EXPIRY_TIME && 
              state.sessionId === sessionId && 
              state.messages?.length > 0) {
            console.log("%c│ 从缓存恢复: " + state.messages.length + " 条消息", "color: blue; font-size: 12px;");
            console.log("%c└───── 历史消息加载 END", "color: blue; font-weight: bold; font-size: 14px;");
            return {
              messages: state.messages,
              title: state.sessionTitle || "会话",
              sessionId: state.sessionId,
            };
          }
        } catch (e) {
          console.warn("缓存解析失败:", e);
        }
      }
    }

    // 从数据库读取
    const sessionData = await sessionApi.getSessionMessages(sessionId);

    // 检查是否有消息 - 空会话（无消息但有标题）也要返回有效结果
    if (!sessionData.messages || sessionData.messages.length === 0) {
      // 有标题的空会话，返回有效结果（不返回null）
      if (sessionData.title) {
        console.log("%c│ 无历史消息（空会话），但有标题: " + sessionData.title, "color: blue; font-size: 12px;");
console.log("%c└───── 历史消息加载 END", "color: blue; font-weight: bold; font-size: 14px;");
        return {
          messages: [],
          title: sessionData.title,
          sessionId: sessionData.session_id,
          version: sessionData.version,
        };
      }
      console.log("%c│ 无历史消息", "color: blue; font-size: 12px;");
      console.log("%c└───── 历史消息加载 END", "color: blue; font-weight: bold; font-size: 14px;");
      return null;
    }

    // 解析消息
const messages = sessionData.messages.map((rawMsg: unknown, index: number) => {
      const parsedMsg = parseMessage(rawMsg);
      (parsedMsg as Message & { dbIndex?: number }).dbIndex = index + 1;
      return parsedMsg;
    });

    // 日志每条消息（带序号）
    messages.forEach((m: Message & { dbIndex?: number }) => {
      const isUser = m.role === "user";
      const roleColor = isUser ? "green" : "purple";
      const roleLabel = isUser ? "👤 用户" : "🤖 AI";
      const msgIndex = m.dbIndex || "?";
      console.log(
        "%c│ [" + msgIndex + "] " + roleLabel + " | " + (m.content || "").substring(0, 40) + "...", 
        "color: " + roleColor + "; font-size: 11px;"
      );
    });

    // 日志结束
    console.log("%c│ 共 " + messages.length + " 条消息", "color: blue; font-size: 12px;");
    console.log("%c└───── 历史消息加载 END", "color: blue; font-weight: bold; font-size: 14px;");

    // 返回统一格式
    return {
      messages,
      title: sessionData.title || "会话",
      sessionId: sessionId,
      version: sessionData.version,
      title_locked: sessionData.title_locked,
    };

  } catch (error) {
    console.error("加载历史消息失败:", error);
    return null;
  }
};

/**
 * 加载最近会话的历史消息
 */
export const loadLatestHistoryMessages = async (): Promise<HistoryLoadResult | null> => {
  try {
    const response = await sessionApi.listSessions(1, 1, undefined, true);
    if (response.sessions && response.sessions.length > 0) {
      const latestSession = response.sessions[0];
      const result = await loadHistoryMessages(latestSession.session_id);
      if (result) {
        return { ...result, sessionId: latestSession.session_id };
      }
    }
    return null;
  } catch (error) {
    console.error("加载最近会话失败:", error);
    return null;
  }
};

/**
 * 保存会话到缓存
 */
export const saveSessionToCache = (
  sessionId: string,
  messages: Message[],
  sessionTitle: string
): void => {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
      sessionId,
      messages,
      sessionTitle,
      timestamp: Date.now(),
    }));
  } catch (e) {
    console.warn("保存会话缓存失败:", e);
  }
};

/**
 * 清除会话缓存
 */
export const clearSessionCache = (): void => {
  sessionStorage.removeItem(STORAGE_KEY);
};
