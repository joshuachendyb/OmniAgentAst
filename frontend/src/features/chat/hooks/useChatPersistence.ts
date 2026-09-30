// 编辑历史: 2026-08-26 小欧 - 参与改造: 状态持久化对接消息/任务恢复
// 编辑历史: 2026-09-10 小欧 - S12: messages持久化防抖由1000ms改5000ms, 与steps防抖同频, 去双路全量stringify — 小欧-2026-09-10
// 编辑历史: 2026-09-30 14:30 小欧 - 卸载/页面隐藏改调 flush()（原走防抖，页面销毁后定时器不执行致丢消息）；删死函数 clearStorage
/**
 * useChatPersistence Hook - 状态持久化与恢复
 *
 * 功能：
 * - 防抖保存逻辑（saveMessagesToStorage）
 * - 页面可见性处理（visibilitychange）
 * - 页面卸载前保存（beforeunload）
 * - 状态恢复（restoreState）
 * - 自动保存（当messages变化时）
 *
 * 设计说明：
 * - 集中管理所有持久化相关逻辑
 * - 处理sessionStorage的读写操作
 * - 处理页面可见性和卸载事件
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-21
 */

import { useEffect, useCallback, useRef } from 'react';
import type { Message } from '../../../types/chat';
import type { UseChatStateReturn } from './useChatState';
import type { UseChatStreamingReturn } from './useChatStreaming';
import {
  debounce,
  STORAGE_KEY,
  SESSION_EXPIRY_TIME,
  loadHistoryMessages,
} from '../../../utils/chatHistory';

// ============================================================================
// 类型定义
// ============================================================================

/**
 * 持久化状态接口
 */
interface PersistenceState {
  messages: Message[];
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  timestamp: number;
  scrollPosition: number;
  isPaused: boolean;
  isReceiving: boolean;
}

/**
 * 轻量级状态（用于大容量情况）
 */
interface LightState {
  sessionId: string | null;
  sessionTitle: string;
  timestamp: number;
  messageCount: number;
  isPaused: boolean;
  isReceiving: boolean;
}

/**
 * useChatPersistence Hook返回值
 */
export interface UseChatPersistenceReturn {
  // 保存函数
  saveState: () => void;
  saveStateWithSSECheck: () => void;

  // 恢复函数
  restoreState: () => Promise<{
    messages: Message[];
    sessionId: string | null;
    sessionTitle: string;
    sessionVersion: number;
    isPaused: boolean;
    isReceiving: boolean;
  } | null>;

