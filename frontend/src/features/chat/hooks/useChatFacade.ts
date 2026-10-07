// 编辑历史: 2026-08-26 小欧 - 参与改造: 7Hook组合入口整合(统一暴露)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 透传setIsReceiving/hasSteps/复用Options类型/memo依赖onError
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-09-08 小欧 - 六章6.3.4(北京老陈裁定回归总原则): onError 包装器不再把 SSEError 压成 string,
//   改构 LiveError{text, requestLevel} 上抛(页面级错误数据源对象形态); options.onError 签名同步升级;
//   内部 chatCallbacks.onError 仍先调(后端分道早退不影响页面级错误写入) — 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-B6: :355 useMemo有意只列字段级依赖(整体对象入deps每次重建级联渲染),
//   eslint-disable注释移至依赖数组行上方使生效+写明理由 — 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - 阶段二S2提前实施: shared.executionStepsRef改从chatStreaming取(useSSE单一真源),
//   deps同步改源(341/413行) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段二S2收尾(方案A): shared.executionStepsRef 维持从 chatStreaming 取,
//   useChatCallbacks 不再需要 executionStepsRef(读点用 sseParser 三参、清空点归 useSSE.clearSteps) — 小欧-2026-09-10
// 编辑历史: 2026-09-19 小欧: options加onSuccess回调, 透传useChatCallbacks(任务成功完成→清liveError) — 北京老陈驱动
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.9: 删 receivingSetterRef 中间层与其注入 effect,
//   setIsReceiving 改直连 chatStreamStore.setReceiving(5.4 公开动作, 循环依赖已不复存在);
//   taskControl.functions.disconnect 改 stop(Store.stop, 见 5.14) — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-30 14:30 小欧 - URL 归页面层 Router 唯一写；会话真源改 state 优先；删九组零消费分组；onSuccess 移出流接口
/**
 * useChatFacade Hook - 便捷的Chat状态组合
 *
 * 功能：
 * - 提供统一的Chat状态访问入口
 * - 组合7个独立Hook的便捷访问
 * - 通过useMemo缓存避免不必要的重渲染
 *
 * 设计说明：
 * - 不改变现有7个Hook的结构
 * - 不追求"按需加载"Hook（React规则禁止）
 * - 通过UI条件渲染实现"按需显示"
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-24
 */

import { useMemo } from 'react';
import { useChatState } from './useChatState';
import { useChatCallbacks } from './useChatCallbacks';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
// 2026-09-30 小欧 - 删 InitializeSessionOptions/Result、Message、ExecutionStep 四个 import：
//   它们原只服务于已删除的九组结构化分组（K2），分组内联过这些类型
import { useChatStreaming } from './useChatStreaming';
import { useChatSession } from './useChatSession';
import { useChatPersistence } from './useChatPersistence';
import { useChatSend } from './useChatSend';
import { useChatTaskControl } from './useChatTaskControl';
import type { LiveError } from '@/types/sse'; // 2026-09-08 小欧 6.3.4: 页面级错误数据源对象形态 — 小欧-2026-09-08

/**
 * useChatFacade 返回类型定义
 */
export interface UseChatFacadeReturn {
  // 2026-09-30 小欧 - 删九组结构化分组（session/message/streaming/ui/send/interrupt/
  //   sessionOps/persistence/shared，约 96 行）：全仓零消费者——ChatPage 自始只解构
  //   chatState / chatStreaming / chatSend / chatTaskControl 四个原始 Hook 对象，
  //   分组既未被消费也未被测试引用，属 YAGNI（K2）。删后本接口只剩下面一套 Hook 对象，
  //   "新旧两套暴露面并存"随之消失（B2，不再需要"兼容旧引用"的说法）。
  // ===== 本 Hook 组装并透出的各子 Hook（唯一一套暴露面）=====
  chatState: ReturnType<typeof useChatState>;
  chatCallbacks: ReturnType<typeof useChatCallbacks>;
  chatStreaming: ReturnType<typeof useChatStreaming>;
  chatSession: ReturnType<typeof useChatSession>;
  chatPersistence: ReturnType<typeof useChatPersistence>;
  chatSend: ReturnType<typeof useChatSend>;
  chatTaskControl: ReturnType<typeof useChatTaskControl>;
}

