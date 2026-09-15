// 编辑历史: 2026-08-26 小欧 - 参与P1-P7: SSE流式状态管理改造(8.4/8.6 事件分发/暂停续传)
// 编辑历史: 2026-08-27 小欧 - 三堂会审H1修复: executeSend内sendMessage加await闭合SSE发送Promise, 防拒绝变unhandled rejection/占位消息永久悬挂
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - hooks修复#10: disconnect参数语义纠偏(force->manualDisconnect, stopServer->clearStorage)
// 编辑历史: 2026-08-28 小强 - hooks修复#14: sendMessage开头清executionStepsRef+disconnectWithParams参数映射确认
// 编辑历史: 2026-09-06 小欧 - B2方案C(北京老陈裁定): 拒绝/拦截/超时三路聚合 deniedStepSet(Map step→denied计数,
//   deniedCount>=tools.length 停齿轮)——handleDenied(独立 user_rejected 回调) + sseOnError(blocked/timeout
//   error 事件带 step 过滤聚合, 不触发红字/liveErrorText); 注入 useSSE 第10参 — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定 被拒工具 UI 灰字痕迹): 聚合升级——
//   ①markDenied 两参→三参(step, tool?, reason?): tool 有名时同步聚合 deniedEntries(Map step→[{tool,reason}] 去重),
//   reason=user_rejected.content / blocked/timeout 的 error_message(两路拒绝理由可见);
//   ②sseOnError 取 SSEError.tool_name、handleDenied 三参透传——承 ToolCallLine 被拒工具点名橘红灰字 — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4A, 北京老陈裁定: 本会话恢复被拒灰字): deniedEntries 独立键持久化
//   sessionStorage(与 steps 备份同生命周期概念)——①恢复: sessionId 变化读键回填(无记录置空) ②持久化:
//   deniedEntries 非空写键(序列化 entries 数组) ③sendMessage/disconnect(clearStorage) 同步删键防陈旧残留;
//   换会话/重启即失, 与"本会话够用"定案一致 — 小欧-2026-09-06
// 编辑历史: 2026-09-09 小欧 - 会话页console日志治理(北京老陈指示「该清理的清理」): executeSend 删 3 处调试噪音——
//   ①🔍客户端信息(整对象打印) ②🔍在调用AI之前先保存用户消息(整 userMessage 打印) ③🔍assistant消息ID(占位ID计算过程);
//   保留启动/保存成功/404清空/未找到sessionId/失败 等真实流程锚点打点 — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 等待心跳打点(北京老陈「UI冻住/日志不完整」实证): executeSend waitTimer
//   每秒 waitTime+1 时每5秒 console 打点「已等待后端响应 Ns」, 终结等待期 console 一片空白
//   「像假死/日志不完整」的误判; 实证 waitTime 全链 0 处 .tsx 消费(从不展示等待秒数), 心跳打点为最低代价活性证据 — 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: 删streamingStepsRef类型声明+解构+清空+依赖数组(110/280/306/330/352/531);
//   阶段二S2提前实施: useSSE新增第12参externalExecutionStepsRef透传state.executionStepsRef, executionStepsRef改从useSSE解构
//   (263行), state解构删除executionStepsRef(280行) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段二S2收尾(方案A): useSSE删除第12参externalExecutionStepsRef(唯一真源独立useRef),
//   此处删除传参state.executionStepsRef(285行), executionStepsRef仍从useSSE解构(264行) — 小欧-2026-09-10
// 编辑历史: 2026-09-13 小欧 - Prettier 格式统一(前端源码格式专项, 纯格式零逻辑): 对齐项目 prettier 排版规范 — 小欧-2026-09-13
// 编辑历史: 2026-09-15 20:13:04 小欧 - P-008注释清理: 去除取消链路[41]遗留F5代号, 改描述性术语 — 小欧-2026-09-15 20:13:04
/**
 * useChatStreaming Hook - SSE协议与流式状态管理
 *
 * 功能：
 * - 管理SSE连接和流式状态
 * - 提供发送消息、中断任务等操作
 * - 集成useChatCallbacks中的回调函数
 * - 提供executeSend方法处理完整发送流程
 *
 * 设计说明：
 * - 作为SSE连接的核心管理Hook
 * - 依赖useChatState和useChatCallbacks
 * - 提供完整的SSE功能接口
 *
 * @author 小强
 * @version 2.1.0
 * @since 2026-04-21
 * @update 2026-04-22 添加executeSend方法，迁移executeStreamSend逻辑
 */

