// 编辑历史: 2026-08-28 小欧 - 由 utils/sse.ts 拆出 hook(429-1001)+工具函数(215-428 classifyError/handleSSEError/ERROR_CONFIG_MAP/calculateReconnectDelay), processSSEData拆至features/chat/services/sseParser.ts, 类型归types/sse.ts, 零逻辑变更 - 小欧-2026-08-28
// 编辑历史: 2026-08-29 小强 - 修复#25: canRetry统一以ERROR_CONFIG_MAP[errorType].retryable为权威来源, unknown直达failed; 修复#26: 空闲超时改走reconnect()重连路径而非disconnect(true)绕过重连 - 小强-2026-08-29
// 编辑历史: 2026-08-30 小欧 - 根治重连重复起任务: reconnect()空闲超时若尚无任务ID(首响应未到)即走统一错误中心判失败(不重新POST), sendMessageInternal再加兜底守卫禁止重连态无ID重POST(双任务/僵尸任务根治) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修正陈旧闭包: serverTaskId加serverTaskIdRef同步读写(parser回调同步ref+state), 内部判定全部改读ref, 使挂起reader帧/空闲定时器/重连守卫读到最新任务ID, 杜绝state闭包陈旧误判 - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: SSE-02 isReceiving加Ref防闭包陈旧(空闲超时读旧值误重连) — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 修复等待图标闪烁(北京老陈反馈): disconnect函数新增setReceiving参数(默认true),
//   重连路径传递false避免setIsReceiving(false)→true间隙导致等待图标闪烁
// 编辑历史: 2026-09-03 小欧 Bug-26: onAuthorizationRequired 类型补全 4→8 字段, 与 sseParser 下发契约一致 — 小欧-2026-09-03
// 编辑历史: 2026-09-03 小欧 P1-3: HITL等待期暂停IDLE计时（paused/badge挂起时不清IDLE），自适应backendTimeout，防60s误杀110s等待 - 小欧-2026-09-03
// 编辑历史: 2026-09-06 小欧 方案C三堂会审缺陷1修复: 每行热路径(L671循环内)processSSEData handlers 对象
//   漏传 onDenied(done 块已传) → 流式期间独立 user_rejected 事件无法触发 deniedStepSet 聚合, 拒绝不停齿轮;
//   补齐 onDenied 转发, useChatStreaming 侧 handleDenied 已注入(10参) — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 方案C观察点1/2根治(北京老陈批准方案2后端标记): sessionStorage 恢复时剔除
//   preview 预览行(仅SSE齿轮先行, 拦截/拒绝 action 本就不落库) — 刷新恢复与 DB 回放语义一致,
//   根治"刷新后无灰字工具行"(观察点1)与"双条 action"(观察点2) — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定): onDenied 回调签名两参→三参
//   (step, message, toolName?) 与 sseParser 三参回调契约对齐, 透传被拒工具名供点名条聚合 — 小欧-2026-09-06
// 编辑历史: 2026-09-07 小欧 - REQUEST-ABORT静默短路(9月优化5.3.1, 北京老陈裁定方案): 主动断开意图标记
//   disconnect()主动abort与180s fetch超时abort同型(AbortError)无法靠error区分, 以操作语义标记判别:
//   ①disconnect确有活动连接时设intentionalAbortRef并2s兜底清残留; ②catch入口读标+errorHandlerClassify===REQUEST_ABORT短路静默,
//   根治"手动停止/卸载→误判request_timeout→1s后自动重连复活任务/误弹超时warning"; 180s超时abort无标记, 仍走原重连 - 小欧-2026-09-07
// 编辑历史: 2026-09-08 小欧 - 方案二(北京老陈, 见doc-9月优化[12] 6.3): 重连N次全失败不再自动调cancel(任务可能仍在正常执行,
//   tool参数流式等假断连会被误杀), 改为轮询会话任务列表(GET /sessions/{session_id}/tasks, 复用sessionTaskApi.listTasks)
//   观察终态: 任务不存在或已终态(completed/failed/cancelled)即静默收尾, 轮询超时仍在执行才提示用户手动确认 - 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 空闲超时实证打点+类型修正(北京老陈驱动「xx 60000」toast 定位):
//   ①空闲超时触发点 readStream 加 console.warn 打点, 打印完整上下文(timeSinceLastData/thresholdMs/receiving/hitlWaiting/
//   nowIso), 复现时与 handler.ts 的 [Toast] 打点对照即可明确 60000 是 timeSinceLastData 本身还是下游 error 透传;
//   ②tsc 既有类型瑕疵修正: 轮询终态判定 status 可为 undefined 而 includes 需 string, ?? '' 兜底(语义不变) - 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 方案二实施期新增真实bug修复(测试F6/F9红→绿, 与sse-reconnect-poll用例对齐):
//   轮询无中止信号——组件卸载后轮询仍持续 listTasks 并误弹"手动确认", 用户再发新消息后旧轮询与新消息请求叠加;
//   新增 pollSignalRef+signal 中止信号(handleSSEError/pollSessionTaskStatus/useSSE 三条链路透传), 卸载/新消息置 aborted 即静默停止 - 小欧-2026-09-08
// 编辑历史: 2026-09-08 小欧 - 方案二实施期新增真实bug修复(测试F10红→绿): 正常完成流后未清理残留 idle 定时器,
//   60s后僵尸 reconnect 再造重连链/再生轮询; connect 成功路径补 idleTimeoutRef 清理(clearTimeout+置null) - 小欧-2026-09-08
// 编辑历史: 2026-09-09 小欧 - A类死代码清理: disconnect内去reconnectTimeoutRef解构(196-205) — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - 存量warning清零-B10/B11: :589 disconnect的eslint-disable注释原错位于}行末未生效,
//   移至依赖数组行上方使生效+写明理由; :975 attemptReconnect依赖数组真补onError — 小欧-2026-09-09
// 编辑历史: 2026-09-09 小欧 - saveStepsToStorage防抖: 原实现每个SSE事件排队setTimeout(0)宏任务,
//   N个事件→N次同步JSON.stringify(fullSteps)+sessionStorage.setItem, 累积O(N²)阻塞主线程,
//   React渲染被推迟导致UI冻结; 改为300ms防抖, 合并连续事件只保留最后一次保存 — 小欧-2026-09-09
// 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: 删reconnectConfigRef.enabled字段+设置代码(418/596-601);
//   阶段一S8超时改名: fetchTimeoutRef→firstChunkTimeoutRef(442/549/677/712);
//   阶段一S1.3: processSSEData调用删除第3参isProcessingRef(796/837);
//   阶段二S2提前实施: 新增第12参externalExecutionStepsRef, executionStepsRef优先用外部ref,
//   useSSE返回值暴露executionStepsRef供useChatStreaming透传(1070行) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段二S2收尾(方案A): 删第12参externalExecutionStepsRef, useSSE恢复独立useRef
//   唯一真源(无外部注入依赖, 不可能分裂) — 小欧-2026-09-10
// 编辑历史: 2026-09-10 小欧 - 阶段三S15收尾: 组件卸载cleanup追加 hitlWaitingKeysRef.current.clear(),
//   HITL等待key Set卸载即归零, 封死abort竞态窗口旧流帧add残留口子(disconnect已断流清定时器, 此行为防御完备)
//   — 小欧-2026-09-10
import { useState, useCallback, useRef, useEffect } from 'react';
import { useStateWithRef } from './useStateWithRef'; // 小欧 2026-09-10 S14: state/ref 双写同步
// import { message } from "antd";  // 已迁移到errorHandler统一处理
import {
  handleSSEError as errorHandlerHandleSSE,
  ErrorType,
  classifyError as errorHandlerClassify, // 2026-08-27 小欧 三堂会审H2: 引入纯分类函数替代带副作用的handleSSEError
} from '@/services/error/handler';
import { sessionTaskApi } from '../services/api/task.api'; // 2026-09-08 小欧 方案二: taskControlApi 移出(重连耗尽不再自动取消)
import type {
  SSEError,
  SSEMetadata,
  SSEConfig,
  ReconnectConfig,
  UseSSEReturn,
  SSEErrorType,
  TaskMetaFrames,
} from '@/types/sse';
import { emptyMetaFrames } from '@/types/sse';
import type { ExecutionStep } from '@/types/execution';
import { processSSEData } from '@/features/chat/services/sseParser';