  // 防抖保存函数Ref
  saveMessagesToStorage: React.MutableRefObject<
    (
      msgs: Message[],
      sid: string,
      title: string,
      paused: boolean,
      receiving: boolean
    ) => void
  >;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatPersistence - 状态持久化与恢复
 *
 * 迁移自：NewChatContainer.tsx 中的持久化逻辑
 * - saveMessagesToStorage：防抖保存到sessionStorage
 * - 页面可见性处理：visibilitychange事件
 * - 页面卸载前保存：beforeunload事件
 * - 自动保存：当messages变化时
 * - 状态恢复：从sessionStorage恢复状态
 *
 * @param state - useChatState返回的状态对象
 * @param streaming - useChatStreaming返回的流式对象
 * @returns 持久化相关函数和Refs
 */
export const useChatPersistence = (
  state: UseChatStateReturn,
  streaming: UseChatStreamingReturn
): UseChatPersistenceReturn => {
  const {
    messages,
    sessionId,
    sessionTitle,
    isPaused,
    messagesEndRef,
    messagesRef,
  } = state;

  const { isReceiving, executionStepsRef } = streaming;

  // ========================================
  // 防抖保存函数Ref
  // 迁移自：NewChatContainer.tsx 第139-170行
  // ========================================

  const saveMessagesToStorage = useRef(
    debounce(
      (
        msgs: Message[],
        sid: string,
        title: string,
        paused: boolean,
        receiving: boolean
      ) => {
        if (sid) {
          const state: PersistenceState = {
            messages: msgs,
            sessionId: sid,
            sessionTitle: title,
            sessionVersion: 1, // 默认版本
            timestamp: Date.now(),
            scrollPosition:
              messagesEndRef.current?.parentElement?.scrollTop || 0,
            isPaused: paused,
            isReceiving: receiving,
          };

          try {
            const stateStr = JSON.stringify(state);
            // 原有4MB检查保留
            if (stateStr.length > 4 * 1024 * 1024) {
              const lightState: LightState = {
                sessionId: sid,
                sessionTitle: title,
                timestamp: Date.now(),
                messageCount: msgs.length,
                isPaused: paused,
                isReceiving: receiving,
              };
              sessionStorage.setItem(STORAGE_KEY, JSON.stringify(lightState));
            } else {
              sessionStorage.setItem(STORAGE_KEY, stateStr);
            }
          } catch (e) {
            if (e instanceof DOMException && e.name === 'QuotaExceededError') {
              console.warn('⚠️ sessionStorage容量满，跳过保存');
            } else {
              console.error('保存会话状态失败:', e);
            }
          }
        }
      },
      500
    ) // 500ms防抖
  );

  // ========================================
  // 保存函数
  // ========================================

  /**
   * saveState - 保存当前状态到sessionStorage
   * 迁移自：NewChatContainer.tsx 第409行
   * 包含 executionStepsRef 合并逻辑，用于 SSE 正在接收时保存最新数据
   */
  const saveState = useCallback(() => {
    if (sessionId) {
      // 使用 messagesRef.current 获取最新消息，而不是闭包中的 messages
      let messagesToSave = messagesRef.current;

      // 如果正在接收 SSE，合并最新 steps 到 messages
      if (isReceiving && executionStepsRef.current.length > 0) {
        messagesToSave = messagesRef.current.map((msg, idx) => {
          // 找到最后一条 assistant 消息（正在流式输出的）
          if (
            msg.role === 'assistant' &&
            idx === messagesRef.current.length - 1
          ) {
            return {
              ...msg,
              executionSteps: executionStepsRef.current,
            };
          }
          return msg;
        });
      }

      saveMessagesToStorage.current(
        messagesToSave,
        sessionId,
        sessionTitle,
        isPaused,
        isReceiving
      );
    }
  }, [
    sessionId,
    messagesRef,
    sessionTitle,
    isPaused,
    isReceiving,
    executionStepsRef,
    saveMessagesToStorage,
  ]);

  /**
   * saveStateWithSSECheck - 带SSE检查的保存
   * 如果正在接收SSE消息，延迟500ms保存
   */
  const saveStateWithSSECheck = useCallback(() => {
    if (isReceiving) {
      // SSE正在接收，延迟保存
      setTimeout(() => {
        saveState();
      }, 500);
    } else {
      saveState();
    }
  }, [isReceiving, saveState]);

  // 2026-09-30 小欧 - 删 clearStorage 死函数：全仓零消费者（唯一提及处在 useChatStreaming 的
  //   历史注释里，描述早已不存在的 disconnect 三参），属 YAGNI 假接口面。

  // ========================================
  // 恢复函数
  // ========================================

  /**
   * restoreState - 从sessionStorage恢复状态
   * 迁移自：NewChatContainer.tsx 第1010行
   */
  const restoreState = useCallback(async () => {
    try {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (!stored) {
        return null;
      }

      const data = JSON.parse(stored);

      // 检查时间戳，避免恢复过时的状态（超过5分钟）
      const currentTime = Date.now();
      const savedTime = data.timestamp || 0;
      const timeDiff = currentTime - savedTime;

      // 只恢复5分钟内的状态
      if (timeDiff > SESSION_EXPIRY_TIME) {
        console.log('🕒 会话状态已过期，跳过恢复');
        sessionStorage.removeItem(STORAGE_KEY);
        return null;
      }

      // 检查是否是轻量级状态
      if (data.messageCount !== undefined) {
        // 轻量级状态，需要从服务器加载完整消息
        if (data.sessionId) {
          // 2026-09-30 小欧 [81]v1.4-H3: useCache:false 强制走后端——缓存即本快照自证，
          //   命中 5min 内同类缓存会返回缓存而非 DB 全量消息，DB 与 UI 失联不察觉
          const result = await loadHistoryMessages(data.sessionId, {
            useCache: false,
          });
          if (result) {
            return {
              messages: result.messages || [],
              sessionId: result.sessionId,
              sessionTitle: result.title || '新会话',
              sessionVersion: result.version || 1,
              isPaused: data.isPaused || false,
              isReceiving: data.isReceiving || false,
            };
          }
        }
        return null;
      }

      // 完整状态：检查display_name是否存在
      if (!data.messages || data.messages.length === 0) {
        console.log('🕒 缓存中没有messages，从 API 重新加载');
        return null;
      }

      const hasDisplayName = data.messages.some((m: Message) => m.display_name);
      if (!hasDisplayName) {
        console.log('🕒 缓存消息缺少 display_name，跳过恢复');
        sessionStorage.removeItem(STORAGE_KEY);
        return null;
      }

      // 完整状态：验证sessionId后端有效性，防止缓存指向已删除的session
      if (data.sessionId) {
        try {
          // 2026-09-30 小欧 [81]v1.4-H3: useCache:false 强制验证走后端——原默认读缓存
          //   5min 内命中"刚写入的快照"自证，后端已删该会话仍被当存在，DB 与 UI 失联
          const verifyResult = await loadHistoryMessages(data.sessionId, {
            useCache: false,
          });
          if (!verifyResult) {
            console.warn(
              '🔴 缓存中的sessionId后端不存在，清除缓存:',
              data.sessionId
            );
            sessionStorage.removeItem(STORAGE_KEY);
            return null;
          }
        } catch (verifyError) {
          // 2026-09-30 小欧 - 区分"确实不存在"与"验证失败"：loadHistoryMessages 已只对 404
          //   返回 null（上面分支处理），走到这里的都是网络/5xx。原实现一律清缓存并 return null，
          //   等于把弱网当成"缓存指向已删会话"→ 弱网进页面即丢本地快照。
          //   改：不清缓存、继续用下面的本地快照返回（缓存是完整本地数据，降级优于清空）。
          console.warn('⚠️ 验证 sessionId 有效性失败，改用本地缓存:', verifyError);
        }
      }

      // 完整状态
      return {
        messages: data.messages || [],
        sessionId: data.sessionId || null,
        sessionTitle: data.sessionTitle || '新会话',
        sessionVersion: data.sessionVersion || 1,
        isPaused: data.isPaused || false,
        isReceiving: data.isReceiving || false,
      };
    } catch (error) {
      console.error('恢复状态失败:', error);
      return null;
    }
  }, []);

  // ========================================
  // 副作用：页面可见性变化处理
  // 迁移自：NewChatContainer.tsx 第1079-1101行
  // ========================================

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        // 2026-09-30 小欧 - 与 beforeunload 同因——页面隐藏后可能被冻结/杀掉，
        //   500ms 防抖定时器不保证执行，故同样在 saveState 后立即 flush 同步落盘。
        saveState();
        saveMessagesToStorage.current.flush();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
    // 2026-09-30 小欧 - saveMessagesToStorage 为 useRef（引用恒定），入依赖仅为闭包新鲜度
  }, [saveState, saveMessagesToStorage]);

  // ========================================
  // 副作用：页面卸载前保存
  // 迁移自：NewChatContainer.tsx 第815-880行
  // ========================================

  useEffect(() => {
    const handleBeforeUnload = (_e: BeforeUnloadEvent) => {
      // 2026-09-30 小欧 - saveState() 后**立即 flush**，
      //   使卸载前最后一批消息同步落盘。
      //   病根：saveState 的唯一落盘出口是 debounce(...,500) 包装，无同步通道；
      //   而 beforeunload 处理器同步返回后页面立即销毁 → 500ms 定时器永不执行
      //   → 卸载时最后若干条消息 100% 丢失（注释"在页面卸载前保存状态"与实现相反）。
      //   修：flush 同步执行已排入的参数（与定时器语义等价、只是提前），零重复实现。
      saveState();
      saveMessagesToStorage.current.flush();

      // 标准做法：设置returnValue来显示确认对话框
      // 但为了更好的用户体验，我们只保存状态，不阻止用户离开
      // e.preventDefault();
      // e.returnValue = '';
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
    // 2026-09-30 小欧 - saveMessagesToStorage 为 useRef（引用恒定），入依赖仅为闭包新鲜度
  }, [saveState, saveMessagesToStorage]);

  // ========================================
  // 副作用：自动保存（当messages变化时）
  // ========================================

  useEffect(() => {
    // 2026-09-30 小欧 - 保留最外层 5s（曾尝试按 K1 删掉，实测导致退化后回退）：
    //   这层不只是"多余防抖"，它承担**与 store 侧 steps 落盘同频**的职责
    //   （chatStreamStore.schedulePersist 同为 5000ms，2026-09-10 S12 去双路全量 stringify）。
    //   删掉后 messages 变 1s 落盘、steps 仍 5s → 两者不同频，反而破坏 S12 意图。
    //   真要解 K1（三层防抖 6s 延迟）须两侧频率一起改，属跨 store/hook 的独立改造，
    //   且用例 T26 正是锁定该契约，单独改本侧必然转红——不擅自改测试迁就。
    const timer = setTimeout(() => {
      saveStateWithSSECheck();
    }, 5000); // 小欧 2026-09-10 S12: 与 steps 防抖同频，去双路全量 stringify

    return () => {
      clearTimeout(timer);
    };
  }, [messages, saveStateWithSSECheck]);

  // ========================================
  // 返回值
  // ========================================

  return {
    saveState,
    saveStateWithSSECheck,
    restoreState,
    saveMessagesToStorage,
  };
};