import { useCallback, useState, useEffect } from 'react'; // 2026-09-06 小欧 B2(6.4A): useEffect 持久化被拒点名条 — 小欧-2026-09-06
import type { UseChatStateReturn } from './useChatState';
import type { UseChatCallbacksReturn } from './useChatCallbacks';
import type { ExecutionStep } from '../../../types/execution';
import type { Message } from '../../../types/chat';
import { useSSE } from '@/hooks/useSSE';
import { sessionApi } from '../../../services/api/session.api';
import { getClientInfo } from '../../../utils/clientInfo';
import { handleError } from '@/services/error/handler';

// 2026-09-06 小欧 B2(6.4A, 北京老陈裁定): 被拒工具点名条 sessionStorage 备份 key——
//   与 useSSE.ts:43 `sse_execution_steps_backup`(steps 备份)平行命名, 本会话内刷新/重看恢复点名灰字 — 小欧-2026-09-06
const DENIED_STORAGE_KEY = 'sse_denied_entries_backup';

// ============================================================================
// 类型定义
// ============================================================================

/**
 * SSE配置参数
 */
export interface SSEConfig {
  baseURL: string;
  sessionId: string | null;
}

/**
 * useChatStreaming Hook返回值
 */
export interface UseChatStreamingReturn {
  // 流式接收状态
  isReceiving: boolean;
  setIsReceiving: (receiving: boolean) => void;

  // 执行步骤
  executionSteps: ExecutionStep[];

  // 当前响应
  currentResponse: string;

  // SSE操作
  sendMessage: (
    content: string,
    sessionId?: string,
    contextLinkMode?: 'linked' | 'independent'
  ) => Promise<void>;
  disconnect: (
    stopServer?: boolean,
    force?: boolean,
    callback?: () => void
  ) => void; // 2026-08-27 小欧 修复#10: 签名语义 force->manualDisconnect, stopServer->clearStorage
  clearSteps: () => void;

  // 服务器任务ID
  serverTaskId: string | null;

  // 任务元信息帧（8.4.14 透传）
  metaFrames: import('@/types/sse').TaskMetaFrames;

  // 2026-09-06 小欧 B2(方案C, 北京老陈裁定): 拒绝/拦截/超时的工具执行轮 step 聚合(Map: step→denied计数, 两路来源:
  //   独立 user_rejected 事件 + error 通道 blocked/timeout), 供流水线"齿轮停转/灰字"整批计数判定;
  //   error 事件仍不进 executionSteps(8.4.5 收敛设计不动), 仅此按 step 记计数 — 小欧-2026-09-06
  deniedSteps: ReadonlyMap<number, number>;

  // 2026-09-06 小欧 B2(6.4, 北京老陈裁定): 被拒工具点名条聚合(Map: step→[{tool, reason}]),
  //   user_rejected(独立事件, reason=content) + blocked/timeout(error 通道, reason=error_message) 两路 — 小欧-2026-09-06
  deniedEntries: ReadonlyMap<number, Array<{ tool: string; reason: string }>>;

  // Refs - 用于累积流式内容（供外部访问）
  streamingContentRef: React.MutableRefObject<string>;

  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;

  // 【小强 2026-04-22】executeSend - 完整的发送流程
  executeSend: (userMessage: Message) => Promise<void>;
}

// ============================================================================
// Hook实现
// ============================================================================