// 【小强修复 2026-03-18】sessionStorage key - 用于长时间隐藏页面时备份数据
// 场景：用户切换到其他应用→页面隐藏→SSE 连接不断开→后端数据持续发送
// 问题：浏览器降频导致回调延迟执行，标签页可能被丢弃
// 解决：同时保存到 ref + sessionStorage，即使标签页丢弃数据也不会丢失
const SSE_STORAGE_KEY = 'sse_execution_steps_backup';

/**
 * 错误类型分类
 * 【小强修复 2026-04-11】使用统一错误处理中心
 */
const classifyError = (error: unknown): SSEErrorType => {
  // 小欧 2026-06-25: 优先检查SSEError的error_type字段（后端直接指定）
  if (error && typeof error === 'object' && 'error_type' in error) {
    const errorType = (error as { error_type: string }).error_type;
    if (errorType === 'fc_format_error') return 'fc_format_error';
  }

  // 使用errorHandler的纯分类函数(无UI副作用, 避免误弹"正在重试")
  // 2026-08-27 小欧 三堂会审H2: 原调handleSSEError会触发虚假重试提示, 改为纯classifyError取类型
  const unifiedType = errorHandlerClassify(error);

  // 映射到SSE本地错误类型
  switch (unifiedType) {
    case ErrorType.IDLE_TIMEOUT:
      return 'idle_timeout';
    case ErrorType.REQUEST_TIMEOUT:
      return 'request_timeout';
    case ErrorType.NETWORK_ERROR:
    case ErrorType.WEAK_NETWORK:
      return 'network';
    case ErrorType.CONNECTION_REFUSED:
    case ErrorType.CONNECTION_RESET:
      return 'connection_refused';
    case ErrorType.SERVER_500:
      return 'http_500';
    case ErrorType.SERVER_502:
    case ErrorType.SERVER_503:
      return 'server';
    case ErrorType.BACKEND_ERROR:
      return 'empty_response';
    case ErrorType.REQUEST_ABORT:
      return 'request_timeout';
    default:
      return 'unknown';
  }
};

/**
 * 错误配置 - 定义每种错误类型的处理方式
 * 【小强修复 2026-04-11】使用统一错误处理中心errorHandler
 */
interface ErrorConfig {
  retryable: boolean; // 是否可重试
  maxRetries: number; // 最大重试次数
  retryDelay: number; // 重试延迟(毫秒)
  showMessage: string; // 显示的消息
  stopAction?: () => void; // 停止后的操作
}

// ============================================================
// 方案二 轮询观察模式(北京老陈 2026-09-08): 重连耗尽后不再自动取消, 轮询会话任务列表观察终态。
// 复用后端 GET /sessions/{session_id}/tasks(sessions.py:88-94) + 前端 sessionTaskApi.listTasks(task.api.ts:196-199)。
// 任务不存在或已终态(completed/failed/cancelled) → 静默收尾; 轮询超时仍未终态 → 提示用户手动确认。 — 小欧-2026-09-08
// ============================================================
const TASK_POLL_INTERVAL = 5000; // 每5秒轮询一次
const TASK_POLL_MAX = 30; // 最多30次(约2.5分钟)
const TASK_TERMINAL_STATUSES = ['completed', 'failed', 'cancelled'];

const pollSessionTaskStatus = async (params: {
  sessionId: string;
  serverTaskId: string;
  onError: ((error: SSEError) => void) | undefined;
  onSetIsReceiving: (receiving: boolean) => void;
  // 2026-09-08 小欧 F6/F9修复(实施期新增真实bug): 轮询中止信号, 组件卸载/用户再发新消息即静默停止
  signal?: { aborted: boolean };
}): Promise<void> => {
  const { sessionId, serverTaskId, onError, onSetIsReceiving, signal } = params;
  for (let i = 0; i < TASK_POLL_MAX; i++) {
    await new Promise((r) => setTimeout(r, TASK_POLL_INTERVAL));
    // 2026-09-08 小欧 F6/F9修复: 每tick前检查中止信号, 根治"unmount后轮询仍持续listTasks+误弹手动确认"
    //   与"新消息发起后旧轮询请求叠加"两个真实缺陷(见sse-reconnect-poll.test.tsx F6/F9红→绿) - 小欧-2026-09-08
    if (signal?.aborted) return;
    try {
      const res = await sessionTaskApi.listTasks(sessionId);
      const task = res.tasks.find((t) => t.task_id === serverTaskId);
      const status = task?.status;
      // 任务不存在或已终态 → 正常收尾, 不取消不误报 — 小欧-2026-09-08
      if (!task || TASK_TERMINAL_STATUSES.includes(status ?? '')) {
        console.info(
          `[SSE] 轮询终态: task=${serverTaskId} status=${status ?? 'not_found'}, 正常收尾`
        );
        onSetIsReceiving(false);
        return;
      }
      console.info(
        `[SSE] 轮询观察中: task=${serverTaskId} status=${status} (${i + 1}/${TASK_POLL_MAX})`
      );
    } catch (e) {
      console.warn(`[SSE] 轮询失败(第${i + 1}次):`, e);
    }
  }
  // 轮询超时仍未终态 → 提示用户手动处理(仍不自动取消) — 小欧-2026-09-08
  console.warn(
    `[SSE] 轮询 ${TASK_POLL_MAX} 次任务仍在执行, 提示用户手动确认 task=${serverTaskId}`
  );
  onError?.({
    type: 'error',
    error_type: 'server',
    error_message: '连接已断开且任务仍在执行，请手动确认任务状态',
    timestamp: new Date().toISOString(),
  });
};

