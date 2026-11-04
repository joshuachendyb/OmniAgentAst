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
 *
 * 编辑历史:
 * 2026-09-30 20:05:00 小欧 - restoreState 完整态分支改用后端最新消息: 原实现把
 *   loadHistoryMessages(useCache:false) 的返回值只当"会话存在性探针"(仅判 !verifyResult),
 *   拉回的全量消息被丢弃、转而渲染 sessionStorage 旧快照 → 列表标签显示 DB 真实条数而
 *   点进去只渲染旧条数(实测"001"标签 4 条、界面 2 条, 刷新才恢复)。改为 fresh 留存,
 *   网络正常用后端数据(与轻量态分支同口径), 仅弱网 catch 才回退本地快照 — 小欧-2026-09-30
 */

// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.10.3(a′)(b): 持久化载荷补 linkEnabled。①写入侧(完整态
//   PersistenceState + 降级态 LightState + saveMessagesToStorage 第6参 + saveState 传参 + 依赖)——
//   5.10.3(a′) 明列 3 处写入点, 本文件是第 2 处, 只补读侧不补写侧会让 state.linkEnabled 恒 undefined(测试假绿);
//   ②restoreState 两条返回路径(轻量态 result / 完整态 fresh)补 linkEnabled, 两条路径均 useCache:false
//   走后端故 result/fresh 天然含该字段; ③restoreState 返回类型补 linkEnabled。— 小欧-2026-10-03
// 编辑历史: 2026-10-03 小欧 - restoreState 两条路径的 linkEnabled 取值改为"本地优先, 后端兜底"。
//   原为后端优先, 与 5.8.19"勾选随消息携带"矛盾: 勾选在消息发出前只存在于浏览器, 后端存的还是
//   上一次发消息时的旧值, 后端优先会把用户刚勾的意图抹掉(勾了不发再刷新即丢)。
//   消息发出后该值随 link_enabled 上送, 两端一致, 故改优先级不影响已落库场景。— 小欧-2026-10-03

import { useEffect, useCallback, useRef } from 'react';
import type {
  Message,
  HistoryLoadResult,
  SessionModelOverride,
} from '../../../types/chat';
import type { UseChatStateReturn } from './useChatState';
import type { UseChatStreamingReturn } from './useChatStreaming';
import {
  debounce,
  STORAGE_KEY,
  SESSION_EXPIRY_TIME,
  loadHistoryMessages,
  // 2026-10-05 小欧 - 缓存 schema 单一来源: 写侧统一经 buildChatCacheState, 形状经 ChatCacheState,
  //   本文件不再自建平行 interface(见下方 PersistenceState/LightState 收窄别名)
  buildChatCacheState,
  parseChatCacheState,
  type ChatCacheState,
} from '../../../utils/chatHistory';

// ============================================================================
// 类型定义
// ============================================================================

/**
 * 持久化状态接口
 * 2026-10-05 小欧 - 改为 ChatCacheState 的收窄别名(缓存 schema 单一来源在 chatHistory.ts):
 *   此前本文件另立 PersistenceState/LightState 两份平行形状, 与 utils/sessionStorage.ts 的
 *   LightChatState 各自演化, 已实际漂移出两类故障(漏 sessionModel / 漏 linkEnabled)。
 *   形状不再本地声明, 新增字段只需改 chatHistory.ts 一处。 — 小欧-2026-10-05
 */
type PersistenceState = ChatCacheState & {
  messages: Message[];
  scrollPosition: number;
  isPaused: boolean;
  isReceiving: boolean;
  linkEnabled: boolean;
  allowInterject: boolean; // 2026-10-07 小欧 - 文档[11] 3.5.6: PersistenceState
  sessionVersion: number;
};

/**
 * 轻量级状态（用于大容量情况）
 * 2026-10-05 小欧 - 降级形状同样收窄到 ChatCacheState(删平行 interface, DRY)。
 */
