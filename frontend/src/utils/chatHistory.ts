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
export const debounce = <T extends (...args: any[]) => any>(
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

/**
 * 解析单条消息
 * @update 2026-03-14: 添加错误相关字段解析（使用API文档字段名）
 */
export const parseMessage = (rawMessage: any): Message => {
  // 处理 executionSteps（兼容两种字段名）
  let executionSteps: ExecutionStep[] = [];
  if (rawMessage.execution_steps && Array.isArray(rawMessage.execution_steps)) {
    executionSteps = rawMessage.execution_steps;
  } else if (rawMessage.executionSteps && Array.isArray(rawMessage.executionSteps)) {
    executionSteps = rawMessage.executionSteps;
  }

  return {
    id: rawMessage.id?.toString() || Date.now().toString(),
    role: rawMessage.role || "assistant",
    content: rawMessage.content || "",
    timestamp: new Date(rawMessage.timestamp || Date.now()),
    executionSteps,
    display_name: rawMessage.display_name,
    model: rawMessage.model || undefined,
    provider: rawMessage.provider || undefined,
    is_reasoning: rawMessage.is_reasoning,
    isStreaming: rawMessage.is_streaming ?? rawMessage.isStreaming ?? false,
    // 【小沈修改2026-04-16】错误相关字段：删除details/stack/retryable，后端已删除
    isError: rawMessage.is_error || false,
    errorType: rawMessage.error_type || undefined,
    errorMessage: rawMessage.error_message || rawMessage.message || undefined,  // 优先使用error_message
    errorRetryAfter: rawMessage.retry_after || undefined,
    errorTimestamp: rawMessage.timestamp || undefined,
    // 【小沈添加2026-04-15】新增recoverable和context字段
    errorRecoverable: rawMessage.recoverable || undefined,
    errorContext: rawMessage.context || undefined,
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
    const messages = sessionData.messages.map((rawMsg: any, index: number) => {
      const parsedMsg = parseMessage(rawMsg);
      // 附加原始序号（从数据库返回的顺序）
      (parsedMsg as any).dbIndex = index + 1;
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