/**
 * useChatFacade - 统一的Chat状态Facade
 */
export const useChatFacade = (options?: {
  baseURL?: string;
  sessionId?: string | null;
  onError?: (liveError: LiveError) => void;
  onSuccess?: () => void; // 2026-09-19 小欧: 任务成功完成回调(终态非failed), 用于清liveError — 北京老陈驱动
  // 2026-09-30 小欧 - URL 写入出口透传（原 useChatSession 直接调原生
  //   window.history.pushState/replaceState 绕过 React Router，导致 urlSessionId 陈旧、
  //   本层的 `sessionId || chatState.sessionId` 让陈旧值优先 → setIsReceiving 写错会话）。
  //   改由页面层（唯一与 Router 接触处，ChatPage 用 setSearchParams）写，URL 写入单一入口。
  //   同一注入也透给 useChatSend，使"发消息自动建会话"同样进 URL，写入口彻底收口。
  onUrlSessionChange?: (sessionId: string | null) => void;
}): UseChatFacadeReturn => {
  const { baseURL = '', sessionId } = options || {};
  const onError = options?.onError; // 2026-08-27 小欧 三堂会审: 透传SSE错误用
  const onSuccess = options?.onSuccess;
  const onUrlSessionChange = options?.onUrlSessionChange;

  // 1. 基础状态（始终加载）
  const chatState = useChatState();

  // 2. 回调函数（始终加载）
  // [63] 5.9 v1.29：直连 Store——原 receivingSetterRef 解的是与 useChatStreaming 的循环依赖，
  //   现 setIsReceiving 已是 Store 公开动作（5.4 setReceiving），循环不复存在（KISS：删中间层）
  // 2026-09-30 小欧 - 会话真源判据改为"state 优先、URL 仅在 state 尚未建立时兜底"（?? 而非 ||）。
  //   病根：原 `sessionId || chatState.sessionId` 让 URL 恒优先，而 URL 由 Router 同步更新、
  //   state 由异步初始化收敛 → 切会话的窗口内 URL 已是新会话、state 仍是旧会话，
  //   旧会话在跑的流其 setIsReceiving/setReceiving 就会写到新会话槽位（跨会话污染）。
  //   首屏不受影响：此时 state.sessionId 仍为 null，正好取 URL 作初始化兜底。
  const storeSessionId = chatState.sessionId ?? sessionId;
  // 2026-09-30 小欧 - 流对象只留流的事（setIsReceiving）；页面级 onSuccess 移到第三个参数
  //   pageCallbacks（ISP：页面 UI 回调不再混进流对象/流事件接口）
  const chatCallbacksStreaming = useMemo(
    () => ({
      setIsReceiving: (v: boolean) =>
        chatStreamStore.setReceiving(storeSessionId ?? '', v),
    }),
    [storeSessionId]
  );
  const chatCallbacksPages = useMemo(
    () => ({
      onSuccess, // 2026-09-19 小欧: 任务成功完成回调透传 — 北京老陈驱动
    }),
    [onSuccess]
  );
  const chatCallbacks = useChatCallbacks(
    chatState,
    chatCallbacksStreaming,
    chatCallbacksPages
  );

  // 2.1 透传 SSE 错误给上层（页面级错误数据源对象形态，6.3.4——不再压 string）
  const chatCallbacksWithError = useMemo<ReturnType<typeof useChatCallbacks>>(
    () => ({
      ...chatCallbacks,
      onError: (error: Parameters<typeof chatCallbacks.onError>[0]) => {
        // 2026-09-08 小欧 6.3.3: 内部先调(后端业务错误分道早退只清refs; 本地错误走弹窗+消息替换),
        //   页面级错误写入不因早退而跳过 —— 由构造 LiveError 继续完成
        chatCallbacks.onError(error);
        if (onError) {
          const text =
            typeof error === 'string'
              ? error
              : error.error_message || '未知错误';
          const requestLevel =
            typeof error === 'string' ? false : error.request_level === true;
          onError({ text, requestLevel });
        }
      },
    }),
    [chatCallbacks, onError] // 2026-08-27 小欧 三堂会审: 依赖onError避免options每次新对象
  );

  // 3. 流式处理（始终加载，但可UI按需显示）
  // [63] 5.9：调用形状不变；流状态与连接已常驻 Store（5.3/5.4），本层只拿快照与动作
  const chatStreaming = useChatStreaming(chatState, chatCallbacksWithError, {
    baseURL,
    sessionId: storeSessionId ?? null, // 复用同一真源判据，不另写一份（DRY）；undefined 归一为 null
  });

  // 4. 会话管理（始终加载）
  // [63] 5.18：streaming 参数收敛（session 内零消费）
  const chatSession = useChatSession(chatState, onUrlSessionChange);

  // 5. 持久化（始终加载）
  const chatPersistence = useChatPersistence(chatState, chatStreaming);

  // 6. 消息发送（始终加载）
  const chatSend = useChatSend({
    sessionId: chatState.sessionId,
    setLoading: chatState.setLoading,
    setSessionId: chatState.setSessionId,
    setMessages: chatState.setMessages,
    setWaitTime: chatState.setWaitTime,
    waitTimerRef: chatState.waitTimerRef,
    currentSessionIdRef: chatState.currentSessionIdRef,
    executeSend: chatStreaming.executeSend,
    // 2026-10-07 小欧 - 文档[11] 决策 9/13: 插话投递(独立于 executeSend) + 插话判定所需的执行中标志
    interjectSend: chatStreaming.interjectSend,
    isReceiving: chatStreaming.isReceiving,
    // 2026-09-30 小欧 - 自动建会话也要写 URL，故把同一注入形状透到 useChatSend（写入口收口）
    onUrlSessionChange,
  });

  // 7. 中断控制（始终加载）
  const chatTaskControl = useChatTaskControl({
    setters: {
      setLoading: chatState.setLoading,
      setIsPaused: chatState.setIsPaused,
      // [63] 5.14 连带：chatStreaming.setIsReceiving 已被 5.8 删除，改直连 Store
      setIsReceiving: (v: boolean) =>
        chatStreamStore.setReceiving(storeSessionId ?? '', v),
    },
    states: {
      isPaused: chatState.isPaused,
      sessionId: chatState.sessionId,
      serverTaskId: chatStreaming.serverTaskId,
    },
    refs: {
      cancelInProgressRef: chatState.cancelInProgressRef,
      waitTimerRef: chatState.waitTimerRef,
      isPausedRef: chatState.isPausedRef,
    },
  });

  // 通过useMemo统一返回，避免不必要的重渲染
  return useMemo(
    () => ({
      // 2026-09-30 小欧 - 删九组结构化分组的构造（原 session/message/streaming/ui/send/
      //   interrupt/sessionOps/persistence/shared）：运行时零消费者（ChatPage 自始只解构
      //   四个子 Hook；useChatScroll 仅把分组当**类型引用源**、运行时仍传原始对象，
      //   该类型引用已改指 UseChatStateReturn/UseChatStreamingReturn）。详见 K2 说明。
      // ===== 本 Hook 组装并透出的各子 Hook（唯一一套暴露面）=====
      chatState,
      chatCallbacks,
      chatStreaming,
      chatSession,
      chatPersistence,
      chatSend,
      chatTaskControl,
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- facade单次组装: 底层各hook各自精确依赖, 整体入deps会全量重建级联渲染 — 小欧-2026-09-09
    [
      // ===== 会话状态 =====
      chatState.sessionId,
      chatState.sessionTitle,
      chatState.sessionVersion,
      chatState.titleLocked,
      chatState.editingTitle,
      chatState.titleInput,
      chatState.setSessionId,
      chatState.setSessionTitle,
      chatState.setSessionVersion,
      chatState.setTitleLocked,
      chatState.setEditingTitle,
      chatState.setTitleInput,
      chatState.currentSessionIdRef,
      // ===== 消息状态 =====
      chatState.messages,
      chatState.loading,
      chatState.isRetrying,
      chatState.setMessages,
      chatState.setLoading,
      chatState.setIsRetrying,
      chatState.messagesRef,
      chatState.messagesEndRef,
      // ===== 流式状态 =====
      chatStreaming.isReceiving,
      chatStreaming.executionSteps,
      chatStreaming.serverTaskId,
      chatStreaming.currentResponse,
      storeSessionId,
      chatState.isPaused,
      chatState.waitTime,
      chatState.setIsPaused,
      chatState.setWaitTime,
      // ===== UI状态 =====
      chatState.useStream,
      chatState.isInitialized,
      chatState.sessionJumpLoading,
      chatState.isMessageListLoading,
      chatState.setUseStream,
      chatState.setIsInitialized,
      chatState.setSessionJumpLoading,
      chatState.setIsMessageListLoading,
      chatState.userScrolledUpRef,
      chatState.lastScrollTimeRef,
      // ===== 操作函数 =====
      chatSend.handleSend,
      chatTaskControl.handleCancel,
      chatTaskControl.handleTogglePause,
      chatSession.initializeSession,
      chatSession.handleNewSession,
      chatSession.handleClear,
      chatPersistence.saveStateWithSSECheck,
      chatPersistence.saveMessagesToStorage,
      // ===== Refs =====
      chatState.waitTimerRef,
      chatStreaming.executionStepsRef, // 小欧 2026-09-10 S2: deps 同步改源
      chatState.isPausedRef,
      chatState.hasReceivedCancelEventRef,
      chatState.cancelInProgressRef,
    ]
  );
};

/**
 * useShouldLoadStreaming - UI按需渲染判断
 *
 * 功能：
 * - 判断是否需要显示streaming相关UI
 * - 通过状态检查实现"按需显示"
 * - 避免条件渲染Hook的问题
 *
 * 注意：此Hook需要配合useChatFacade使用
 * 因为它依赖chatState中的状态
 *
 * 使用方法：
 * ```typescript
 * const chat = useChatFacade();
 * const shouldLoad = useShouldLoadStreaming(chat);
 *
 * // UI按需渲染
 * return (
 *   <div>
 *     {shouldLoad.isReceiving && <LoadingIndicator />}
 *     {shouldLoad.hasSteps && <StepList />}
 *     {shouldLoad.canCancel && <CancelButton />}
 *   </div>
 * );
 * ```
 */
export const useShouldLoadStreaming = (
  chat: ReturnType<typeof useChatFacade>
) => {
  // 2026-09-30 小欧 - 改读子 Hook 原始对象（K2）：原经 chat.streaming / chat.ui 两个
  //   分组间接取值，而分组本身是 facade 手工拼装的派生视图（同一份数据再抄一遍），
  //   删分组后此处直连唯一真源，语义完全等价。
  const streaming = chat?.chatStreaming;
  const ui = chat?.chatState;

  return useMemo(
    () => ({
      // 是否正在接收
      isReceiving: streaming?.isReceiving ?? false,

      // 是否有执行步骤（需要从chatState获取）
      hasSteps: (streaming?.executionSteps?.length ?? 0) > 0, // 2026-08-27 小欧 三堂会审: 由executionSteps派生

      // 是否可以显示工具面板
      showPanel:
        (streaming?.isReceiving ?? false) ||
        (streaming?.executionSteps?.length ?? 0) > 0,

      // 是否可以显示中断按钮
      canCancel: streaming?.isReceiving ?? false,

      // 是否显示等待时间
      showWaitTime:
        (streaming?.isReceiving ?? false) &&
        (ui?.isMessageListLoading ?? false),
    }),
    [streaming, ui]
  );
};

/**
 * useChatFacade组合 - 用于替代NewChatContainer中的多个Hook调用
 *
 * 使用示例：
 * ```typescript
 * // 之前（调用7个Hook）
 * const chatState = useChatState();
 * const chatStreaming = useChatStreaming(...);
 * const chatSession = useChatSession(...);
 * // ...
 *
 * // 之后（调用1个Facade）
 * const chat = useChatFacade();
 * const { session, message, streaming, send, interrupt } = chat;
 * ```
 */
export default useChatFacade;