/**
 * useChatStreaming - SSE协议与流式状态管理
 *
 * 迁移自：NewChatContainer.tsx 中的SSE相关逻辑
 * - useSSE Hook配置和调用
 * - 发送消息、中断任务等操作
 * - 流式状态管理
 * - executeStreamSend 完整逻辑（2026-04-22迁移）
 *
 * @param state - useChatState返回的状态对象
 * @param callbacks - useChatCallbacks返回的回调函数
 * @param config - SSE配置（baseURL, sessionId）
 * @returns SSE相关状态和操作
 */
export const useChatStreaming = (
  state: UseChatStateReturn,
  callbacks: UseChatCallbacksReturn,
  config: SSEConfig
): UseChatStreamingReturn => {
  const { sessionId, setSessionId, cancelInProgressRef } = state;
  const {
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onRetry,
    onAuthorizationRequired,
  } = callbacks;

  // 2026-09-06 小欧 B2(方案C, 北京老陈裁定): 拒绝(user_rejected独立事件)/拦截(blocked)/超时(timeout) 的
  //   工具执行轮 step 计数聚合(Map: step→denied计数), 供流水线"齿轮停转/灰字"整批计数判定;
  //   error 事件仍不进 executionSteps(8.4.5 收敛), 仅在此按 step 记计数——聚合复用三 deny 型
  //   与后端 safety_gate/sandbox_gate 发射点同集合 — 小欧-2026-09-06
  const [deniedSteps, setDeniedSteps] = useState<ReadonlyMap<number, number>>(
    new Map()
  );
  // 2026-09-06 小欧 B2(6.4, 北京老陈裁定): 被拒工具点名条聚合(Map: step→[{tool,reason}] 按工具去重),
  //   供 ToolCallLine 对被拒工具显橘红灰字点名单 — 小欧-2026-09-06
  const [deniedEntries, setDeniedEntries] = useState<
    ReadonlyMap<number, Array<{ tool: string; reason: string }>>
  >(new Map());
  const markDenied = useCallback(
    (step: number, tool?: string, reason?: string) => {
      if (typeof step === 'number' && step >= 0) {
        setDeniedSteps((prev) => {
          const next = new Map(prev);
          next.set(step, (next.get(step) ?? 0) + 1);
          return next;
        });
        // 2026-09-06 小欧 B2(6.4): tool 有名才聚点名条(拒绝事件带 tool_name 是灰字链路前提), 按工具去重 — 小欧-2026-09-06
        if (tool && reason) {
          setDeniedEntries((prev) => {
            const next = new Map(prev);
            const existing = next.get(step) ?? [];
            if (!existing.some((e) => e.tool === tool))
              next.set(step, [...existing, { tool, reason }]);
            return next;
          });
        }
      }
    },
    []
  );

  // 2026-09-06 小欧 B2(6.4A, 北京老陈裁定): 被拒工具点名条本会话持久化——
  //   恢复: sessionId 变化时读独立键回填现有会话的被拒灰字(无记录置空, 防切任务残留旧会话点名);
  //   存储格式: Map→entries 数组 [[step, [{tool,reason}]], …], 可 JSON 序列化 — 小欧-2026-09-06
  useEffect(() => {
    const key = `${DENIED_STORAGE_KEY}_${sessionId}`;
    try {
      const raw = sessionStorage.getItem(key);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          setDeniedEntries(
            new Map(
              parsed as Array<[number, Array<{ tool: string; reason: string }>]>
            )
          );
        }
      } else {
        setDeniedEntries(new Map());
      }
    } catch (e) {
      console.warn('[SSE] 解析 sessionStorage 被拒点名条失败:', e);
      sessionStorage.removeItem(key);
      setDeniedEntries(new Map());
    }
  }, [sessionId]);

  // 持久化: deniedEntries 非空时写独立键(流式聚合增长即跟写), 空则不动(避免覆盖恢复态/残留由删键接管) — 小欧-2026-09-06
  useEffect(() => {
    const key = `${DENIED_STORAGE_KEY}_${sessionId}`;
    try {
      if (deniedEntries.size > 0) {
        sessionStorage.setItem(
          key,
          JSON.stringify(Array.from(deniedEntries.entries()))
        );
      }
    } catch (e) {
      console.warn('[SSE] 保存 sessionStorage 被拒点名条失败:', e);
    }
  }, [deniedEntries, sessionId]);

  // 2026-09-06 小欧 B2: 拦截(blocked)/超时(timeout) 仍走 error 通道(北京老陈裁定), 其错误对象现带 step ——
  //   在此过滤聚合 deniedSteps(不打断原有 onError 红字提示链路); user_rejected 已独立事件不含此路 — 小欧-2026-09-06
  const sseOnError = useCallback(
    (error: string | import('@/types/sse').SSEError) => {
      if (typeof error === 'object' && error !== null) {
        const _e = error as import('@/types/sse').SSEError;
        if (_e.error_type === 'blocked' || _e.error_type === 'timeout') {
          // 2026-09-06 小欧 B2(6.4): 事件带被拒工具名与理由, 聚合点名条(deniedEntries) — 小欧-2026-09-06
          if (typeof _e.step === 'number')
            markDenied(_e.step, _e.tool_name, _e.error_message);
        }
      }
      onError?.(error);
    },
    [onError, markDenied]
  );

  // 2026-09-06 小欧 B2: 独立拒绝事件回调(不占 error 通道, 无红字) — 小欧-2026-09-06
  const handleDenied = useCallback(
    (step: number, message: string, toolName?: string) => {
      // 2026-09-06 小欧 B2(6.4): toolName 透传, 聚合点名条(reason=拒绝消息) — 小欧-2026-09-06
      markDenied(step, toolName, message);
    },
    [markDenied]
  );

  // 使用useSSE Hook
  // 小欧 2026-09-10 S2收尾(方案A): useSSE 唯一真源，此处从 useSSE 解构 executionStepsRef
  const {
    isReceiving,
    setIsReceiving,
    executionSteps,
    executionStepsRef, // 小欧 2026-09-10 S2: 从 useSSE 取（useSSE 唯一真源）
    currentResponse,
    sendMessage: sendStreamMessage,
    disconnect,
    clearSteps,
    serverTaskId,
    metaFrames, // 【小欧 2026-08-26 8.4.14】任务元信息帧快照透传
  } = useSSE(
    {
      baseURL: config.baseURL,
      sessionId: sessionId || 'default-session',
    },
    onStep,
    onChunk,
    onComplete,
    sseOnError, // 2026-09-06 小欧 B2: 包装聚合 blocked/timeout 到 deniedStepSet — 小欧-2026-09-06
    onPaused,
    onResumed,
    onRetry,
    onAuthorizationRequired, // 【v3.4新增 2026-06-09 小沈】
    handleDenied // 2026-09-06 小欧 B2: 独立拒绝事件聚合到 deniedStepSet — 小欧-2026-09-06
  );

  // 从state中获取Refs
  const {
    streamingContentRef,
    // 【小强 2026-04-22】需要解构的Refs和状态setters
    currentSessionIdRef,
    replyUserMessageIdRef,
    waitTimerRef,
  } = state;

  // 【小强 2026-04-22】从state解构需要的setters
  const { setLoading, setWaitTime, setIsRetrying, setMessages } = state;

  // 发送消息函数（包装useSSE的sendMessage）
  const sendMessage = useCallback(
    async (
      content: string,
      customSessionId?: string,
      contextLinkMode?: 'linked' | 'independent'
    ) => {
      try {
        // 清理之前的流式内容
        streamingContentRef.current = '';

        executionStepsRef.current = []; // 2026-08-28 小强 修复#14: 清空executionStepsRef, 防旧数据残留
        setDeniedSteps(new Map()); // 2026-09-06 小欧 B2: 新任务清空 denied 标记(与 executionSteps 同生命周期) — 小欧-2026-09-06
        setDeniedEntries(new Map()); // 2026-09-06 小欧 B2(6.4): 新任务同步清空被拒工具点名条 — 小欧-2026-09-06
        // 2026-09-06 小欧 B2(6.4A): 新任务删独立键, 防带旧会话/旧任务点名残留 — 小欧-2026-09-06
        sessionStorage.removeItem(`${DENIED_STORAGE_KEY}_${sessionId}`);
        sessionStorage.removeItem(
          `${DENIED_STORAGE_KEY}_${customSessionId ?? sessionId}`
        );

        // 调用useSSE的sendMessage
        return await sendStreamMessage(
          content,
          customSessionId,
          contextLinkMode
        );
      } catch (error) {
        console.error('发送消息失败:', error);
        throw error;
      }
    },
    [
      sendStreamMessage,
      streamingContentRef,

      executionStepsRef,
      sessionId, // 2026-09-06 小欧 B2(6.4A): 删独立键依赖, 防陈旧会话闭包 — 小欧-2026-09-06
    ]
  );

  // 【小沈 2026-04-22】中断任务函数
  // 2026-08-27 小欧 修复#51/B3: 参数名与底层disconnect对齐, 消除stopServer语义混淆
  // 2026-08-27 小欧 修复#10: 底层 useSSE.disconnect 签名为 (manualDisconnect, clearStorage, onDisconnect)。
  //   force 控制 manualDisconnect(禁止自动重连), stopServer 控制 clearStorage; 此前 force 被误当 clearStorage 传入, 语义反转。
  // 编辑历史: 2026-08-28 小欧 - BUG14b修复: disconnect参数用局部变量避免字面量匹配翻转语义
  const disconnectWithParams = useCallback(
    (stopServer?: boolean, force?: boolean, callback?: () => void) => {
      const manualDisconnect = force ?? false;
      const clearStorage = stopServer ?? true;
      disconnect(manualDisconnect, clearStorage, callback);
      // 2026-09-06 小欧 B2(6.4A): 清 storage 时同步删被拒点名条独立键(与 steps 备份同清), 防陈旧残留 — 小欧-2026-09-06
      if (clearStorage) {
        sessionStorage.removeItem(`${DENIED_STORAGE_KEY}_${sessionId}`);
      }
      // 清理流式状态
      streamingContentRef.current = '';

      executionStepsRef.current = []; // 2026-08-28 小强 修复#14: disconnect时清executionStepsRef
    },
    [disconnect, streamingContentRef, executionStepsRef, sessionId] // 2026-09-06 小欧 B2(6.4A): sessionId 入依赖 — 小欧-2026-09-06
  );

  // 【小强 2026-04-22】executeSend - 完整的发送流程
  // 迁移自：NewChatContainer.tsx 的 executeStreamSend 函数
  const executeSend = useCallback(
    async (
      userMessage: Message,
      contextLinkMode?: 'linked' | 'independent'
    ) => {
      // 2026-09-15 小欧 [41]v1.3: executeSend起点兜底复位 — 极端终态帧丢失时新消息必达
      cancelInProgressRef.current = false;

      // 1. 启动等待计时器
      setLoading(true);
      setWaitTime(0);
      setIsRetrying(false);
      if (waitTimerRef.current) {
        clearInterval(waitTimerRef.current);
      }
      waitTimerRef.current = setInterval(() => {
        setWaitTime((t: number) => {
          const nt = t + 1;
          // 【2026-09-09 小欧 等待心跳】后端响应间隔>5s 时 console 每5秒打点一次"已等待N秒",
          //   终结"等待期 console 一片空白→疑似日志不完整/前端假死"的误判(UI 冻住 实证:
          //   waitTime 全链 0 处 .tsx 消费, 等待秒数从不展示, UI 20s 空档完全静止) — 小欧-2026-09-09
          if (nt % 5 === 0) {
            console.log(`⏳ [心跳] 已等待后端响应 ${nt}s, 流式持续接收中...`);
          }
          return nt;
        });
      }, 1000);
      clearSteps();

      // 2. 保存用户消息到后端
      const currentSessionId = currentSessionIdRef.current || sessionId;

      let backendUserMessageId: number | null = null;

      if (currentSessionId) {
        try {
          // 获取客户端信息
          const clientInfo = getClientInfo();
          const saveResult = await sessionApi.saveMessage(currentSessionId, {
            role: 'user',
            content: userMessage.content,
            client_os: clientInfo.client_os,
            browser: clientInfo.browser,
            device: clientInfo.device,
            network: clientInfo.network,
          });

          // 保存用户消息ID，用于AI消息关联
          backendUserMessageId = saveResult?.message_id || null;
          replyUserMessageIdRef.current = backendUserMessageId;

          // 用后端返回的ID更新用户消息ID
          if (backendUserMessageId) {
            setMessages((prev) => {
              const newMessages = [...prev];
              const userMsgIndex = newMessages.findIndex(
                (m) => m.id === userMessage.id
              );
              if (userMsgIndex !== -1) {
                newMessages[userMsgIndex] = {
                  ...newMessages[userMsgIndex],
                  id: String(backendUserMessageId),
                };
              }
              return newMessages;
            });
          }
        } catch (error) {
          console.error('❌ [executeSend] 保存用户消息失败:', error);
          const is404 =
            (error as { response?: { status?: number } })?.response?.status ===
            404;
          if (is404) {
            console.warn(
              '🔴 [executeSend] sessionId无效(404)，清空sessionId，SSE将不带sessionId'
            );
            currentSessionIdRef.current = null;
            setSessionId(null);
          } else {
            const result = handleError(error, {
              source: 'api',
              continueOnError: true,
            });
            if (!result.shouldContinue) {
              console.warn('   └─ 保存失败且不能继续');
            }
          }
        }
      } else {
        console.warn(
          '⚠️ [executeSend] 未找到sessionId，无法保存用户消息:',
          userMessage.id
        );
      }

      // 3. 创建assistant占位消息
      const assistantId = backendUserMessageId
        ? (backendUserMessageId + 1).toString()
        : (Date.now() + 1).toString();

      const assistantMessage: Message = {
        id: assistantId,
        role: 'assistant',
        content: '🤔 AI 正在思考...',
        timestamp: new Date(),
        executionSteps: [],
        isStreaming: true,
        model: undefined,
      };
      setMessages((prev) => [...prev, assistantMessage]);

      // 4. 调用sendMessage发送
      // 2026-08-27 小欧 三堂会审H1: await闭合SSE发送Promise, 防拒绝变unhandled rejection导致占位消息永久悬挂
      await sendMessage(
        userMessage.content,
        currentSessionIdRef.current ?? sessionId ?? undefined,
        contextLinkMode
      );
    },
    [
      sessionId,
      setSessionId,
      setLoading,
      setWaitTime,
      setIsRetrying,
      setMessages,
      waitTimerRef,
      currentSessionIdRef,
      replyUserMessageIdRef,
      clearSteps,
      sendMessage,
    ]
  );

  return {
    // 流式状态
    isReceiving,
    setIsReceiving:
      setIsReceiving ||
      ((_: boolean) => {
        /* no-op */
      }),
    executionSteps,
    currentResponse,

    // SSE操作
    sendMessage,
    disconnect: disconnectWithParams,
    clearSteps,
    serverTaskId: serverTaskId || null,
    metaFrames, // 【小欧 2026-08-26 8.4.14】任务元信息帧快照透传
    deniedSteps, // 2026-09-06 小欧 B2(方案C): 拒绝/拦截/超时执行轮集合, 供流水线停齿轮 — 小欧-2026-09-06
    deniedEntries, // 2026-09-06 小欧 B2(6.4): 被拒工具点名条集合, 供 ToolCallLine 对被拒工具显橘红灰字 — 小欧-2026-09-06

    // Refs
    streamingContentRef,

    executionStepsRef,

    // 【小强 2026-04-22】executeSend
    executeSend,
  };
};