/**
 * 统一错误处理函数
 * 【小强添加 2026-04-11】使用统一错误处理中心errorHandler
 * 【小强修复 2026-04-11】重构：使用errorHandler.handleSSEError
 */
const handleSSEError = (params: {
  error: unknown;
  errorType: SSEErrorType;
  reconnectAttempts: number;
  reconnectConfig: ReconnectConfig;
  pendingMessage: { content: string; sessionId?: string } | null;
  onReconnect?: () => void;
  onSetReconnectStatus: (
    status: 'idle' | 'connecting' | 'reconnecting' | 'failed'
  ) => void;
  onSetIsConnected: (connected: boolean) => void;
  onSetIsReceiving: (receiving: boolean) => void;
  onError: ((error: SSEError) => void) | undefined;
  reconnectTimeoutRef: React.MutableRefObject<number | null>;
  serverTaskId?: string | null; // 【北京老陈 2026-07-12 小欧】重连耗尽用于发起取消
  sessionId?: string; // 【北京老陈 2026-09-08 小欧 方案二】重连耗尽后轮询观察会话任务列表所需 sessionId
  // 2026-09-08 小欧 F6/F9修复(实施期新增真实bug): 轮询中止信号透传, 组件卸载/新消息即停止本轮轮询 - 小欧-2026-09-08
  pollSignal?: { aborted: boolean };
}) => {
  const {
    error,
    errorType,
    reconnectAttempts,
    reconnectConfig,
    pendingMessage: _pendingMessage,
    onReconnect,
    onSetReconnectStatus,
    onSetIsConnected,
    onSetIsReceiving,
    onError,
    serverTaskId,
  } = params;

  // 如果不可重试或已超过最大次数
  // 2026-08-27 小欧 修复B1: 显式Boolean, 避免 pendingMessage 对象使 canRetry 变为对象(永远truthy)导致 failed 永不触发
  // 2026-08-28 小沈 修复B3: 去掉!!pendingMessage(无pendingMessage时重连仍有意义——重建连接获取服务端响应), 与内层handleSSEError retryable判断对齐
  // 2026-08-29 小强 修复#25: canRetry以单一权威来源ERROR_CONFIG_MAP[errorType].retryable为准, 使unknown(retryable:false)直达failed而非悬空
  const errorConfig = ERROR_CONFIG_MAP[errorType];
  const canRetry =
    !!errorConfig?.retryable && reconnectAttempts < reconnectConfig.maxAttempts;

  // 使用统一错误处理中心（handleSSEError 恒返回 handled:true，无需再判 else 早退）
  // 2026-08-27 小欧 修复B1: 仅canRetry时注入onReconnect, 达到maxAttempts后停止重连;
  //   onReconnect 退避重连交由 setTimeout 调度(由 fake timers 驱动), 避免同步递归在 act 边界外执行
  errorHandlerHandleSSE(error as Error, {
    reconnectAttempts,
    maxRetries: reconnectConfig.maxAttempts,
    onReconnect: canRetry
      ? () => {
          onSetReconnectStatus('reconnecting');
          onReconnect?.();
        }
      : undefined,
  });

  if (!canRetry) {
    console.error(
      `[SSE] 超过最大重试次数(${reconnectConfig.maxAttempts})，停止重连`
    );
    onSetReconnectStatus('failed');
    onSetIsConnected(false);
    onSetIsReceiving(false);

    // 【北京老陈 2026-07-12 小欧 → 2026-09-08 小欧 方案二】重连 N 次全失败不再自动取消:
    //   任务可能仍在正常执行(tool 参数流式等, 本案例根因), 自动取消会误杀; 改为轮询会话任务列表观察终态
    //   (GET /sessions/{session_id}/tasks, 复用 sessionTaskApi.listTasks), 任务不存在或已终态即静默收尾 — 小欧-2026-09-08
    if (serverTaskId && (params.sessionId || _pendingMessage?.sessionId)) {
      console.warn(
        `[SSE] 重连 ${reconnectConfig.maxAttempts} 次均失败, 进入轮询观察 task=${serverTaskId}`
      );
      void pollSessionTaskStatus({
        sessionId: params.sessionId || _pendingMessage?.sessionId || '',
        serverTaskId,
        onError,
        onSetIsReceiving,
        signal: params.pollSignal,
      });
    }

    // 调用错误回调
    onError?.({
      type: 'error',
      error_type: errorType,
      error_message: errorType
        ? ERROR_CONFIG_MAP[errorType]?.showMessage || '连接失败'
        : '连接失败', // 【小沈修改2026-04-15】message → error_message
      timestamp: new Date().toISOString(),
    });
  }
};

/**
 * 获取错误配置 - 兼容SSE本地类型
 */
const ERROR_CONFIG_MAP: Record<SSEErrorType, ErrorConfig> = {
  idle_timeout: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: '空闲超时（长时间无数据），连接可能已断开',
  },
  request_timeout: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: '请求等待超时，服务器响应过慢',
  },
  network: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: '网络连接失败，请检查网络后重试',
  },
  server: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: '服务器错误',
  },
  empty_response: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: '模型未能生成有效回复，请尝试更换问题或稍后重试',
  },
  connection_refused: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 1000,
    showMessage: '服务器连接被拒绝，请检查后端服务是否运行',
  },
  http_500: {
    retryable: true,
    maxRetries: 3,
    retryDelay: 3000, // 500错误等待3秒
    showMessage: '服务器内部错误，请稍后重试',
  },
  unknown: {
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    showMessage: '发生未知错误',
  },
  fc_format_error: {
    // 小欧 2026-06-25: FC格式错误（可恢复，后端会自动降级到Text模式）
    retryable: false,
    maxRetries: 0,
    retryDelay: 0,
    showMessage: '工具调用格式异常，已自动切换到文本模式',
  },
};

/**
 * 计算重连延迟（指数退避 + Full Jitter）
 * 【小强修复 2026-03-18】增强重试策略，使用Full Jitter算法
 *
 * Full Jitter公式：delay = random(0, min(baseDelay * 2^attempt, maxDelay))
 * 优点：避免多客户端同时重连造成"惊群效应"
 */
