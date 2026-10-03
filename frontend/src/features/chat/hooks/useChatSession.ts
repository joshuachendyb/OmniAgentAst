// 编辑历史: 2026-08-22 小欧 - sessionModel 结构化: state 类型 SessionModelOverride | null; loadSession/initializeSession 读 result.sessionModel
// 编辑历史: 2026-08-26 小欧 - 参与改造: 会话生命周期对接sessionModel/版本冲突
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 删编辑标题辅助函数/删未用messages/deps补setSessionModelOverride
// 编辑历史: 2026-08-27 小欧 - hooks修复: 重试计数改由 ref 持久化, 破除 options.retryCount 永不回写导致的无限重试死循环
// 编辑历史: 2026-08-28 小强 - hooks修复#13: 删不可达if(urlSessionId)分支+删重复onLoadingEnd(只保留finally中)
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.18: generationRef 代际守卫(三异步入口各++, 四个 await 后断言,
//   根治"旧 session 异步结果过期污染新会话" G3 病根); L1修正① handleNewSession 删断流+清步骤
//   (新会话不断旧流); L1修正② handleClear 改 stop+clearSteps(显式清空=用户明确终止意图);
//   streaming 参数与 UseChatStreamingReturn import 零消费整删(5.18 参数收敛) — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-30 14:30 小欧 - loadSession 补写 setMessages；loading 复位进 finally；URL 写入上抛；合并透传壳
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.7 + 5.10.3(c): 消费 setLinkEnabled 并在 5 处注入 —— 场景3 加载最近会话
//   (result.linkEnabled ?? false, F5 刷新恒走该路径)、场景2 缓存恢复(restored.linkEnabled)、三处复位(新建/清空/失败)
//   归 false。缓存恢复分支原以"与 setSessionModelOverride 同构"为由不注入, 但那是复制既有缺口而非正当性:
//   漏注入则 UI 显示关、DB 为 true, 用户一次点击即被静默改坏真源。 — 小欧-2026-10-03
/**
 * useChatSession Hook - 会话生命周期管理
 *
 * 功能：
 * - 会话状态管理（sessionId, sessionTitle, sessionVersion, titleLocked等）
 * - 会话函数（loadSession, handleNewSession, handleClear, updateSessionTitle等）
 * - 会话标题编辑和版本控制
 *
 * 设计说明：
 * - 集中管理所有会话相关状态和逻辑
 * - 处理会话加载、创建、清空、标题更新等操作
 * - 处理版本冲突和错误处理
 *
 * @author 小强
 * @version 2.0.0
 * @since 2026-04-21
 */

import { useCallback, useRef } from 'react';
import type { Message, SessionModelOverride } from '../../../types/chat';
import type { UseChatStateReturn } from './useChatState';
import { sessionApi } from '../../../services/api/session.api';
// 2026-09-30 小欧 - 标题生成已迁出本 hook（S4：纯文案拼装不属生命周期编排）
import { generateNewSessionTitle } from '@/utils/sessionTitle';
// [63] 5.18：stop/clearSteps + 代际守卫（G3 病根修复）
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import {
  loadHistoryMessages,
  loadLatestHistoryMessages,
  STORAGE_KEY,
} from '../../../utils/chatHistory';
import {
  showNewSessionSuccess,
  showNewSessionRetryWarning,
  showNewSessionError,
  showLoadErrorWithKey,
  showSaveError,
} from '../../../utils/chatMessages';

// ============================================================================
// 类型定义
// ============================================================================

/**
 * useChatSession Hook返回值
 */
export interface UseChatSessionReturn {
  // 会话状态
  sessionId: string | null;
  sessionTitle: string;
  sessionVersion: number;
  titleLocked: boolean;
  editingTitle: boolean;
  titleInput: string;
  lastSavedTitle: string;
  sessionModelOverride: SessionModelOverride | null;
  setSessionModelOverride: (v: SessionModelOverride | null) => void;
  setLinkEnabled: (v: boolean) => void;

  // 会话函数
  loadSession: (sessionId: string) => Promise<Message[]>;
  handleNewSession: (retry?: number) => Promise<void>;
  handleClear: () => void;
  updateSessionTitle: (newTitle: string) => Promise<void>;
  initializeSession: (
    options: InitializeSessionOptions
  ) => Promise<InitializeSessionResult>;

  // 标题编辑函数
  setEditingTitle: (editing: boolean) => void;
  setTitleInput: (input: string) => void;
  setLastSavedTitle: (title: string) => void;

  // Refs
  currentSessionIdRef: React.MutableRefObject<string | null>;
}

/**
 * initializeSession 方法的参数
 */
export interface InitializeSessionOptions {
  searchParams: URLSearchParams;
  retryCount: Record<string, number>;
  setRetryCount: (
    fn: (prev: Record<string, number>) => Record<string, number>
  ) => void;
  isLoadingHistoryRef: React.MutableRefObject<boolean>;
  setIsInitialized: (v: boolean) => void;
  restoreState: () => Promise<{
    messages: Message[];
    sessionId: string | null;
    sessionTitle: string;
    sessionVersion: number;
    linkEnabled: boolean;
  } | null>;
  onLoadingStart: () => void;
  onLoadingEnd: () => void;
  onRenderStart: () => void;
  onRenderEnd: () => void;
  // 2026-09-30 小欧 - 删 onMessageListLoadingStart：解构进来后函数体零调用（原先靠
  //   eslint-disable no-unused-vars 压着），属接口污染（O1）。配套删 useChatInit 的定义与传参。
  onMessageListLoadingEnd: () => void;
}

/**
 * initializeSession 方法的返回值
 */
export interface InitializeSessionResult {
  loaded: boolean;
  fromCache: boolean;
  hasUrlSession: boolean;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatSession - 会话生命周期管理
 *
 * 迁移自：NewChatContainer.tsx 中的会话相关逻辑
 * - 会话状态管理
 * - 会话加载、创建、清空
 * - 标题编辑和版本控制
 * - 错误处理和重试逻辑
 *
 * @param state - useChatState返回的状态对象
 * @returns 会话相关状态和函数
 */
export const useChatSession = (
  state: UseChatStateReturn,
  /**
   * 2026-09-30 小欧 - URL 写入的唯一出口（依赖注入，不引隐式 Router 上下文）。
   *   病根：原直接调 history.pushState/replaceState 绕过 Router，而 pushState 不派发
   *   popstate、Router 收不到通知 → urlSessionId 恒为旧值 → 陈旧 URL 优先于真实会话
   *   → 写旧会话而界面读新会话（两个真源分叉）。改为只上抛意图、由页面层用 Router 写。
   *   传 null = 清 URL 参数；不传 = 本 hook 不写 URL（无 Router 场景，YAGNI）。
   */
  onUrlSessionChange?: (sessionId: string | null) => void
): UseChatSessionReturn => {
  // [63] 5.18 v1.29：代际号——三异步入口各 ++，await 后比对，旧代结果一律丢弃（G3 病根）
  const generationRef = useRef(0);

  // 从state中解构需要的状态和setter
  const {
    sessionId,
    setSessionId,
    sessionTitle,
    setSessionTitle,
    sessionVersion,
    setSessionVersion,
    titleLocked,
    setTitleLocked,
    editingTitle,
    setEditingTitle,
    titleInput,
    setTitleInput,
    lastSavedTitle,
    setLastSavedTitle,
    sessionModelOverride,
    setSessionModelOverride,
    setLinkEnabled,
    setMessages,
    currentSessionIdRef,
  } = state;

  // 2026-08-27 小欧 修复: 重试计数持久化 ref, 避免闭包内读取的 options.retryCount 永为初始 {} 而无限重试
  const sessionRetryRef = useRef<Record<string, number>>({});

  // ========================================
  // 会话加载函数
  // ========================================

  /**
   * loadSession - 加载会话历史
   * 迁移自：NewChatContainer.tsx 第1207行
   */
  const loadSession = useCallback(
    async (sid: string): Promise<Message[]> => {
      // [63] 5.18 v1.29 会话切换竞态：代际号单调递增，旧代异步结果一律丢弃
      //   （loadSession / initializeSession / handleNewSession 三入口各取一代）
      const generation = ++generationRef.current;
      try {
        const result = await loadHistoryMessages(sid);
        if (generation !== generationRef.current) return []; // 旧代过期：丢弃
        if (result) {
          setSessionId(result.sessionId);
          currentSessionIdRef.current = result.sessionId;
          setSessionTitle(result.title || '新会话');
          setSessionVersion(result.version || 1);
          setTitleLocked(result.title_locked || false);
          setLastSavedTitle(result.title || '新会话');
          setSessionModelOverride(result.sessionModel ?? null);
          setLinkEnabled(result.linkEnabled ?? false);
          // 2026-09-30 小欧 - 补写 setMessages：其余分支都写，唯独本成功分支漏写。
          //   病根：漏写 + 上游 void 丢弃返回值，两处叠加致返回值彻底蒸发 →
          //   刷新进会话消息恒空；会话间切换则保留上个会话消息（跨会话串消息）。
          setMessages(result.messages || []);
          return result.messages || [];
        }
        // 2026-09-30 小欧 - 失败路径也必须清理，不能只清成功路径。
        //   病根：URL 已切到新会话后本分支既不写也不清 → chatState.messages 保留上个会话内容，
        //   而 title/sessionId 语境已是新会话 → 跨会话串消息（与成功分支漏写同型）。
        //   404 = 会话确实不存在 → 按"空会话"清理；与 initializeSession 的 404 分支保持对称。
        setMessages([]);
        setSessionId(null);
        setLinkEnabled(false);
        setLastSavedTitle('新会话');
        return [];
      } catch (error) {
        console.error('加载会话失败:', error);
        showLoadErrorWithKey('加载失败', sid);
        // 网络/5xx 不等于"会话不存在"：不清状态，保留当前界面，交由调用方重试，
        // 否则弱网切会话会把用户正在看的内容清空。
        return [];
      }
    },
    [
      setSessionId,
      setSessionTitle,
      setSessionVersion,
      setTitleLocked,
      setLastSavedTitle,
      setMessages, // 2026-09-30 小欧: 成功分支与 404 分支均已写入，补进依赖
      setSessionModelOverride, // 2026-08-27 小欧 三堂会审: 补全依赖
      setLinkEnabled,
      currentSessionIdRef,
    ]
  );

  /**
   * initializeSession - 初始化会话（核心入口）
   * 迁移自：NewChatContainer.tsx loadSession useEffect (第838-1055行)
   *
   * 处理三种互斥场景：
   * 1. URL指定会话 -> loadHistoryMessages
   * 2. 缓存恢复 -> restoreState
   * 3. 最近会话 -> loadLatestHistoryMessages
   */
  const initializeSession = useCallback(
    async (
      options: InitializeSessionOptions
    ): Promise<InitializeSessionResult> => {
      // [63] 5.18：初始化取新代，切入中的旧 load 作废
      const generation = ++generationRef.current;
      const {
        searchParams,
        setRetryCount,
        isLoadingHistoryRef,
        setIsInitialized,
        restoreState,
        onLoadingStart,
        onLoadingEnd,
        onRenderStart,
        onRenderEnd,
        onMessageListLoadingEnd,
      } = options;

      const urlSessionId = searchParams.get('session_id');

      // 检测是否是强制刷新（Ctrl+F5或Cmd+Shift+R）
      const navigationEntry = performance.getEntriesByType(
        'navigation'
      )?.[0] as PerformanceNavigationTiming | undefined;
      const isReload = navigationEntry?.type === 'reload';

      if (isReload) {
        console.log('🔄 检测到刷新操作，清除sessionStorage缓存');
        sessionStorage.removeItem(STORAGE_KEY);
      }

      // 场景1: URL指定会话
      if (urlSessionId) {
        const retryKey = `session-load-${urlSessionId}`;
        // 2026-08-27 小欧 修复: currentRetry 以 ref 为准(跨递归持久), 不再读永不更新的 options.retryCount
        const currentRetry = sessionRetryRef.current[retryKey] || 0;

        // 如果正在加载中，跳过此次调用
        if (isLoadingHistoryRef.current) {
          console.log('⏭️ 正在加载中，跳过重复调用');
          onLoadingEnd();
          return { loaded: false, fromCache: false, hasUrlSession: true };
        }

        isLoadingHistoryRef.current = true;
        onLoadingStart();
        onRenderStart();
        // 2026-09-30 小欧 - 标记"本层已自行释放锁"：递归重试那条路径会在 return 前显式释放，
        //   而 `return expr` 是先求值 expr 再执行 finally，递归体内已重新上锁并点亮 loading，
        //   若 finally 无条件复位会把它清掉（锁失效 + 指示器提前消失）。
        let releasedLock = false;

        try {
          const result = await loadHistoryMessages(urlSessionId);
          if (generation !== generationRef.current)
            return { loaded: false, fromCache: false, hasUrlSession: true };
          if (result) {
            setSessionId(result.sessionId);
            currentSessionIdRef.current = result.sessionId;
            setMessages(result.messages);
            setSessionTitle(result.title);
            if (result.version !== undefined) {
              setSessionVersion(result.version);
            }
            if (result.title_locked !== undefined) {
              setTitleLocked(result.title_locked);
            }
            setLastSavedTitle(result.title || '新会话');
            setSessionModelOverride(result.sessionModel ?? null);
            setLinkEnabled(result.linkEnabled ?? false);

            onMessageListLoadingEnd();
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
            // 2026-08-27 小欧 修复: 同步重置 ref 计数
            sessionRetryRef.current[retryKey] = 0;

            console.log(
              '🔵 从URL加载会话:',
              urlSessionId,
              '标题:',
              result.title,
              '版本:',
              result.version
            );
            return { loaded: true, fromCache: false, hasUrlSession: true };
          } else {
            // URL会话没有消息（可能已被删除/404），清理状态+URL参数
            console.warn('🔴 URL会话不存在，清除URL参数和状态:', urlSessionId);
            setSessionId(null);
            currentSessionIdRef.current = null;
            setMessages([]);
            setSessionTitle('新会话');
            setSessionVersion(1);
            setTitleLocked(false);
            setSessionModelOverride(null);
            setLinkEnabled(false);
            setLastSavedTitle('新会话');
            // 2026-09-30 小欧 - 删原生 replaceState，改上抛意图交页面层用 Router 写（见第二参注释）
            onUrlSessionChange?.(null);

            return { loaded: false, fromCache: false, hasUrlSession: false };
          }
        } catch (error) {
          console.warn('加载URL会话失败:', error);

          // 重试机制 - 最多3次
          if (currentRetry < 3) {
            const newRetry = currentRetry + 1;
            // 2026-08-27 小欧 修复: 写入 ref 计数(跨递归持久), 并同步 React state
            sessionRetryRef.current[retryKey] = newRetry;
            setRetryCount((prev) => ({ ...prev, [retryKey]: newRetry }));

            // 2026-09-30 小欧 - 必须先释放 loading 锁再递归：`return expr` 是先求值 expr
            //   再执行 finally，故递归会卡在"正在加载中"被拦 → 重试由 4 次退化为 1 次。
            isLoadingHistoryRef.current = false;
            onLoadingEnd();
            onRenderEnd();
            releasedLock = true;

            // 延迟1秒后重试
            await new Promise((resolve) => setTimeout(resolve, 1000));
            return initializeSession(options); // 递归重试
          } else {
            // 超过重试次数
            setRetryCount((prev) => ({ ...prev, [retryKey]: 0 }));
            // 2026-08-27 小欧 修复: 同步重置 ref 计数
            sessionRetryRef.current[retryKey] = 0;
            return { loaded: false, fromCache: false, hasUrlSession: true };
          }
        } finally {
          // 2026-09-30 小欧 - loading 复位移入 finally 单一出口。
          //   病根：原复位散在 4 处分支，而代际守卫早退发生在复位点之前 → 锁卡在 true
          //   → 后续初始化全被"正在加载中"拦下 → 会话初始化死锁（loading 圈永转）。
          //   onLoadingEnd/onRenderEnd 幂等，故取代原各分支内复位而非叠加。
          //   releasedLock 分支跳过：递归已在上层重新上锁，此处复位会把它清掉。
          if (!releasedLock) {
            isLoadingHistoryRef.current = false;
            onLoadingEnd();
            onRenderEnd();
          }
        }
      }

      // 场景2: 缓存恢复
      if (!urlSessionId) {
        const restored = await restoreState();
        if (generation !== generationRef.current)
          return { loaded: false, fromCache: false, hasUrlSession: true };
        if (restored) {
          console.log('🟢 从缓存恢复会话状态');
          setSessionId(restored.sessionId);
          currentSessionIdRef.current = restored.sessionId;
          setMessages(restored.messages);
          setSessionTitle(restored.sessionTitle);
          setSessionVersion(restored.sessionVersion);
          setLastSavedTitle(restored.sessionTitle);
          // 缓存恢复必须注入会话级真源(复制 setSessionModelOverride 的缺口不构成正当性; 漏注入则 UI 显示关而 DB 为 true)。
          setLinkEnabled(restored.linkEnabled);
          // 2026-08-27 小欧 修复#55: 缓存恢复分支补调onRenderEnd/onMessageListLoadingEnd(URL加载分支已调用, 此处遗漏导致渲染/加载结束信号缺失)
          onRenderEnd();
          onMessageListLoadingEnd();

          onLoadingEnd();
          isLoadingHistoryRef.current = false;
          return { loaded: true, fromCache: true, hasUrlSession: false };
        }
      }

      // 场景3: 加载最近会话
      // 2026-08-28 小强 修复#13: 删除不可达if(urlSessionId)分支(场景1已return)

      // 检查是否正在加载
      if (isLoadingHistoryRef.current) {
        console.log('⏭️ 正在加载中，跳过重复调用');
        onLoadingEnd();
        setIsInitialized(true);
        return { loaded: false, fromCache: false, hasUrlSession: false };
      }

      isLoadingHistoryRef.current = true;
      onLoadingStart();
      onRenderStart();

      try {
        const result = await loadLatestHistoryMessages();
        if (generation !== generationRef.current)
          return { loaded: false, fromCache: false, hasUrlSession: false };
        if (result) {
          setSessionId(result.sessionId);
          currentSessionIdRef.current = result.sessionId;
          setSessionTitle(result.title);
          if (result.version !== undefined) {
            setSessionVersion(result.version);
          }
          if (result.title_locked !== undefined) {
            setTitleLocked(result.title_locked);
          }
          setLastSavedTitle(result.title);

          setLinkEnabled(result.linkEnabled ?? false);
          setMessages(result.messages);

          onMessageListLoadingEnd();

          console.log(
            '🟡 加载最近会话:',
            result.sessionId,
            '标题:',
            result.title,
            '版本:',
            result.version
          );
        } else {
          console.log('🟡 没有找到任何会话，显示新会话界面');
          setSessionTitle('新会话');
          setMessages([]);
          setSessionId(null);
          setLastSavedTitle('新会话');
          onMessageListLoadingEnd();
        }

        setIsInitialized(true);
        return { loaded: true, fromCache: false, hasUrlSession: false };
      } catch (error) {
        console.warn('加载最近会话失败:', error);
        setIsInitialized(true);
        return { loaded: false, fromCache: false, hasUrlSession: false };
      } finally {
        // 2026-09-30 小欧 - 同上方 URL 分支，loading 复位移入 finally 单一出口
        isLoadingHistoryRef.current = false;
        onLoadingEnd();
        onRenderEnd();
      }
    },
    [
      setSessionId,
      setMessages,
      setSessionTitle,
      setSessionVersion,
      setTitleLocked,
      setLastSavedTitle,
      setSessionModelOverride, // 2026-08-27 小欧 三堂会审: 补全依赖
      setLinkEnabled,
      currentSessionIdRef,
      onUrlSessionChange, // 2026-09-30 小欧 - URL 写入出口入依赖（闭包新鲜度）
    ]
  );

  // ========================================
  // 会话操作函数
  // ========================================

  // 2026-09-30 小欧 - generateNewSessionTitle 已迁至 utils/sessionTitle.ts
  //   （S4：纯文案拼装混在生命周期编排里，违反 SRP），本处改为直接调用。

  /**
   * handleNewSession - 新建会话（支持重试机制）
   * 迁移自：NewChatContainer.tsx handleNewSessionInternal
   * 2026-09-30 小欧 - 原先另有 handleNewSession 作为纯透传壳（仅 return handleNewSessionInternal(retry)），
   *   属"无透传函数"违反；现把实现并入本函数、对外签名与成员名不变，壳与多余成员一并消除。
   */
  const handleNewSession = useCallback(
    async (retry: number = 0): Promise<void> => {
      // [63] 5.18：新建取新代（重试递归再取新代，自身一致）
      const generation = ++generationRef.current;
      const maxRetries = 3;

      try {
        // 生成智能标题
        const newTitle = generateNewSessionTitle();
        const response = await sessionApi.createSession(newTitle);
        if (generation !== generationRef.current) return; // 旧代过期：丢弃
        const newSessionId = response.session_id;

        setSessionId(newSessionId);
        currentSessionIdRef.current = newSessionId;
        setSessionTitle(newTitle);
        setSessionVersion(1);
        setTitleLocked(false);
        setSessionModelOverride(null);
        setLinkEnabled(false);
        setLastSavedTitle(newTitle);

        // [63] 5.18 v1.29：删"断开之前SSE+清steps"（L1：新会话不断旧流、不清旧步——旧流留
        //   Store 由订阅关系自然让位；视图按新 sessionId 读到的自然是新会话快照，无需手工清）

        // 添加系统提示消息
        const systemMessage: Message = {
          id: (Date.now() + 1000).toString(),
          role: 'system',
          content: '💡 新会话已创建！开始与AI助手对话吧。',
          timestamp: new Date(),
        };
        setMessages([systemMessage]);

        // 清除sessionStorage
        sessionStorage.removeItem(STORAGE_KEY);

        // 2026-09-30 小欧 - 删原生 pushState，改上抛意图交页面层用 Router 写（见第二参注释）
        //   配套：useChatInit 已加幂等守卫，URL 更新触发的 effect 重跑不会重复初始化
        onUrlSessionChange?.(newSessionId);

        showNewSessionSuccess(newTitle);
      } catch (error: unknown) {
        const err = error as { message?: string };
        if (retry < maxRetries) {
          const newRetry = retry + 1;
          showNewSessionRetryWarning(newRetry, maxRetries);
          // 延迟1秒后重试
          await new Promise((resolve) => setTimeout(resolve, 1000));
          return handleNewSession(newRetry);
        }
        const errMsg = err?.message || '未知错误';
        showNewSessionError(errMsg);
      }
    },
    [
      setSessionId,
      setSessionTitle,
      setSessionVersion,
      setTitleLocked,
      setMessages,
      setLastSavedTitle,
      setSessionModelOverride,
      setLinkEnabled,
      currentSessionIdRef,
      onUrlSessionChange, // 2026-09-30 小欧 - URL 写入出口入依赖（闭包新鲜度）
    ]
  );

  /**
   * handleClear - 清空对话
   * 迁移自：NewChatContainer.tsx handleClear
   */
  const handleClear = useCallback(() => {
    console.log('[useChatSession] handleClear - 清空对话');

    // [63] 5.18 v1.29 L1 修正②：用户显式"清空"必须真停（与 5.14 停止语义同源），
    //   与"关视图不停任务"红线并存不悖——切页面不断流，切会话也不断流，唯"清空"是用户明确终止意图。
    //   清步骤走 Store（清步骤与删备份同一动作，5.4 clearSteps），stop 为 async 故不阻塞 UI 复位。
    const sidToStop = sessionId ?? '';
    if (sidToStop) {
      void chatStreamStore.stop(sidToStop);
      chatStreamStore.clearSteps(sidToStop);
    }

    setSessionId(null);
    currentSessionIdRef.current = null;
    setSessionTitle('新会话');
    setSessionVersion(1);
    setTitleLocked(false);
    setMessages([]);
    setSessionModelOverride(null); // 2026-08-27 小欧 修复#41: 清空会话复位L2模型, 避免新会话继承旧模型覆盖
    setLinkEnabled(false); // 同源复位会话级 link 开关, 避免新会话继承旧开关
    setLastSavedTitle('新会话');
  }, [
    sessionId,
    setSessionId,
    setSessionTitle,
    setSessionVersion,
    setTitleLocked,
    setMessages,
    setLastSavedTitle,
    setSessionModelOverride,
    setLinkEnabled,
    currentSessionIdRef,
  ]);

  // ========================================
  // 标题管理函数
  // ========================================

  /**
   * updateSessionTitle - 更新会话标题
   * 迁移自：NewChatContainer.tsx 中的标题更新逻辑
   */
  const updateSessionTitle = useCallback(
    async (newTitle: string) => {
      if (!sessionId || !newTitle.trim()) {
        return;
      }

      try {
        const response = await sessionApi.updateSession(
          sessionId,
          newTitle.trim(),
          sessionVersion
        );

        setSessionTitle(newTitle.trim());
        setSessionVersion(response.version || sessionVersion);
        setLastSavedTitle(newTitle.trim());

        console.log('✅ 标题更新成功:', newTitle, '版本:', response.version);
      } catch (error: unknown) {
        const err = error as {
          message?: string;
          response?: { status?: number };
        };
        const errMsg = err?.message || '更新标题失败';
        if (err?.response?.status === 409) {
          // 版本冲突，重新加载最新数据
          console.warn('⚠️ 标题版本冲突，重新加载最新数据');
          try {
            const result = await loadHistoryMessages(sessionId);
            if (result) {
              setSessionTitle(result.title || newTitle);
              setSessionVersion(result.version || sessionVersion + 1);
              setTitleLocked(result.title_locked || false);
              setLastSavedTitle(result.title || newTitle);

              // 提示用户重新编辑
              showSaveError('会话标题已被其他人修改，已自动更新为最新版本');
            }
          } catch (syncError) {
            console.error('同步最新数据失败:', syncError);
            showSaveError('同步最新数据失败，请刷新页面重试');
          }
        } else {
          showSaveError(errMsg);
        }
        throw error;
      }
    },
    [
      sessionId,
      sessionVersion,
      setSessionTitle,
      setSessionVersion,
      setTitleLocked,
      setLastSavedTitle,
    ]
  );

  // ========================================
  // 返回值
  // ========================================

  return {
    // 会话状态
    sessionId,
    sessionTitle,
    sessionVersion,
    titleLocked,
    editingTitle,
    titleInput,
    lastSavedTitle,

    // 会话函数
    loadSession,
    initializeSession,
    handleNewSession,
    handleClear,
    updateSessionTitle,

    // 标题编辑函数
    setEditingTitle,
    setTitleInput,
    setLastSavedTitle,

    // 会话级模型覆盖(L2)
    sessionModelOverride,
    setSessionModelOverride,
    setLinkEnabled,

    // Refs
    currentSessionIdRef,
  };
};
