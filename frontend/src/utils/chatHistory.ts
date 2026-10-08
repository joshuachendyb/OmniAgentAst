// 编辑历史: 2026-07-16 小欧 - parseMessage 解析 thought 字段
// 编辑历史: 2026-08-22 小欧 - sessionModel 结构化: 两返回点字段 model_override→sessionModel
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep改从types/execution导入; 删execution_steps camel兼容分支(后端仅发snake); 删装饰性console.log
// 编辑历史: 2026-09-30 14:30 小欧 - 查会话改判 404 返回 null 其余冒泡（原吞异常致"不存在"与"取不到"不可区分）；debounce 加 flush()
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.5 + 5.10.3(a)(a′): ①两个后端返回点(空会话/有消息)补
//   linkEnabled(源 sessionData.link_enabled); ②缓存读侧返回补 linkEnabled: state.linkEnabled === true
//   (生产构建命中缓存即 return, 不补则镜像恒 false —— dev 因 DEBUG_LOAD_FROM_API 短路不可达, 故 dev 全绿 prod 假绿);
//   ③写入点 saveSessionToCache 补 linkEnabled(3 处写入点中的第 1 处)。 — 小欧-2026-10-03
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

import { sessionApi } from '../services/api/session.api';
// 2026-09-30 小欧 - 判 404 以把 null 语义收窄为"确实不存在"（其余异常冒泡给调用方重试）
import axios from 'axios';
import type {
  Message,
  HistoryLoadResult,
  SessionModelOverride,
} from '../types/chat';
import type { ExecutionStep } from '../types/execution';

// ============================================================
// 常量配置
// ============================================================

export const SESSION_EXPIRY_TIME = 5 * 60 * 1000; // 5分钟
export const STORAGE_KEY = 'chat_session_state';
export const DEBUG_LOAD_FROM_API = import.meta.env.DEV || false;

// ============================================================
// 缓存 schema 单一来源(DRY: 写侧4处 + 读侧1处共用, 杜绝"漏字段"重复发生)
// ============================================================

/**
 * 会话缓存 schema —— STORAGE_KEY 的唯一权威形状。
 *
 * 2026-10-05 小欧 新增(修"刷新后模型选择器误显示跟随全局"):
 *   病根: STORAGE_KEY 有 4 个写入点(useChatPersistence.saveState /
 *         useChatLifecycle.beforeunload / sessionStorage.saveChatState /
 *         chatHistory.saveSessionToCache), 各写各的字段, 谁漏一个字段
 *         刷新命中缓存时就丢一个字段。linkEnabled 已于 2026-10-03 踩过同型坑
 *         (useChatLifecycle.ts 注释留证), 这次轮到 sessionModel:
 *         4 处都没写 → 刷新后 loadHistoryMessages 缓存分支返回体无 sessionModel
 *         → useChatSession.ts:207 `result.sessionModel ?? null` 置 null
 *         → 选择器显示"跟随全局", 而后端 DB 该会话实有覆盖 → 界面与实际用型不符。
 *   修法: 本 interface + buildChatCacheState/parseChatCacheState 收口 schema,
 *         写侧只传字段不再各自拼对象, 读侧只走 parse。新增字段只需改这一处。
 *   不做旧 schema 兼容(禁止 backward): 缺字段自然降级为 undefined/null,
 *         缓存本就是同窗口短期态, 兼容层只会再制造一处"看起来有值其实没有"。
 */
export interface ChatCacheState {
  sessionId: string | null;
  sessionTitle: string;
  timestamp: number;
  /** 4MB 超限降级时用消息数代替全量 messages */
  messageCount?: number;
  messages?: Message[];
  scrollPosition?: number;
  isPaused?: boolean;
  isReceiving?: boolean;
  /** 会话 link 续聊开关(2026-10-03 补) */
  linkEnabled?: boolean;
  allowInterject?: boolean; // 2026-10-07 小欧 - 文档[11] 3.5.6: 插话开关镜像
  /** 乐观锁版本号(读侧回填 sessionVersion, 缺则调用方回落 1) */
  sessionVersion?: number;
  /**
   * 会话级模型覆盖(L2, null=跟随全局) —— 本次修复的主角。
   * 类型与 HistoryLoadResult.sessionModel 同源, 读侧直传不做二次映射。
   */
  sessionModel?: SessionModelOverride | null;
}

/**
 * 写侧唯一出口: 构造缓存 JSON。所有写入点必须经本函数(DRY 单一来源)。
 */
export const buildChatCacheState = (state: ChatCacheState): string =>
  JSON.stringify(state);