const calculateReconnectDelay = (
  attempt: number,
  baseDelay: number,
  maxDelay: number
): number => {
  // 指数退避
  const exponentialDelay = baseDelay * Math.pow(2, attempt);
  // Full Jitter：在[0, exponentialDelay]范围内随机
  const jitter = Math.random() * exponentialDelay;
  // 最终延迟不超过maxDelay
  return Math.min(jitter, maxDelay);
};

export const useSSE = (
  config: SSEConfig,
  onStep?: (step: ExecutionStep) => void,
  onChunk?: (chunk: string, is_reasoning?: boolean) => void,
  onComplete?: (
    fullResponse: string,
    metadata?: string | SSEMetadata,
    executionSteps?: ExecutionStep[]
  ) => void,
  onError?: (error: string | SSEError) => void,
  onPaused?: () => void,
  onResumed?: () => void,
  // ⭐ 新增：重试回调 - 【小查修复2026-03-13】添加wait_time参数
  onRetry?: (message: string, waitTime?: number) => void,
  // 【v3.4新增 2026-06-09 小沈】授权请求回调
  onAuthorizationRequired?: (data: {
    confirm_id: string;
    tool_name: string;
    params: Record<string, unknown>;
    safety_level: string;
    // 2026-09-03 小欧 Bug-26: 类型补全 4→8 字段(与 sseParser 下发契约一致)
    trust_path?: string | null;
    auto_confirm?: boolean;
    confirm_timeout?: number;
    backend_timeout?: number;
  }) => void,
  // 2026-09-06 小欧 B2(北京老陈裁定): 独立拒绝事件回调(user_rejected 不走 error 通道) — 小欧-2026-09-06
  onDenied?: (step: number, message: string, toolName?: string) => void, // 2026-09-06 小欧 B2(6.4): 三参带被拒工具名 — 小欧-2026-09-06
): UseSSEReturn => {
  const [isConnected, setIsConnected] = useState(false);
  // 小欧 2026-09-10 S14: useStateWithRef 替换手工双写（state 驱动渲染 + ref 供异步回调读最新值）
  const [isReceiving, isReceivingRef, setIsReceiving] = useStateWithRef(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  // 小欧 2026-09-10 S2收尾(方案A): useSSE 唯一真源，独立 useRef
  const executionStepsRef = useRef<ExecutionStep[]>([]);
  // 小欧 2026-09-10 S12: 批量 commit — 每帧只 append 到 pendingSteps
  // requestAnimationFrame 合并多帧，单次 setExecutionSteps 批量更新
  const pendingStepsRef = useRef<ExecutionStep[]>([]);
  const flushScheduledRef = useRef(false);

  const flushPendingSteps = useCallback(() => {
    if (pendingStepsRef.current.length === 0) {
      flushScheduledRef.current = false;
      return;
    }
    const batch = pendingStepsRef.current.splice(0);
    setExecutionSteps((prev) => {
      const newSteps = [...prev, ...batch];
      executionStepsRef.current = newSteps;
      return newSteps;
    });
    flushScheduledRef.current = false;
  }, []);

  const scheduleFlush = useCallback(() => {
    if (!flushScheduledRef.current) {
      flushScheduledRef.current = true;
      requestAnimationFrame(flushPendingSteps);
    }
  }, [flushPendingSteps]);

  const [currentResponse, setCurrentResponse] = useState('');
  const [reconnectStatus, setReconnectStatus] = useState<
    'idle' | 'connecting' | 'reconnecting' | 'failed'
  >('idle');

  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null); // 【修复 2026-05-11 小健】fetch AbortController ref，disconnect时可abort
  const responseBufferRef = useRef('');
  const isProcessingRef = useRef(false);
  // 2026-09-07 小欧 REQUEST-ABORT静默短路(9月优化5.3.1): 主动断开意图标记
  //   disconnect()主动abort 与 180s fetch超时abort 同型(AbortError), 无法靠error区分来源,
  //   以操作语义标记: disconnect确有活动连接时设标, catch读后即清, 2s兜底清残留 - 小欧-2026-09-07
  const intentionalAbortRef = useRef(false);
  const intentionalAbortTimerRef = useRef<number | null>(null);

  // 【小欧 2026-08-26 8.4.14】任务元信息帧状态 + usage 续传去重
  const [metaFrames, setMetaFrames] =
    useState<TaskMetaFrames>(emptyMetaFrames());
  const usageAccumRef = useRef({ prompt: 0, completion: 0, total: 0 });
  const lastUsageSeqRef = useRef<number>(-1);
  // 小欧 2026-09-10 S14: useStateWithRef 替换 serverTaskId 手工双写
  const [serverTaskId, serverTaskIdRef, setServerTaskId] = useStateWithRef<string | null>(null);
  // 2026-08-30 小欧 根治陈旧闭包: reader挂起帧运行在旧render上, state版serverTaskId在空闲定时器/重连守卫闭包中读到旧null值误判;
  //   ref版始终同步最新值供内部判定, state版仅驱动UI重渲染(两者同步写入) - 小欧-2026-08-30
  // 小欧 2026-09-10 S14: syncServerTaskId 不再需要（useStateWithRef 已内置 ref 同步）
  // 小欧 2026-09-10 S14: 删除 useEffect 手动同步（useStateWithRef 已内置 ref 同步）

  // 重连相关
  const reconnectConfigRef = useRef<Omit<ReconnectConfig, 'enabled'>>({
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 10000,
  });
  const reconnectAttemptsRef = useRef(0);
  // 2026-09-08 小欧 F6/F9修复(实施期新增真实bug): 轮询中止信号ref, 组件卸载/新消息发起置aborted停止轮询 - 小欧-2026-09-08
  const pollSignalRef = useRef({ aborted: false });
  // 【北京老陈 2026-07-12 小欧】记录已收到的最大后端事件 seq，断线重连时作为 after_seq 续传
  // 小欧 2026-09-10 S3: 已处理最大 seq 语义，初始 -1（首帧 seq=0 不被误拦）
  const lastSeqRef = useRef(-1);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pendingMessageRef = useRef<{
    content: string;
    sessionId?: string;
  } | null>(null);
  // 【小欧 2026-08-26 8.14】记录最近一次发送的任务上下文模式，重连后新发送保持同一模式
  const lastContextLinkModeRef = useRef<'linked' | 'independent'>(
    'independent'
  );

  // 【小强修复 2026-03-18】SSE 空闲超时检测 - 解决页面隐藏后连接断开问题
  // 【小强修复 2026-04-09】重命名为 IDLE_TIMEOUT，更准确反映语义
  const lastDataTimeRef = useRef<number>(0); // 最后收到数据的时间
  const idleTimeoutRef = useRef<number | null>(null); // 空闲超时检测
  const firstChunkTimeoutRef = useRef<number | null>(null); // 首响应超时(180s) — 流中途活性由 idle(60s)+心跳(25s)保障
  const IDLE_TIMEOUT = 60000; // 60 秒无数据判定为断开
  // 2026-09-03 小欧 P1-3: HITL等待态（paused/highlight）时IDLE应暂停，避免60s误杀110s HITL等待
  // 小欧 2026-09-10 S15: Set 计数 — 并发 HITL 场景防误判
  const hitlWaitingKeysRef = useRef(new Set<string>());
  const isHitlWaitingRef = { get current() { return hitlWaitingKeysRef.current.size > 0; } };
  const wrappedOnPaused = useCallback((confirmId?: string) => {
    hitlWaitingKeysRef.current.add(confirmId ?? 'default');
    onPaused?.();
  }, [onPaused]);
  const wrappedOnResumed = useCallback((confirmId?: string) => {
    hitlWaitingKeysRef.current.delete(confirmId ?? 'default');
    onResumed?.();
  }, [onResumed]);

  // 【小强添加 2026-03-18】sessionStorage 备份相关
  // 恢复：组件初始化时检查是否有备份数据
  useEffect(() => {
    const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
    const savedSteps = sessionStorage.getItem(storageKey);
    if (savedSteps) {
      try {
        const parsedRaw = JSON.parse(savedSteps);
        // 小欧 2026-09-10 S19: 兼容旧格式（纯 steps 数组）和新格式（{steps, source, timestamp}）
        const parsedSteps: ExecutionStep[] = Array.isArray(parsedRaw)
          ? parsedRaw
          : (parsedRaw?.steps ?? []);
        const source: string = Array.isArray(parsedRaw) ? 'legacy' : (parsedRaw?.source ?? 'unknown');
        if (parsedSteps.length > 0) {
          console.info(`[SSE] 从 sessionStorage 恢复 ${parsedSteps.length} 步, source=${source}`);
          const restoredSteps = parsedSteps.filter(
            (s: ExecutionStep) => !(s.type === 'action' && s.preview === true)
          );
          executionStepsRef.current = restoredSteps;
          setExecutionSteps(restoredSteps);
        }
      } catch (e) {
        console.warn('[SSE] 解析 sessionStorage 备份失败:', e);
        sessionStorage.removeItem(storageKey);
      }
    }
  }, [config.sessionId]); // 仅在 sessionId 变化时检查

  // 保存到 sessionStorage 的辅助函数(防抖300ms, 合并连续事件避免O(N²)主线程阻塞)
  const saveStepsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveStepsToStorage = useCallback(
    (steps: ExecutionStep[]) => {
      if (steps.length === 0 || !config.sessionId) return;
      if (saveStepsTimerRef.current !== null)
        clearTimeout(saveStepsTimerRef.current);
      saveStepsTimerRef.current = setTimeout(() => {
        const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
        try {
          // 小欧 2026-09-10 S19: 写入元数据外壳——恢复时按 source 区分累积 vs 外部
          const envelope = {
            steps: steps,
            source: 'live' as const,
            timestamp: Date.now(),
          };
          sessionStorage.setItem(storageKey, JSON.stringify(envelope));
        } catch (e) {
          console.warn('[SSE] 保存到 sessionStorage 失败:', e);
        }
        saveStepsTimerRef.current = null;
      }, 5000); // 小欧 2026-09-10 S12: 5s 兜底快照，去主线程同步阻塞
    },
    [config.sessionId]
  );

  // 清空 sessionStorage 的辅助函数
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const clearStepsFromStorage = useCallback(() => {
    const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
    sessionStorage.removeItem(storageKey);
  }, [config.sessionId]);

  // 2026-09-09 小欧: 组件卸载时清理防抖timer, 防止卸载后仍写sessionStorage
  useEffect(() => {
    return () => {
      if (saveStepsTimerRef.current !== null) {
        clearTimeout(saveStepsTimerRef.current);
        saveStepsTimerRef.current = null;
      }
    };
  }, []);

  /**
   * 断开连接
   * @param manualDisconnect - 是否是手动中断（手动中断不允许重连）
   * @param clearStorage - 是否清空 sessionStorage（重连时设为 false，保留数据）
   * @param onDisconnect - 断开后的回调函数【方案2增强】
   * @param resetReconnectAttempts - 是否重置重连计数（重连时设为 false）
   * @param setReceiving - 是否设置isReceiving（重连时设为 false，避免等待图标闪烁）
   */
  const disconnect = useCallback(
    (
      manualDisconnect: boolean = false,
      clearStorage: boolean = true,
      onDisconnect?: () => void,
      resetReconnectAttempts: boolean = true,
      setReceiving: boolean = true
    ) => {
      // 清空 sessionStorage 备份（除非重连时明确指定不清空）
      if (clearStorage) {
        clearStepsFromStorage();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }

      // 2026-08-28 小欧 根治切页/隐藏泄漏: disconnect必须清空闲超时与fetch超时, 否则卸载后定时器在已死组件上触发handleSSEError弹toast并误重连
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
        idleTimeoutRef.current = null;
      }
      if (firstChunkTimeoutRef.current) {
        clearTimeout(firstChunkTimeoutRef.current);
        firstChunkTimeoutRef.current = null;
      }

      // 【修复 2026-05-11 小健】abort正在进行的fetch请求，防止旧流与新流并行
      if (abortControllerRef.current) {
        // 2026-09-07 小欧 REQUEST-ABORT静默短路(9月优化5.3.1): 确有活动连接才设主动断开标记,
        //   abort触发的AbortError进catch时按此标记静默, 与180s fetch超时abort(无标记,继续重连)区分 - 小欧-2026-09-07
        intentionalAbortRef.current = true;
        if (intentionalAbortTimerRef.current) {
          clearTimeout(intentionalAbortTimerRef.current);
        }
        // 兜底: 若该abort无对应catch消费(极端残留), 2s后自动清除, 防污染后续真实错误分类
        intentionalAbortTimerRef.current = window.setTimeout(() => {
          intentionalAbortRef.current = false;
          intentionalAbortTimerRef.current = null;
        }, 2000);
        try {
          abortControllerRef.current.abort();
        } catch (_e) {
          /* ignore */
        }
        abortControllerRef.current = null;
      }

      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
      setIsConnected(false);
      // 2026-09-02 小欧: 重连路径不设置isReceiving=false，避免等待图标闪烁
      if (setReceiving) {
        setIsReceiving(false);
      }
      // 2026-08-29 小强 修复#26: 非手动断开(重连路径)不强制回idle, 保留reconnecting由重连调度驱动
      if (manualDisconnect) {
        setReconnectStatus('idle');
      }
      // 2026-08-27 小欧 修复B1: 仅真正手动断开/新会话/卸载才重置重连计数; 重连路径传false避免计数被清零导致无限重连
      if (resetReconnectAttempts) {
        reconnectAttemptsRef.current = 0;
      }

      // 手动中断时清除 pendingMessage 并阻止重连
      if (manualDisconnect) {
        pendingMessageRef.current = null;

      }

      // 【方案2新增】调用断开回调
      if (onDisconnect) {
        onDisconnect();
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps -- disconnect为手动入口, 故意仅依赖sessionId(闭包全引用运行时refs) — 小欧-2026-09-09
    [config.sessionId]
  );

  /**
   * 软清理执行步骤（用于重连时保留已有步骤）
   * 只清理运行时状态，不清空已收到的 steps
   */
  const softClearSteps = useCallback(() => {
    setCurrentResponse('');
    responseBufferRef.current = '';
  }, []);

  /**
   * 清空执行步骤（完全重置，用于新对话）
   */
  const clearSteps = useCallback(() => {
    setExecutionSteps([]);
    executionStepsRef.current = [];
    setCurrentResponse('');
    responseBufferRef.current = '';
    // 2026-08-27 小欧 修复#4: 跨任务重置usage累计与seq去重, 避免新任务token被旧任务污染
    usageAccumRef.current = { prompt: 0, completion: 0, total: 0 };
    lastUsageSeqRef.current = -1;
    // 2026-08-27 小欧 修复#5: 跨任务重置metaFrames, 避免新任务串用旧统计帧
    setMetaFrames(emptyMetaFrames());
    // 【小强添加 2026-03-18】同时清空 sessionStorage 备份
    clearStepsFromStorage();
  }, [clearStepsFromStorage, setMetaFrames]);

  /**
   * 内部发送消息函数（用于重连）
   * 【小强修复 2026-04-09】重连时使用软清理，保留已收到的 steps
   */
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const sendMessageInternal = async (
    content: string,
    sessionId?: string,
    contextLinkMode?: 'linked' | 'independent'
  ) => {
    const connectStartTime = new Date().toLocaleTimeString();
    console.log(`[SSE] [连接建立] 时间=${connectStartTime}`);
    disconnect(false, false, undefined, false, false); // 2026-09-02 小欧: 重连路径不设置isReceiving=false，避免等待图标闪烁
    // 小沈修复 2026-04-21：新请求时清空 steps，重连时保留 steps
    if (reconnectAttemptsRef.current > 0) {
      softClearSteps(); // 重连：保留 steps，只清理运行时状态
    } else {
      clearSteps(); // 新请求：完全清空 steps
    }

    setIsReceiving(true);
    setIsConnected(true);
    // 2026-08-29 小强 修复#26: 重连进行中保持reconnecting状态, 不被connecting覆盖
    setReconnectStatus((prev) =>
      prev === 'reconnecting' ? prev : 'connecting'
    );

    try {
      // 【北京老陈 2026-07-12 小欧】断线重连：复用 task_id 走 GET 读同一流态缓冲，避免双 agent
      const isReconnect =
        reconnectAttemptsRef.current > 0 && !!serverTaskIdRef.current;
      // 2026-08-30 小欧 根治重复起任务: 重连中但尚无任务ID(首响应未到)时无GET续传目标, 若继续会重新POST起新任务(双任务/僵尸任务),
      //   直接抛错走catch统一错误路径终止重连; 重连计数>0保证仅重连态触发, 用户首发的正常POST不受影响 - 小欧-2026-08-30
      if (!isReconnect && reconnectAttemptsRef.current > 0) {
        throw new Error(
          'SSE 重连终止: 尚无任务ID(首响应未到), 未重复发起新任务'
        );
      }
      if (!isReconnect) {
        lastSeqRef.current = -1; // 小欧 2026-09-10 S3: 重置为已处理最大 seq 初始值
      }
      const controller = new AbortController();
      abortControllerRef.current = controller; // 【修复 2026-05-11 小健】保存到ref，disconnect时可abort
      firstChunkTimeoutRef.current = window.setTimeout(
        () => controller.abort(),
        180000
      ); // 首响应超时(180s) — 流中途活性由 idle(60s)+心跳(25s)保障

      let response: Response;
      if (isReconnect) {
        // 重连：GET /chat/stream/{task_id}?after_seq=N 续传，不重新发起对话 — 北京老陈 2026-07-12 小欧
        // 小欧 2026-09-10 S3: after_seq 改为 lastSeqRef.current + 1（续传从已处理最大 seq 的下一帧开始）
        const url = `${config.baseURL}/chat/stream/${serverTaskIdRef.current}?session_id=${encodeURIComponent(sessionId || '')}&after_seq=${lastSeqRef.current + 1}`;
        console.log(`[SSE] [重连] GET ${url} after_seq=${lastSeqRef.current + 1}`);
        response = await fetch(url, {
          method: 'GET',
          signal: controller.signal,
        });
      } else {
        // 聊天流式传输端点
        const url = `${config.baseURL}/chat/stream`;
        response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(config.token
              ? { Authorization: `Bearer ${config.token}` }
              : {}),
          },
          body: JSON.stringify({
            messages: [{ role: 'user', content: content }],
            stream: true,
            session_id: sessionId || undefined,
            context_link_mode: contextLinkMode ?? 'independent',
          }),
          signal: controller.signal,
        });
      }

      if (firstChunkTimeoutRef.current) {
        clearTimeout(firstChunkTimeoutRef.current);
        firstChunkTimeoutRef.current = null;
      }

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('响应体为空');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buffer = '';

      // 【小强修复 2026-03-18】初始化最后数据时间
      lastDataTimeRef.current = Date.now();

      // eslint-disable-next-line no-constant-condition
      while (true) {
        // 编辑历史: 2026-08-28 小欧 - BUG8修复: 重排顺序→清除旧timeout/设新timeout/更新lastDataTimeRef/再reader.read()
        if (idleTimeoutRef.current) {
          clearTimeout(idleTimeoutRef.current);
        }

        idleTimeoutRef.current = window.setTimeout(() => {
          // 2026-09-03 小欧 P1-3: HITL等待期暂停IDLE计时
          if (isHitlWaitingRef.current) return;
          const timeSinceLastData = Date.now() - lastDataTimeRef.current;
          if (timeSinceLastData >= IDLE_TIMEOUT && isReceivingRef.current) {
            console.warn(
              `[SSE] 空闲超时：已经${timeSinceLastData / 1000}秒未收到数据，判定连接断开`
            );
            // 2026-09-08 小欧 实证打点(北京老陈驱动「xx 60000」toast 定位): 打印空闲超时触发完整上下文,
            //   复现时按 F12 对照 toast 出现时刻, 即可明确 60000 是 timeSinceLastData 本身还是下游 error 透传。 — 小欧-2026-09-08
            console.warn('[SSE] ⏱️ 空闲超时触发上下文:', {
              timeSinceLastData,
              thresholdMs: IDLE_TIMEOUT,
              receiving: isReceivingRef.current,
              hitlWaiting: isHitlWaitingRef.current,
              nowIso: new Date().toISOString(),
            });
            onError?.('SSE 空闲超时：长时间未收到数据');
            // 2026-08-29 小强 修复#26: 空闲超时走重连路径而非disconnect(true)绕过重连, 确保自动重连发生
            reconnect();
          }
        }, IDLE_TIMEOUT);

        lastDataTimeRef.current = Date.now();

        const { done, value } = await reader.read();

        if (done) {
          if (buffer.trim()) {
            processSSEData(
              buffer,
              {
                setExecutionSteps,
                getCurrentExecutionSteps: () => executionStepsRef.current,
                executionStepsRef,
                saveStepsToStorage,
                onStep,
                onChunk,
                onComplete,
                onError,
                onDenied,
                onPaused: wrappedOnPaused,
                onResumed: wrappedOnResumed,
                onRetry,
                onAuthorizationRequired,
                setCurrentResponse,
                responseBufferRef,
                setIsReceiving,
                setIsConnected,
                disconnect,
                setServerTaskId, // 小欧 2026-09-10 S14: useStateWithRef 内置 ref 同步
                onSeq: (s: number) => {
                  if (s > lastSeqRef.current) lastSeqRef.current = s;
                },
                lastSeqRef, // 小欧 2026-09-10 S3: 传给 sseParser 供守卫判定
                pendingStepsRef, // 小欧 2026-09-10 S12: 批量 commit 队列
                scheduleFlush, // 小欧 2026-09-10 S12: rAF 调度刷新
                setMetaFrames,
                usageAccumRef,
                lastUsageSeqRef,
              }
            );
          }
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          processSSEData(
            line,
            {
              setExecutionSteps,
              getCurrentExecutionSteps: () => executionStepsRef.current,
              executionStepsRef,
              saveStepsToStorage,
              onStep,
              onChunk,
              onComplete,
              onError,
              // 方案C三堂会审缺陷1修复(2026-09-06 小欧): 每行热路径漏传 onDenied → 流式期间拒绝事件
              //   永远收不到回调, deniedStepSet 无法聚合停齿轮; done 块已传, 补齐此处 — 小欧-2026-09-06
              onDenied,
              onPaused: wrappedOnPaused,
              onResumed: wrappedOnResumed,
              onRetry,
              onAuthorizationRequired,
              setCurrentResponse,
              responseBufferRef,
              setIsReceiving,
              setIsConnected,
              disconnect,
              setServerTaskId, // 小欧 2026-09-10 S14: useStateWithRef 内置 ref 同步
              onSeq: (s: number) => {
                if (s > lastSeqRef.current) lastSeqRef.current = s;
              },
              lastSeqRef, // 小欧 2026-09-10 S3: 传给 sseParser 供守卫判定
              pendingStepsRef, // 小欧 2026-09-10 S12: 批量 commit 队列
              scheduleFlush, // 小欧 2026-09-10 S12: rAF 调度刷新
              setMetaFrames,
              usageAccumRef,
              lastUsageSeqRef,
            }
          );
        }
      }


      // 成功，重置重连状态
      // 2026-09-08 小欧 F10修复(实施期新增真实bug): 正常完成流后清理残留 idle 定时器,
      //   否则60s后僵尸reconnect再造重连链/再生轮询(F10红→绿) - 小欧-2026-09-08
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
        idleTimeoutRef.current = null;
      }
      setReconnectStatus('idle');
      reconnectAttemptsRef.current = 0;
      abortControllerRef.current = null; // 【修复 2026-05-11 小健】请求完成清理ref
    } catch (error: unknown) {
      // 2026-09-07 小欧 REQUEST-ABORT静默短路(9月优化5.3.1): 主动断开(disconnect abort)引发的AbortError静默收尾,
      //   不再误判为request_timeout弹warning/自动重连复活任务; 标记读后即清 - 小欧-2026-09-07
      if (
        intentionalAbortRef.current &&
        errorHandlerClassify(error) === ErrorType.REQUEST_ABORT
      ) {
        intentionalAbortRef.current = false;
        if (intentionalAbortTimerRef.current) {
          clearTimeout(intentionalAbortTimerRef.current);
          intentionalAbortTimerRef.current = null;
        }
        abortControllerRef.current = null;
        setIsConnected(false);
        setIsReceiving(false);
        console.info('[SSE] 主动断开引发的AbortError, 静默收尾');
        return;
      }

      console.error('[SSE] 请求错误:', error);
      abortControllerRef.current = null; // 【修复 2026-05-11 小健】请求失败清理ref

      // 使用统一的错误处理中心
      handleSSEError({
        error,
        errorType: classifyError(error),
        reconnectAttempts: reconnectAttemptsRef.current,
        reconnectConfig: reconnectConfigRef.current,
        pendingMessage: pendingMessageRef.current,
        onReconnect: () => {
          reconnectAttemptsRef.current++;
          // 2026-08-27 修复: 重连时传入lastContextLinkModeRef, 避免contextLinkMode丢失
          sendMessageInternal(
            content,
            sessionId,
            lastContextLinkModeRef.current
          );
        },
        onSetReconnectStatus: setReconnectStatus,
        onSetIsConnected: setIsConnected,
        onSetIsReceiving: setIsReceiving,
        onError,
        reconnectTimeoutRef,
        serverTaskId: serverTaskIdRef.current, // 【北京老陈 2026-07-12 小欧】重连耗尽用于发起取消
        sessionId: sessionId ?? config.sessionId, // 【北京老陈 2026-09-08 小欧 方案二】重连耗尽轮询观察所需 sessionId, 兜底 config.sessionId 防外层未传自定义会话时轮询静默失效 (2026-09-08 实施修正)
        pollSignal: pollSignalRef.current, // 2026-09-08 小欧 F6/F9: 轮询中止信号透传, 组件卸载/新消息即停止 - 小欧-2026-09-08
      });

      // 保存待重连的消息（用于下次重连）
      if (pendingMessageRef.current) {
        // 消息已由 handleSSEError 处理
      }
    }
  };

  /**
   * 重连函数
   * 【小强修复 2026-04-09】重新添加缺失的 reconnect 函数，移到 sendMessageInternal 之后避免变量未定义问题
   */
  const reconnect = useCallback(() => {
    if (!pendingMessageRef.current) {
      console.warn('[SSE] 没有待重连的消息');
      return;
    }

    // 2026-08-30 小欧 根治重复起任务: 重连需GET续传同一任务(after_seq), 但尚无任务ID(首响应未到)则无目标可续;
    //   继续走sendMessageInternal会重新POST起新任务(双任务/僵尸任务), 此处直接走统一错误中心判连接失败, 由用户重发 - 小欧-2026-08-30
    if (!serverTaskIdRef.current) {
      console.error(
        '[SSE] 无任务ID(首响应未到), 无续传目标, 不重复POST起任务, 判定连接失败'
      );
      handleSSEError({
        error: {
          name: 'IdleTimeoutNoTaskError',
          message: '首次响应未到，连接已中断',
        },
        errorType: 'idle_timeout',
        reconnectAttempts: reconnectConfigRef.current.maxAttempts,
        reconnectConfig: reconnectConfigRef.current,
        pendingMessage: pendingMessageRef.current,
        onReconnect: undefined,
        onSetReconnectStatus: setReconnectStatus,
        onSetIsConnected: setIsConnected,
        onSetIsReceiving: setIsReceiving,
        onError,
        reconnectTimeoutRef,
        serverTaskId: serverTaskIdRef.current,
        sessionId: pendingMessageRef.current?.sessionId, // 2026-09-08 小欧 方案二: 轮询观察 sessionId
        pollSignal: pollSignalRef.current, // 2026-09-08 小欧 F6/F9: 轮询中止信号透传 - 小欧-2026-09-08
      });
      return;
    }

    const { content, sessionId } = pendingMessageRef.current;
    const config = reconnectConfigRef.current;

    if (reconnectAttemptsRef.current >= config.maxAttempts) {
      console.error('[SSE] 超过最大重连次数');
      setReconnectStatus('failed');
      // 使用errorHandler统一处理
      const error = {
        message: 'SSE连接失败，请刷新页面重试',
        name: 'ConnectionError',
      };
      errorHandlerHandleSSE(error, {
        reconnectAttempts: config.maxAttempts,
        maxRetries: config.maxAttempts,
        onReconnect: undefined,
      });
      return;
    }

    const attempt = reconnectAttemptsRef.current;
    const delay = calculateReconnectDelay(
      attempt,
      config.baseDelay,
      config.maxDelay
    );

    setReconnectStatus('reconnecting');
    // 使用errorHandler统一处理（显示重试警告）
    const retryWarningError = {
      message: `正在重新连接 (${attempt + 1}/${config.maxAttempts})...`,
      name: 'RetryWarning',
    };
    errorHandlerHandleSSE(retryWarningError, {
      reconnectAttempts: attempt,
      maxRetries: config.maxAttempts,
      onReconnect: undefined,
    });

    console.log(`[SSE] 准备重连，attempt=${attempt + 1}, delay=${delay}ms`);

    reconnectTimeoutRef.current = setTimeout(() => {
      reconnectAttemptsRef.current++;
      sendMessageInternal(content, sessionId, lastContextLinkModeRef.current);
    }, delay);
  }, [sendMessageInternal, onError]);

  /**
   * 发送消息建立SSE连接
   */
  const sendMessage = useCallback(
    async (
      content: string,
      sessionId?: string,
      contextLinkMode?: 'linked' | 'independent'
    ) => {
      // 【修复小查问题】防止并发调用
      if (isProcessingRef.current) {
        console.warn('[SSE] 已有进行中的请求，等待完成后重试');
        // 使用errorHandler统一处理
        const error = {
          message: '请求处理中，请稍后再试',
          name: 'DuplicateClick',
        };
        errorHandlerHandleSSE(error, {
          reconnectAttempts: 0,
          maxRetries: 0,
          onReconnect: undefined,
        });
        return;
      }
      isProcessingRef.current = true;
      // 2026-09-08 小欧 F6/F9修复(实施期新增真实bug): 用户再发新消息时中止旧轮询, 防轮询请求与新一轮处理叠加 - 小欧-2026-09-08
      pollSignalRef.current.aborted = true;
      pollSignalRef.current = { aborted: false };

      // 保存待重连的消息
      pendingMessageRef.current = { content, sessionId };
      lastContextLinkModeRef.current = contextLinkMode ?? 'independent';
      reconnectAttemptsRef.current = 0;

      try {
        await sendMessageInternal(content, sessionId, contextLinkMode);
      } finally {
        // 【修复 2026-05-11 小健】用finally保证重置，防止异常时isProcessingRef永远true
        isProcessingRef.current = false;
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [
      config,
      disconnect,
      clearSteps,
      onStep,
      onChunk,
      onComplete,
      onError,
      onRetry,
    ]
  );

  // 组件卸载时清理
  useEffect(() => {
    return () => {
      disconnect();
      // 2026-09-08 小欧 F6/F9修复(实施期新增真实bug): 组件卸载即中止进行中轮询, 根治
      //   "unmount后轮询仍持续listTasks并误弹手动确认"(F6红→绿) - 小欧-2026-09-08
      pollSignalRef.current.aborted = true;
      // 【修复小查问题】清理 pendingMessageRef 避免内存泄漏
      pendingMessageRef.current = null;
      // 【小新修复 2026-03-14】额外确保 reconnectTimeoutRef 被清理
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
      // 小欧 2026-09-10 S15收尾: 组件卸载清空 HITL 等待 key Set——
      //   disconnect 已断流中止 reader（abort 竞态窗口内最多向死 Set 加一个 key，无人再读），
      //   clear() 一行封死该原理口子，卸载后状态归零，防残留语义完备 —— 小欧-2026-09-10
      hitlWaitingKeysRef.current.clear();
    };
  }, [disconnect]);

  return {
    isConnected,
    isReceiving,
    setIsReceiving, // 【方案3】暴露setter用于中断时立即更新状态
    executionSteps,
    executionStepsRef, // 小欧 2026-09-10 S2: 暴露 ref 供 useChatStreaming 透传，收敛单一真源
    currentResponse,
    sendMessage,
    disconnect,
    clearSteps,
    serverTaskId,
    setServerTaskId,
    reconnectStatus,
    reconnect,
    metaFrames, // 【小欧 2026-08-26 8.4.14】任务元信息帧快照
  };
};

export default useSSE;
