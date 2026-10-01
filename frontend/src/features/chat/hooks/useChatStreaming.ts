// 编辑历史: 2026-09-30 10:44:56 小欧 - sendMessage/clearSteps 改直连 chatStreamStore
//   （桥接透传成员已删，北京老陈授权按可靠性标准裁定）— 小欧-2026-09-30 10:44:56：
//   §sendMessage 不再经 useChatStreamSession 透传，useCallback 内部直连
//     chatStreamStore.sendMessage(customSessionId ?? sessionId, content, mode)，
//     依赖数组 remove 桥接透传身份，改 module 级稳定引用 + sessionId（memo 更简）；
//   §clearSteps 由"桥接解构"改为本文件 useCallback 直连 chatStreamStore.clearSteps(sessionId)，
//     对外签名 () => void 与 UseChatStreamingReturn 接口一致（矛盾 D 消费面签名不变）；
//   §调用链收敛为「useChatStreaming→store」直线，与本项目既有直连惯例同构
//     （useChatInit:81 / useChatTaskControl:162 / useChatSession:568-569）。
// 编辑历史: 2026-08-26 小欧 - 参与改造: SSE流式状态管理改造(事件分发/暂停续传)
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
// 编辑历史: 2026-09-15 20:13:04 小欧 - 注释清理: 去除取消链路遗留代号, 改描述性术语 — 小欧-2026-09-15 20:13:04
// 编辑历史: 2026-09-17 小欧 - 统一拒绝事件 type="rejected": ①deniedEntries 数据结构新增 reject_type 字段; ②markDenied 函数新增 reject_type 参数; ③删除旧 sseOnError/handleDenied; ④新增统一 handleRejected 函数 - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 - 实施: 新增 waitClock 钟面信号透传(返回类型接口声明/从 useSSE 解构/return 暴露) - 小欧-2026-09-17
// 编辑历史: 2026-09-28 小欧 - 活跃任务注入(设计[76] 6.14 实施回填): callbacks 解构加 onMerged 并透传 useSSE(中层原漏, 链路断) - 小欧-2026-09-28
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.8: useSSE 删除(5.6)改订阅 Store(useChatStreamSession);
//   9 具名回调收敛为 StreamEvent 单入口分发(授权改 pendingAuthorization 快照驱动, 见 5.15);
//   删 disconnectWithParams(唯一生产消费者 useChatTaskControl 5.14 改走 Store.stop)与 setIsReceiving 注入;
//   config.baseURL/token 首连消费移交 setTransportConfig(5.3, 应用初始化一次性注入) — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-30 14:30 小欧 - 删 deniedSteps 改由 deniedEntries 派生（两套口径致误判全拒）；切会话复位会话级 ref
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

import { useCallback, useState, useEffect, useMemo } from 'react'; // 2026-09-06 小欧 B2(6.4A): useEffect 持久化被拒点名条 — 小欧-2026-09-06
import type { UseChatStateReturn } from './useChatState';
import type { UseChatCallbacksReturn } from './useChatCallbacks';
import type { ExecutionStep } from '../../../types/execution';
import type { Message } from '../../../types/chat';
// [63] 5.8：useSSE 已删（5.6）——订阅桥接 Store，事件走 StreamEvent 单入口
import { useChatStreamSession } from '@/features/chat/streams/useChatStreamSession';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import type { StreamEvent } from '@/features/chat/streams/backupTypes';
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
  // 流式接收状态（[63] 5.8：状态宿主已移交 Store，本层只读快照，不再暴露 setter）
  isReceiving: boolean;

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
  deniedEntries: ReadonlyMap<
    number,
    // 2026-09-30 小欧 - tool/reason 转**可选**：无名条目也要入表（保证计数），显示侧由渲染层过滤。
    Array<{ tool?: string; reason?: string; reject_type?: string }>
  >;

  // Refs - 用于累积流式内容（供外部访问）
  streamingContentRef: React.MutableRefObject<string>;

  executionStepsRef: React.MutableRefObject<ExecutionStep[]>;

  // 【小强 2026-04-22】executeSend - 完整的发送流程
  executeSend: (userMessage: Message) => Promise<void>;

  // 2026-09-17 小欧 实施: 心跳等待感知钟面信号透传 — 小欧-2026-09-17
  waitClock: import('@/types/sse').ClockSignals;
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
 * @param _config - SSE配置（[63] 5.8：baseURL/token 首连消费已移交 setTransportConfig，
 *   本层不再读取；形参保留以免改动 facade 调用形状）
 * @returns SSE相关状态和操作
 */