/**
 * 读侧唯一入口: 解析缓存 JSON。损坏/非法一律 null(交调用方按"无缓存"走 API),
 * 不抛异常 —— 存储损坏不得阻断会话加载。
 */
export const parseChatCacheState = (
  raw: string | null
): ChatCacheState | null => {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as ChatCacheState;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    return null;
  }
};

// ============================================================
// 工具函数
// ============================================================

/**
 * 防抖函数
 *
 * 2026-09-30 小欧 - 新增 flush()：beforeunload 同步调 saveState 后即返回，而落盘唯一出口是
 *   本防抖（无同步通道）→ 页面销毁后定时器永不执行、最后一批消息 100% 丢；卸载路径改调 flush。
 */
export type Debounced<T extends (...args: Parameters<T>) => void> = T & {
  /** 同步执行最近一次实参并取消待触发定时器（用于 beforeunload 等"同步返回即销毁"的场景） */
  flush: () => void;
};

export const debounce = <T extends (...args: Parameters<T>) => void>(
  func: T,
  delay: number
): Debounced<T> => {
  let timeoutId: ReturnType<typeof setTimeout> | null = null;
  let lastArgs: Parameters<T> | null = null;

  // 2026-09-30 小欧 - 单一调用点，供 debounced / flush 共用（DRY）。
  //   T 为自引用泛型，`func(...args)` 展开时 TS 报 "Parameters<T> must have a
  //   [Symbol.iterator]"（自引用约束下 TS 丢失元组可迭代性），故经 unknown 断言后展开。
  const invoke = (args: Parameters<T>): void => {
    (func as unknown as (...a: unknown[]) => void)(...(args as unknown[]));
  };

  const debounced = ((...args: Parameters<T>) => {
    lastArgs = args;
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      timeoutId = null;
      lastArgs = null;
      invoke(args);
    }, delay);
  }) as Debounced<T>;

  debounced.flush = (): void => {
    if (timeoutId) {
      clearTimeout(timeoutId);
      timeoutId = null;
    }
    if (lastArgs) {
      const args = lastArgs;
      lastArgs = null;
      invoke(args);
    }
  };

  return debounced;
};

/**
 * 解析单条消息
 * @update 2026-03-14: 添加错误相关字段解析（使用API文档字段名）
 */