type LightState = ChatCacheState & { messageCount: number };

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
    linkEnabled: boolean;
    allowInterject: boolean; // 2026-10-07 小欧 - 文档[11] 3.5.6: restoreState 返回类型
    // 2026-10-05 小欧 - 补 sessionModel: 本函数与 loadHistoryMessages 是两条独立的会话恢复路径,
    //   前者此前同样漏该字段, 只修后者会留下"刷新仍误显示跟随全局"的另一半缺口。
    sessionModel: SessionModelOverride | null;
  } | null>;

  // 防抖保存函数Ref
  saveMessagesToStorage: React.MutableRefObject<
    (
      msgs: Message[],
      sid: string,
      title: string,
      paused: boolean,
      receiving: boolean,
      linkEnabled: boolean,
      allowInterject: boolean, // 2026-10-07 小欧 - 文档[11] 3.5.6: 8→9 参, 插 linkEnabled 后/sessionModel 前
      // 2026-10-05 小欧 - 补两参: 会话模型覆盖(刷新后选择器状态) 与真实版本(原硬编码 1 会撞 409)
      sessionModel?: SessionModelOverride | null,
      version?: number
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
    linkEnabled,
    allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.6: 从 state 解构
    // 2026-10-05 小欧 - 缓存 schema 补 sessionModel 的数据源(刷新后模型选择器状态):
    //   本 hook 此前不解构该字段, 写出的缓存无此项 → 读侧命中缓存后选择器显示"跟随全局"。
    //   同 linkEnabled 同型事故(2026-10-03 已修过一次, 病根同为"写入点漏字段")。 — 小欧-2026-10-05
    sessionModelOverride,
    sessionVersion,
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
        receiving: boolean,
        linkEnabled: boolean,
        allowInterject: boolean, // 2026-10-07 小欧 - 文档[11] 3.5.6: 8→9 参形参
        sessionModel?: SessionModelOverride | null,
        version?: number
      ) => {
        if (sid) {
          // 2026-10-05 小欧 - ①补 sessionModel(刷新后模型选择器状态, 本次修复主体);
          //   ②sessionVersion 原硬编码 1, 缓存态因此永远声明"版本 1", 读侧回填会把
          //   乐观锁版本冲成 1 → 下一次 updateSession 必撞后端 409。改用真实版本(缺失才回落 1)。
          const state: PersistenceState = {
            messages: msgs,
            sessionId: sid,
            sessionTitle: title,
            sessionVersion: version ?? 1,
            timestamp: Date.now(),
            scrollPosition:
              messagesEndRef.current?.parentElement?.scrollTop || 0,
            isPaused: paused,
            isReceiving: receiving,
            linkEnabled,
            allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.6: 完整态 state 构造
            sessionModel: sessionModel ?? null,
          };

          try {
            const stateStr = buildChatCacheState(state);
            // 原有4MB检查保留
            if (stateStr.length > 4 * 1024 * 1024) {
              const lightState: LightState = {
                sessionId: sid,
                sessionTitle: title,
                timestamp: Date.now(),
                messageCount: msgs.length,
                isPaused: paused,
                isReceiving: receiving,
                linkEnabled,
                allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.6: 4MB 降级 lightState 构造
                sessionVersion: state.sessionVersion,
                sessionModel: state.sessionModel,
              };
              sessionStorage.setItem(
                STORAGE_KEY,
                buildChatCacheState(lightState)
              );
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
        isReceiving,
        linkEnabled,
        allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.6: saveState 实参调用(漏=保存恒 undefined)
        // 2026-10-05 小欧 - 随保存透传模型覆盖与真实版本(否则缓存丢 sessionModel, 刷新后误显示跟随全局)
        sessionModelOverride,
        sessionVersion
      );
    }
  }, [
    sessionId,
    messagesRef,
    sessionTitle,
    isPaused,
    isReceiving,
    linkEnabled,
    allowInterject, // 2026-10-07 小欧 - 文档[11] 3.5.6: saveState deps(漏依赖=闭包过期值)
    executionStepsRef,
    saveMessagesToStorage,
    // 2026-10-05 小欧 - 新增两个依赖: 缓存内容随之变化, 漏依赖会写进过期值
    sessionModelOverride,
    sessionVersion,
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
      // 2026-10-05 小欧 - 改走 parseChatCacheState(缓存 schema 单一来源): 原实现自己 JSON.parse,
      //   与写侧/chatHistory 读侧各一套解析, 是"漏字段"能反复发生的结构原因。
      //   解析失败/损坏一律 null(按无缓存走), 语义与 chatHistory 读侧一致。
      const data = parseChatCacheState(sessionStorage.getItem(STORAGE_KEY));
      if (!data) {
        return null;
      }

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
              sessionVersion: result.version ?? 1,
              // 本地勾选优先于后端, 理由同完整状态分支(见该处注释)
              linkEnabled: (data.linkEnabled ?? result.linkEnabled) === true,
              allowInterject:
                (data.allowInterject ?? result.allowInterject) === true, // 2026-10-07 小欧 - 文档[11] 3.5.6: restoreState 轻量路径
              isPaused: data.isPaused || false,
              isReceiving: data.isReceiving || false,
              // 2026-10-05 小欧(文档[10] §4.3): 轻量态返回体补 sessionModel(否则缓存分支无从注入)
              sessionModel: data.sessionModel ?? result.sessionModel ?? null,
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
      // 2026-09-30 20:05 小欧 - 修真 bug: 原实现把上面拉回的 verifyResult 只当"存在性探针"
      //   (只看 !verifyResult), 拉到的全量最新消息被丢弃, 转而渲染 sessionStorage 旧快照
      //   → 会话列表标签显示 DB 真实条数、点进去却只渲染旧条数(实测"001"显示4条只见2条, 刷新才恢复)。
      //   改: 留住 fresh, 网络正常用后端最新消息(与轻量态分支同口径), 仅弱网 catch 才回退本地快照。
      let fresh: HistoryLoadResult | null = null;
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
          fresh = verifyResult;
        } catch (verifyError) {
          // 2026-09-30 小欧 - 区分"确实不存在"与"验证失败"：loadHistoryMessages 已只对 404
          //   返回 null（上面分支处理），走到这里的都是网络/5xx。原实现一律清缓存并 return null，
          //   等于把弱网当成"缓存指向已删会话"→ 弱网进页面即丢本地快照。
          //   改：不清缓存、继续用下面的本地快照返回（缓存是完整本地数据，降级优于清空）。
          console.warn(
            '⚠️ 验证 sessionId 有效性失败，改用本地缓存:',
            verifyError
          );
        }
      }

      // 完整状态：优先后端最新消息, 无后端数据(弱网)才用本地快照
      return {
        messages: fresh?.messages || data.messages || [],
        sessionId: fresh?.sessionId || data.sessionId || null,
        sessionTitle: fresh?.title || data.sessionTitle || '新会话',
        sessionVersion: fresh?.version || data.sessionVersion || 1,
        // 本地勾选优先于后端: 勾选随消息携带(文档[4] 5.8.19), 未发出前只存在于浏览器,
        // 此时本地值即用户意图, 后端存的还是上一次发消息时的旧值。
        // 消息一旦发出, 该值随 link_enabled 上送后端, 此后两端一致, 谁优先都不影响结果。
        linkEnabled: (data.linkEnabled ?? fresh?.linkEnabled) === true,
        allowInterject: (data.allowInterject ?? fresh?.allowInterject) === true, // 2026-10-07 小欧 - 文档[11] 3.5.6: restoreState 完整 fresh 路径(取 HistoryLoadResult 镜像)
        isPaused: data.isPaused || false,
        isReceiving: data.isReceiving || false,
        // 2026-10-05 小欧(文档[10] §4.3): 完整态返回体补 sessionModel。
        //   取值同 linkEnabled 的"本地优先"语义: 模型覆盖未发出前只存在于浏览器(用户意图),
        //   后端存的还是上次发消息时的旧值; 消息发出后两端一致, 谁优先都不影响结果。
        sessionModel: data.sessionModel ?? fresh?.sessionModel ?? null,
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
