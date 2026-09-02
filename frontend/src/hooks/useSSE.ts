// 编辑历史: 2026-08-28 小欧 - 由 utils/sse.ts 拆出 hook(429-1001)+工具函数(215-428 classifyError/handleSSEError/ERROR_CONFIG_MAP/calculateReconnectDelay), processSSEData拆至features/chat/services/sseParser.ts, 类型归types/sse.ts, 零逻辑变更 - 小欧-2026-08-28
// 编辑历史: 2026-08-29 小强 - 修复#25: canRetry统一以ERROR_CONFIG_MAP[errorType].retryable为权威来源, unknown直达failed; 修复#26: 空闲超时改走reconnect()重连路径而非disconnect(true)绕过重连 - 小强-2026-08-29
// 编辑历史: 2026-08-30 小欧 - 根治重连重复起任务: reconnect()空闲超时若尚无任务ID(首响应未到)即走统一错误中心判失败(不重新POST), sendMessageInternal再加兜底守卫禁止重连态无ID重POST(双任务/僵尸任务根治) - 小欧-2026-08-30
// 编辑历史: 2026-08-30 小欧 - 修正陈旧闭包: serverTaskId加serverTaskIdRef同步读写(parser回调同步ref+state), 内部判定全部改读ref, 使挂起reader帧/空闲定时器/重连守卫读到最新任务ID, 杜绝state闭包陈旧误判 - 小欧-2026-08-30
// 编辑历史: 2026-09-02 小欧 - 44case审计修复: SSE-02 isReceiving加Ref防闭包陈旧(空闲超时读旧值误重连) — 小欧-2026-09-02
// 编辑历史: 2026-09-02 小欧 - 修复等待图标闪烁(北京老陈反馈): disconnect函数新增setReceiving参数(默认true),
//   重连路径传递false避免setIsReceiving(false)→true间隙导致等待图标闪烁
import { useState, useCallback, useRef, useEffect } from 'react';
// import { message } from "antd";  // 已迁移到errorHandler统一处理
import {
  handleSSEError as errorHandlerHandleSSE,
  ErrorType,
  classifyError as errorHandlerClassify, // 2026-08-27 小欧 三堂会审H2: 引入纯分类函数替代带副作用的handleSSEError
} from '@/services/error/handler';
import { taskControlApi } from '../services/api/task.api';
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
    reconnectTimeoutRef,
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

    // 【北京老陈 2026-07-12 小欧】重连 N 次全失败 → 才置为取消（不武断算取消）
    if (serverTaskId) {
      console.warn(
        `[SSE] 重连 ${reconnectConfig.maxAttempts} 次均失败，发起取消 task=${serverTaskId}`
      );
      taskControlApi.cancel(serverTaskId).catch(() => {});
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
  }) => void
): UseSSEReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isReceiving, setIsReceiving] = useState(false);
  const isReceivingRef = useRef(false);
  const [executionSteps, setExecutionSteps] = useState<ExecutionStep[]>([]);
  const executionStepsRef = useRef<ExecutionStep[]>([]);
  const [currentResponse, setCurrentResponse] = useState('');
  const [reconnectStatus, setReconnectStatus] = useState<
    'idle' | 'connecting' | 'reconnecting' | 'failed'
  >('idle');

  const eventSourceRef = useRef<EventSource | null>(null);
  const abortControllerRef = useRef<AbortController | null>(null); // 【修复 2026-05-11 小健】fetch AbortController ref，disconnect时可abort
  const responseBufferRef = useRef('');
  const isProcessingRef = useRef(false);

  // 【小欧 2026-08-26 8.4.14】任务元信息帧状态 + usage 续传去重
  const [metaFrames, setMetaFrames] =
    useState<TaskMetaFrames>(emptyMetaFrames());
  const usageAccumRef = useRef({ prompt: 0, completion: 0, total: 0 });
  const lastUsageSeqRef = useRef<number>(-1);
  const [serverTaskId, setServerTaskId] = useState<string | null>(null);
  // 2026-08-30 小欧 根治陈旧闭包: reader挂起帧运行在旧render上, state版serverTaskId在空闲定时器/重连守卫闭包中读到旧null值误判;
  //   ref版始终同步最新值供内部判定, state版仅驱动UI重渲染(两者同步写入) - 小欧-2026-08-30
  const serverTaskIdRef = useRef<string | null>(null);
  const syncServerTaskId = useCallback((id: string | null) => {
    serverTaskIdRef.current = id;
    setServerTaskId(id);
  }, []);
  useEffect(() => {
    isReceivingRef.current = isReceiving;
  }, [isReceiving]);

  // 重连相关
  const reconnectConfigRef = useRef<ReconnectConfig>({
    enabled: true,
    maxAttempts: 3,
    baseDelay: 1000,
    maxDelay: 10000,
  });
  const reconnectAttemptsRef = useRef(0);
  // 【北京老陈 2026-07-12 小欧】记录已收到的最大后端事件 seq，断线重连时作为 after_seq 续传
  const lastSeqRef = useRef(0);
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
  const fetchTimeoutRef = useRef<number | null>(null); // 180s fetch超时检测
  const IDLE_TIMEOUT = 60000; // 60 秒无数据判定为断开

  // 【小强添加 2026-03-18】sessionStorage 备份相关
  // 恢复：组件初始化时检查是否有备份数据
  useEffect(() => {
    const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
    const savedSteps = sessionStorage.getItem(storageKey);
    if (savedSteps) {
      try {
        const parsedSteps = JSON.parse(savedSteps);
        if (Array.isArray(parsedSteps) && parsedSteps.length > 0) {
          console.log(
            `[SSE] 从 sessionStorage 恢复 ${parsedSteps.length} 个步骤`
          );
          executionStepsRef.current = parsedSteps;
          setExecutionSteps(parsedSteps);
        }
      } catch (e) {
        console.warn('[SSE] 解析 sessionStorage 备份失败:', e);
        sessionStorage.removeItem(storageKey);
      }
    }
  }, [config.sessionId]); // 仅在 sessionId 变化时检查

  // 保存到 sessionStorage 的辅助函数
  const saveStepsToStorage = useCallback(
    (steps: ExecutionStep[]) => {
      if (steps.length > 0 && config.sessionId) {
        const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
        try {
          sessionStorage.setItem(storageKey, JSON.stringify(steps));
        } catch (e) {
          console.warn('[SSE] 保存到 sessionStorage 失败:', e);
        }
      }
    },
    [config.sessionId]
  );

  // 清空 sessionStorage 的辅助函数
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const clearStepsFromStorage = useCallback(() => {
    const storageKey = `${SSE_STORAGE_KEY}_${config.sessionId}`;
    sessionStorage.removeItem(storageKey);
  }, [config.sessionId]);

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
      if (fetchTimeoutRef.current) {
        clearTimeout(fetchTimeoutRef.current);
        fetchTimeoutRef.current = null;
      }

      // 【修复 2026-05-11 小健】abort正在进行的fetch请求，防止旧流与新流并行
      if (abortControllerRef.current) {
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
        reconnectConfigRef.current.enabled = false;
        // 3秒后恢复重连功能（避免永久禁用）
        setTimeout(() => {
          reconnectConfigRef.current.enabled = true;
        }, 3000);
      }

      // 【方案2新增】调用断开回调
      if (onDisconnect) {
        onDisconnect();
      }
      // eslint-disable-next-line react-hooks/exhaustive-deps
    },
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
        lastSeqRef.current = 0; // 新请求重置 seq 偏移
      }
      const controller = new AbortController();
      abortControllerRef.current = controller; // 【修复 2026-05-11 小健】保存到ref，disconnect时可abort
      fetchTimeoutRef.current = window.setTimeout(
        () => controller.abort(),
        180000
      ); // 180s超时，qwen2.5:1.5b CPU首次推理约2分钟

      let response: Response;
      if (isReconnect) {
        // 重连：GET /chat/stream/{task_id}?after_seq=N 续传，不重新发起对话 — 北京老陈 2026-07-12 小欧
        const url = `${config.baseURL}/chat/stream/${serverTaskIdRef.current}?session_id=${encodeURIComponent(sessionId || '')}&after_seq=${lastSeqRef.current}`;
        console.log(`[SSE] [重连] GET ${url} after_seq=${lastSeqRef.current}`);
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

      if (fetchTimeoutRef.current) {
        clearTimeout(fetchTimeoutRef.current);
        fetchTimeoutRef.current = null;
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
          const timeSinceLastData = Date.now() - lastDataTimeRef.current;
          if (timeSinceLastData >= IDLE_TIMEOUT && isReceivingRef.current) {
            console.warn(
              `[SSE] 空闲超时：已经${timeSinceLastData / 1000}秒未收到数据，判定连接断开`
            );
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
                onPaused,
                onResumed,
                onRetry,
                onAuthorizationRequired,
                setCurrentResponse,
                responseBufferRef,
                setIsReceiving,
                setIsConnected,
                disconnect,
                setServerTaskId: syncServerTaskId,
                onSeq: (s: number) => {
                  if (s > lastSeqRef.current) lastSeqRef.current = s;
                },
                setMetaFrames,
                usageAccumRef,
                lastUsageSeqRef,
              },
              isProcessingRef
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
              onPaused,
              onResumed,
              onRetry,
              onAuthorizationRequired,
              setCurrentResponse,
              responseBufferRef,
              setIsReceiving,
              setIsConnected,
              disconnect,
              setServerTaskId: syncServerTaskId,
              onSeq: (s: number) => {
                if (s > lastSeqRef.current) lastSeqRef.current = s;
              },
              setMetaFrames,
              usageAccumRef,
              lastUsageSeqRef,
            },
            isProcessingRef
          );
        }
      }

      // 成功，重置重连状态
      setReconnectStatus('idle');
      reconnectAttemptsRef.current = 0;
      abortControllerRef.current = null; // 【修复 2026-05-11 小健】请求完成清理ref
    } catch (error: unknown) {
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
  }, [sendMessageInternal]);

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
      // 【修复小查问题】清理 pendingMessageRef 避免内存泄漏
      pendingMessageRef.current = null;
      // 【小新修复 2026-03-14】额外确保 reconnectTimeoutRef 被清理
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
      }
    };
  }, [disconnect]);

  return {
    isConnected,
    isReceiving,
    setIsReceiving, // 【方案3】暴露setter用于中断时立即更新状态
    executionSteps,
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