export const parseMessage = (rawMessage: unknown): Message => {
  const msg = rawMessage as Record<string, unknown>;
  // 2026-08-27 小欧 三堂会审: 后端仅发 snake_case execution_steps(ApiMessage.execution_steps), 删 camel 兼容分支
  let executionSteps: ExecutionStep[] = [];
  if (msg.execution_steps && Array.isArray(msg.execution_steps)) {
    executionSteps = msg.execution_steps as ExecutionStep[];
  }

  return {
    id: (msg.id as string)?.toString() || Date.now().toString(),
    role: (msg.role as Message['role']) || 'assistant',
    content: (msg.content as string) || '',
    thought: msg.thought as string | undefined, // 小欧 2026-07-16
    timestamp: new Date((msg.timestamp as string) || Date.now()),
    executionSteps,
    display_name: msg.display_name as string | undefined,
    model: (msg.model as string) || undefined,
    provider: (msg.provider as string) || undefined,
    is_reasoning: msg.is_reasoning as boolean | undefined,
    isStreaming:
      (msg.is_streaming as boolean) ?? (msg.isStreaming as boolean) ?? false,
    isError: (msg.is_error as boolean) || false,
    errorType: (msg.error_type as string) || undefined,
    errorMessage:
      (msg.error_message as string) || (msg.message as string) || undefined,
    errorRetryAfter: msg.retry_after as number | undefined,
    errorTimestamp: (msg.timestamp as string) || undefined,
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
  try {
    // 先尝试从缓存读取（如果启用且不在DEBUG模式）
    if (options?.useCache !== false && !DEBUG_LOAD_FROM_API) {
      // 2026-10-05 小欧 - 读侧改走 parseChatCacheState(缓存 schema 单一来源):
      //   原实现自己 JSON.parse 再逐字段手挑, 漏一个字段就是一次"刷新丢状态"
      //   (sessionModel 即因此丢失 → 模型选择器误显示跟随全局)。
      const state = parseChatCacheState(sessionStorage.getItem(STORAGE_KEY));
      if (state) {
        const currentTime = Date.now();
        const savedTime = state.timestamp || 0;
        const timeDiff = currentTime - savedTime;

        // 缓存有效（5分钟内），且sessionId匹配
        if (
          timeDiff <= SESSION_EXPIRY_TIME &&
          state.sessionId &&
          state.sessionId === sessionId &&
          (state.messages?.length ?? 0) > 0
        ) {
          return {
            messages: state.messages ?? [],
            title: state.sessionTitle || '会话',
            sessionId: state.sessionId,
            version: state.sessionVersion,
            // 2026-10-05 小欧 - 补回 sessionModel/sessionVersion: 缓存态与 API 态字段对齐,
            //   否则刷新命中缓存后选择器拿不到覆盖值而显示"跟随全局"(老陈 2026-10-05 报)
            sessionModel: state.sessionModel ?? null,
            linkEnabled: state.linkEnabled === true,
            allowInterject: state.allowInterject === true, // 2026-10-07 小欧 - 文档[11] 3.5.6: 写入点②(读侧还原)
          };
        }
      }
    }

    // 从数据库读取
    const sessionData = await sessionApi.getSessionMessages(sessionId);

    // 检查是否有消息 - 空会话（无消息但有标题）也要返回有效结果
    if (!sessionData.messages || sessionData.messages.length === 0) {
      // 有标题的空会话，返回有效结果（不返回null）
      if (sessionData.title) {
        return {
          messages: [],
          title: sessionData.title,
          sessionId: sessionData.session_id,
          version: sessionData.version,
          title_locked: sessionData.title_locked, // 2026-08-27 小欧 修复#34: 空会话分支补title_locked(与有消息分支结构对齐)
          sessionModel: sessionData.sessionModel ?? null,
          linkEnabled: sessionData.link_enabled ?? false,
          allowInterject: sessionData.allow_interject ?? false, // 2026-10-07 小欧 - 文档[11] 3.5.6(空会话分支)
        };
      }
      return null;
    }

    // 解析消息
    const messages = sessionData.messages.map((rawMsg: unknown) =>
      parseMessage(rawMsg)
    );

    // 返回统一格式
    return {
      messages,
      title: sessionData.title || '会话',
      sessionId: sessionId,
      version: sessionData.version,
      title_locked: sessionData.title_locked,
      sessionModel: sessionData.sessionModel ?? null,
      linkEnabled: sessionData.link_enabled ?? false,
      allowInterject: sessionData.allow_interject ?? false, // 2026-10-07 小欧 - 文档[11] 3.5.6(有消息分支)
    };
  } catch (error) {
    // 2026-09-30 小欧 - null 语义收窄为"确实不存在"（仅 404）。原 catch 吞全部异常统一
    //   return null，致弱网/5xx 也被当"已删除"→ 清空正在看的内容并抹 URL，且调用方重试成死码。
    console.error('加载历史消息失败:', error);
    if (axios.isAxiosError(error) && error.response?.status === 404)
      return null;
    throw error;
  }
};

/**
 * 加载最近会话的历史消息
 */
export const loadLatestHistoryMessages =
  async (): Promise<HistoryLoadResult | null> => {
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
      // 2026-09-30 小欧 - 与 loadHistoryMessages 同因：异常冒泡，不再吞成 null。
      //   病根：调用方把 null 一律当"没有找到任何会话"→ setMessages([])+setSessionId(null)，
      //   故弱网/5xx 进聊天页会清空正在看的内容。这里吞异常即等于误报"用户没有任何会话"。
      //   "确实没有会话"由上面 listSessions 返回空列表表达，不需要异常来表达。
      console.error('加载最近会话失败:', error);
      throw error;
    }
  };

/**
 * 保存会话到缓存
 * 暂无调用方, 为与另两处写入点(useChatPersistence/useChatState-sessionStorage)同 key schema 对齐保留, 勿删。
 */
export const saveSessionToCache = (
  sessionId: string,
  messages: Message[],
  sessionTitle: string,
  linkEnabled: boolean = false,
  allowInterject: boolean = false, // 2026-10-07 小欧 - 文档[11] 3.5.6
  sessionModel?: SessionModelOverride | null,
  sessionVersion?: number
): void => {
  try {
    // 2026-10-05 小欧 - 经 buildChatCacheState 写(缓存 schema 单一来源), 并补 sessionModel:
    //   本写入点此前漏该字段, 与另 3 处同为"刷新丢状态"的病根(linkEnabled 同型事故 2026-10-03)
    sessionStorage.setItem(
      STORAGE_KEY,
      buildChatCacheState({
        sessionId,
        messages,
        sessionTitle,
        linkEnabled,
        allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.6: 写入点①
        sessionModel: sessionModel ?? null,
        sessionVersion,
        timestamp: Date.now(),
      })
    );
  } catch (e) {
    console.warn('保存会话缓存失败:', e);
  }
};

/**
 * 清除会话缓存
 */
export const clearSessionCache = (): void => {
  sessionStorage.removeItem(STORAGE_KEY);
};