export const useChatStreaming = (
  state: UseChatStateReturn,
  callbacks: UseChatCallbacksReturn,
  _config: SSEConfig
): UseChatStreamingReturn => {
  const {
    sessionId,
    setSessionId,
    cancelInProgressRef,
    isPausedRef,
    displayBufferRef,
    hasReceivedCancelEventRef,
    logFlagsRef,
  } = state;
  const {
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onMerged, // 2026-09-28 小欧: 注入应答回调透传(设计[76] 6.14 实施回填) — 小欧-2026-09-28
    onRetry,
  } = callbacks;

  // 2026-09-06 小欧 B2(6.4, 北京老陈裁定): 被拒工具点名条聚合(Map: step→[{tool,reason}] 按工具去重),
  //   供 ToolCallLine 对被拒工具显橘红灰字点名单 — 小欧-2026-09-06
  //
  // 2026-09-30 小欧 - 删独立 deniedSteps state 改由 deniedEntries 派生：原两套计数口径致
  //   `deniedCount >= candidateCount` 量纲不一致（同一工具拒 2 次即误判"全部拒绝"而提前停齿轮）
  const [deniedEntries, setDeniedEntries] = useState<
    ReadonlyMap<
      number,
      Array<{ tool?: string; reason?: string; reject_type?: string }>
    >
  >(new Map());
  // 派生视图：每 step 的"被拒条目数" = 被拒的不同工具数（与 candidateCount 同量纲）
  const deniedSteps = useMemo<ReadonlyMap<number, number>>(
    () =>
      new Map(Array.from(deniedEntries, ([step, list]) => [step, list.length])),
    [deniedEntries]
  );
  const markDenied = useCallback(
    (step: number, tool?: string, reason?: string, reject_type?: string) => {
      if (typeof step === 'number' && step >= 0) {
        // 2026-09-30 小欧 - 无条件建条目，删掉 `if (tool && reason)` 护栏。
        //   病根：沿用护栏时 tool 缺失不建条目 → 派生计数丢失 → 齿轮不停（功能退化）；
        //   "tool 缺失也必须计数"是已裁定硬需求。无名工具不显示于点名条，由渲染侧过滤，
        //   但必须计入 —— 二者分层职责。
        setDeniedEntries((prev) => {
          const next = new Map(prev);
          const existing = next.get(step) ?? [];
          if (tool && existing.some((e) => e.tool === tool)) return prev; // 同一 tool 不重复入列
          next.set(step, [...existing, { tool, reason, reject_type }]);
          return next;
        });
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
              parsed as Array<
                [
                  number,
                  Array<{
                    tool?: string;
                    reason?: string;
                    reject_type?: string;
                  }>,
                ]
              >
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

  // 2026-09-16 小欧: 统一拒绝事件 type="rejected" — 替代旧 error(blocked/timeout) + user_rejected
  //   合并为统一的 handleRejected 函数，接收 reject_type 参数
  // 2026-09-17 小欧 会审V3(#9): 外层 if(tool_name && reject_type) 护栏删除——护栏会把整回调包死,
  //   tool_name 缺失时齿轮(deniedSteps)不再停转; markDenied 内部已有 step≥0 计数护栏杆,
  //   点名条聚合自带 tool&&reason 条件, 分层职责清晰 — 小欧-2026-09-17
  const handleRejected = useCallback(
    (data: {
      step: number;
      message: string;
      tool_name?: string;
      reject_type: string;
    }) => {
      // 统一聚合到 deniedEntries，传递 reject_type 供 UI 显示不同图标
      markDenied(data.step, data.tool_name, data.message, data.reject_type);
    },
    [markDenied]
  );

  // [63] 5.8 v1.29：原 9 具名回调参数收敛为 StreamEvent 单入口分发（kind→payload 按 5.1 判别联合窄化）；
  //   授权不走事件——由 pendingAuthorization 快照驱动（5.15），故 onAuthorizationRequired 已从回调链移除
  const dispatchStreamEvent = useCallback(
    (ev: StreamEvent) => {
      switch (ev.kind) {
        case 'step':
          onStep(ev.payload.step);
          break;
        case 'chunk':
          onChunk(ev.payload.chunk, ev.payload.isReasoning);
          break;
        case 'complete':
          onComplete(ev.payload.full, ev.payload.meta, ev.payload.steps);
          break;
        case 'error':
          onError(ev.payload);
          break;
        case 'paused':
          // 2026-09-29 小欧：真实 onPaused/onResumed 均为零参（useChatCallbacks.ts:103-104），
          //   confirmId 的 HITL 归属由 Store hitlWaitingKeys 承载（5.3 onPaused/onResumed 内部）
          onPaused();
          break;
        case 'resumed':
          onResumed();
          break;
        case 'retry':
          onRetry(ev.payload.message, ev.payload.waitTime);
          break;
        case 'rejected':
          handleRejected(ev.payload);
          break;
        case 'merged':
          // 2026-09-29 小欧：[76] 6.14 注入应答事件（5.3 storeHandlers 接线），漏则提示条/高亮永不触发
          onMerged(ev.payload.mergedIntoTaskId);
          break;
      }
    },
    [
      onStep,
      onChunk,
      onComplete,
      onError,
      onPaused,
      onResumed,
      onRetry,
      onMerged,
      handleRejected,
    ]
  );

  // 使用 Store 订阅桥接
  // 小欧 2026-09-10 S2收尾(方案A): executionStepsRef 唯一真源在 Store，此处从 5.5 透出的推导视图取
  // 2026-09-30 小欧 - 本 hook 改直连 chatStreamStore，桥接触敛为纯订阅（理由见文件尾编辑历史）
  const {
    isReceiving,
    executionSteps,
    executionStepsRef, // 推导视图（5.4 getExecutionStepsRef），非第二真源
    currentResponse,
    serverTaskId,
    metaFrames, // 【小欧 2026-08-26 8.4.14】任务元信息帧快照透传
    waitClock, // 2026-09-17 小欧 实施: 钟面信号 — 小欧-2026-09-17
  } = useChatStreamSession(sessionId, dispatchStreamEvent);

  // 从state中获取Refs
  const {
    streamingContentRef,
    // 【小强 2026-04-22】需要解构的Refs和状态setters
    currentSessionIdRef,
    replyUserMessageIdRef,
    waitTimerRef,
  } = state;

  // 【小强 2026-04-22】从state解构需要的setters
  const { setLoading, setWaitTime, setIsRetrying, setMessages, setIsPaused } =
    state;

  // 2026-09-30 小欧 - 会话切换时复位**会话级** ref（与 useChatCallbacks 内同名 effect 配对，
  //   两组各在其所有者内复位，不跨层、不扩 facade 接口面）。
  //   病根：Store 已按 sessionId 严格隔离，但这批视图 ref 是全局单例、四条切换入口无一复位
  //   → 跨会话污染。最重实证：A 取消中（cancelInProgressRef=true）→ 切 B → B 的取消被
  //   useChatTaskControl 守卫直接 return → B 的取消按钮永久失效。
  //   只清会话相关：userScrolledUpRef / messagesEndRef / messagesCountRef 属视图级全局，
  //   跨会话应保留滚动位置，一并清会引入新退化。
  useEffect(() => {
    cancelInProgressRef.current = false;
    hasReceivedCancelEventRef.current = false;
    isPausedRef.current = false;
    // 2026-09-30 小欧 - 补 state 侧配对：isPausedRef 是写侧、isPaused state 是读侧，
    //   useChatState 的同步 effect deps 是 [isPaused]，state 未变则不同步 → 只清 ref 会
    //   造成 ref=false / state=true 分裂（下游按 state 读，仍以为在暂停）。
    setIsPaused(false);
    // 2026-09-30 小欧 - 补清等待计时器：A 会话等待中的 interval 切到 B 后仍在跑，
    //   持续 setWaitTime 污染 B 的等待秒数（原复位清单漏了它）。
    if (waitTimerRef.current !== null) {
      clearInterval(waitTimerRef.current);
      waitTimerRef.current = null;
    }
    displayBufferRef.current = [];
    streamingContentRef.current = '';
    replyUserMessageIdRef.current = null;
    // 日志标志归零（chunkFirstDone / showSteps*Done）：跨会话残留会让新会话首块 chunk 不再打点、
    // 或步骤显示判断被上一会话的"已打点"状态污染（LogFlags 三字段全为一次性闸门）。
    logFlagsRef.current = {
      chunkFirstDone: false,
      showStepsFalseDone: false,
      showStepsTrueDone: false,
    };
  }, [
    sessionId,
    cancelInProgressRef,
    hasReceivedCancelEventRef,
    isPausedRef,
    displayBufferRef,
    streamingContentRef,
    replyUserMessageIdRef,
    logFlagsRef,
    waitTimerRef,
    setIsPaused,
  ]);

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
        // 2026-09-30 小欧 - **删除** setDeniedSteps(new Map()) —— deniedSteps 已降级为
        //   deniedEntries 的派生视图，清唯一真源即自动清零，无需第二处同步（消除漏改点）。
        setDeniedEntries(new Map()); // 2026-09-06 小欧 B2(6.4): 新任务同步清空被拒工具点名条 — 小欧-2026-09-06
        // 2026-09-06 小欧 B2(6.4A): 新任务删独立键, 防带旧会话/旧任务点名残留 — 小欧-2026-09-06
        sessionStorage.removeItem(`${DENIED_STORAGE_KEY}_${sessionId}`);
        sessionStorage.removeItem(
          `${DENIED_STORAGE_KEY}_${customSessionId ?? sessionId}`
        );

        // 调用 Store 的 sendMessage（内部先落盘 queued 再 POST）——
        // 2026-09-30 小欧 直连 chatStreamStore，不再经桥接透传（签名保持 customSessionId 优先）
        await chatStreamStore.sendMessage(
          customSessionId ?? sessionId ?? '',
          content,
          contextLinkMode
        );
      } catch (error) {
        console.error('发送消息失败:', error);
        throw error;
      }
    },
    [
      sessionId, // 2026-09-30 小欧 直连后替换原桥接透传身份依赖
      streamingContentRef,

      executionStepsRef, // 2026-08-28 小强 修复#14: 清空executionStepsRef, 防旧数据残留
    ]
  );

  // 2026-09-30 小欧 - clearSteps 改直连 chatStreamStore（原经桥接透传）。
  //   签名 () => void 与对外契约一致（UseChatStreamingReturn.clearSteps 不变）。
  //   引用随 sessionId 稳定：sessionId 是父级字符串，变化即换绑定，与 executeSend 同源。
  const clearSteps = useCallback(
    () => chatStreamStore.clearSteps(sessionId ?? ''),
    [sessionId]
  );

  // 【小强 2026-04-22】executeSend - 完整的发送流程
  // 迁移自：NewChatContainer.tsx 的 executeStreamSend 函数
  const executeSend = useCallback(
    async (
      userMessage: Message,
      contextLinkMode?: 'linked' | 'independent'
    ) => {
      // 2026-09-15 小欧 v1.3: executeSend起点兜底复位 — 极端终态帧丢失时新消息必达
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
    executionSteps,
    currentResponse,

    // SSE操作
    sendMessage,
    clearSteps,
    serverTaskId: serverTaskId || null,
    metaFrames, // 【小欧 2026-08-26 8.4.14】任务元信息帧快照透传
    waitClock, // 2026-09-17 小欧 实施: 钟面信号透传 — 小欧-2026-09-17
    deniedSteps, // 2026-09-06 小欧 B2(方案C): 拒绝/拦截/超时执行轮集合, 供流水线停齿轮 — 小欧-2026-09-06
    deniedEntries, // 2026-09-06 小欧 B2(6.4): 被拒工具点名条集合, 供 ToolCallLine 对被拒工具显橘红灰字 — 小欧-2026-09-06

    // Refs
    streamingContentRef,

    executionStepsRef,

    // 【小强 2026-04-22】executeSend
    executeSend,
  };
};
