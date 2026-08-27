// 编辑历史: 2026-07-18 小欧 - FinalStep终态规整: ExecutionStep接口加outcome/error_type/error_message; processSSEData同步解析
// 编辑历史: 2026-08-18 小欧 - 三堂会审(P7/P4): case 'startinfo'并入'start'渲染; error分支优先content回退error_message
// 编辑历史: 2026-08-23 小欧 - 三堂会审修复: 删除ExecutionStep重复声明error_type/error_message(TS2300)
// 编辑历史: 2026-08-26 小欧 - 8.4/8.4.14实施: ExecutionStep.type改action+新增多case; 移除安全/性能旧字段; final解析累计usage
// 编辑历史: 2026-08-27 小欧 - 三堂会审H2修复: classifyError改调纯classifyError(errorHandler)替代带副作用handleSSEError, 消除SSE错误路径误弹"正在重试"; 顶部import增classifyError别名
// 编辑历史: 2026-08-27 小欧 - 三堂会审配套修复: observation解析同步execution_result=obsData, 供专用渲染器(data/llm_data)消费, 修复删tool_result早退后工具结果渲染空回归
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: 删thought-start恒假守卫/死引用ttftRef等/死导出isPersistBlocked/死守卫!result.handled
// 编辑历史: 2026-08-27 小欧 - 撤回8.6误删isPersistBlocked: sse-parsing.test.ts依赖其判定持久化黑名单, 非死导出, 已恢复PERSIST_BLOCKLIST+isPersistBlocked
/**
 * SSE 工具模块 V2 - Server-Sent Events 流式处理
 *
 * 功能：建立 SSE 连接、接收流式数据、处理执行步骤
 * 改进：增加自动重连、错误分类、友好提示
 *
 * 错误处理说明：
 * - 所有SSE错误统一使用 errorHandler.handleSSEError() 处理
 * - 禁止直接调用 message.error/warning/success/info
 * - 连接重连、错误去重、提示样式由 errorHandler 统一管理
 *
 * @author 小新
 * @version 2.0.0
 * @since 2026-03-04
 */

import { useState, useCallback, useRef, useEffect } from 'react';
// import { message } from "antd";  // 已迁移到errorHandler统一处理
import {
  handleSSEError as errorHandlerHandleSSE,
  ErrorType,
  classifyError as errorHandlerClassify, // 2026-08-27 小欧 三堂会审H2: 引入纯分类函数替代带副作用的handleSSEError
} from './errorHandler';
import { taskControlApi } from '../services/api';

// 【小强修复 2026-03-18】sessionStorage key - 用于长时间隐藏页面时备份数据
// 场景：用户切换到其他应用→页面隐藏→SSE 连接不断开→后端数据持续发送
// 问题：浏览器降频导致回调延迟执行，标签页可能被丢弃
// 解决：同时保存到 ref + sessionStorage，即使标签页丢弃数据也不会丢失
const SSE_STORAGE_KEY = 'sse_execution_steps_backup';

// 编辑历史: 2026-08-27 小欧 - 撤回8.6误删: isPersistBlocked被sse-parsing.test.ts依赖(非死导出), 恢复PERSIST_BLOCKLIST+isPersistBlocked
/** 持久化黑名单：统计类通知不落库不导出（生命周期类仍随步骤流落库，8.4.14 口径）*/
export const PERSIST_BLOCKLIST = [
  'startinfo',
  'usage',
  'stats',
  'final_stats',
  'context_overview',
  'truncated',
] as const;
export const isPersistBlocked = (type: string): boolean =>
  (PERSIST_BLOCKLIST as readonly string[]).includes(type);

// ===== 任务元信息帧（小欧 2026-08-26 8.4.14）=====
export interface StartInfoFrame {
  task_id?: string;
  display_name?: string;
  provider?: string;
  model?: string;
  ai_message_id?: string;
}
export interface StatsFrame {
  step_count?: number;
  llm_call_count?: number;
  retry_count?: number;
  duration?: number;
}
export interface FinalStatsFrame {
  duration?: number;
  tool_stats?: Record<string, number>;
  artifacts?: Array<{ name: string; path: string; type: string }> | null;
  final_status?: 'completed' | 'failed' | 'cancelled';
  retry_count?: number;
}
export interface ContextOverviewFrame {
  summary: string;
  message_count?: number;
  estimated_tokens?: number;
  truncated: boolean;
  injected_ratio?: number;
}
export interface TaskMetaFrames {
  contextSummary: string; // start.content
  startInfo: StartInfoFrame | null;
  startTimestamp: number; // start 事件时间戳（供 useTaskInfo 过程条首行使用）
  usage: { prompt: number; completion: number; total: number }; // 逐帧累加
  stats: StatsFrame | null; // 保留上一帧
  finalStats: FinalStatsFrame | null;
  contextOverview: ContextOverviewFrame | null; // 保留上一帧
  truncated: { content: string; severity: 'info' | 'warn' | 'error' } | null;
}
export const emptyMetaFrames = (): TaskMetaFrames => ({
  contextSummary: '',
  startInfo: null,
  startTimestamp: 0,
  usage: { prompt: 0, completion: 0, total: 0 },
  stats: null,
  finalStats: null,
  contextOverview: null,
  truncated: null,
});

/**
 * SSE错误类型 - 用于 onError 回调函数参数
 * 文档：API-chat-stream.md
 * 【小沈修改2026-04-15】删除code和message字段，统一使用error_message
 */
export interface SSEError {
  // 必填字段（3个）
  type: string; // 固定值: error
  error_type: string; // 错误类型
  error_message: string; // 用户友好的错误信息 【修改2026-04-15】message → error_message
  // 必填字段（1个）
  timestamp: string; // 时间戳
  // 可选字段（8个）
  model?: string; // 模型名称
  provider?: string; // 提供商名称
  details?: string; // 详细错误信息
  stack?: string; // 堆栈信息
  retryable?: boolean; // 是否可重试
  retry_after?: number; // 重试等待秒数
  context?: {
    // 错误上下文 【新增2026-04-15】
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

/**
 * SSE 元数据
 */
export interface SSEMetadata {
  model?: string;
  provider?: string;
  display_name?: string;
}

/**
 * 执行步骤类型 - 与后端字段完全对应，便于调试和理解
 * 【小新重构2026-03-09】适配新API字段名
 *
 * 【重要】8种type说明：
 * - 内容步骤：start（开始）、chunk（AI流式回复的内容片段）、final（最终回答）
 *   【chunk是AI流式输出的内容片段，不是执行步骤，显示在AI回复区域，不在步骤列表】
 * - 执行步骤：thought（思考）、action（工具调用）、observation（工具结果）
 * - 异常步骤：error（错误）、status（生命周期：cancelled/paused/retrying/resumed）
 */
// 2026-08-27 小欧 三堂会审: ExecutionStep 已迁移至 types/execution.ts, 此处仅 re-export 兼容历史引用(断 sse↔api 类型环)
import type { ExecutionStep } from '../types/execution';
export type { ExecutionStep } from '../types/execution';

/**
 * SSE连接配置
 */
export interface SSEConfig {
  baseURL: string;
  sessionId: string;
  token?: string;
  taskId?: string;
}

/**
 * SSE重连配置
 */
export interface ReconnectConfig {
  enabled: boolean;
  maxAttempts: number;
  baseDelay: number;
  maxDelay: number;
}

/**
 * SSE Hook返回值
 */
export interface UseSSEReturn {
  isConnected: boolean;
  isReceiving: boolean;
  setIsReceiving?: (value: boolean) => void; // 【方案3】暴露setter用于中断时立即更新状态
  executionSteps: ExecutionStep[];
  currentResponse: string;
  sendMessage: (
    content: string,
    sessionId?: string,
    contextLinkMode?: 'linked' | 'independent'
  ) => void;
  disconnect: (
    manualDisconnect?: boolean,
    clearStorage?: boolean,
    onDisconnect?: () => void
  ) => void;
  clearSteps: () => void;
  serverTaskId?: string | null;
  setServerTaskId?: (taskId: string | null) => void;
  /** 重连状态 */
  reconnectStatus: 'idle' | 'connecting' | 'reconnecting' | 'failed';
  /** 手动重连 */
  reconnect: () => void;
  /** 任务元信息帧快照（usage/stats/final_stats/context_overview/truncated/startInfo/上下文摘要） */
  metaFrames: TaskMetaFrames;
}

/**
 * 错误类型分类
 * 【小强修复 2026-04-11】使用统一错误处理中心
 */
type SSEErrorType =
  | 'idle_timeout'
  | 'request_timeout'
  | 'network'
  | 'server'
  | 'unknown'
  | 'empty_response'
  | 'connection_refused'
  | 'http_500'
  | 'fc_format_error'; // 小欧 2026-06-25: FC格式错误（可恢复）

/**
 * 分类错误类型 - 适配errorHandler的分类结果
 * 【小强修复 2026-04-09】细分超时类型
 * 【小强修复 2026-04-11】增加 connection_refused 和 http_500，映射到统一ErrorType
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
  onReconnect: () => void;
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
    pendingMessage,
    onReconnect,
    onSetReconnectStatus,
    onSetIsConnected,
    onSetIsReceiving,
    onError,
    reconnectTimeoutRef,
    serverTaskId,
  } = params;

  // 使用统一错误处理中心（handleSSEError 恒返回 handled:true，无需再判 else 早退）
  errorHandlerHandleSSE(error as Error, {
    reconnectAttempts,
    maxRetries: reconnectConfig.maxAttempts,
    onReconnect: () => {
      onSetReconnectStatus('reconnecting');
      reconnectTimeoutRef.current = window.setTimeout(() => {
        onReconnect();
      }, reconnectConfig.baseDelay);
    },
  });

  // 如果不可重试或已超过最大次数
  const canRetry =
    reconnectAttempts < reconnectConfig.maxAttempts && pendingMessage;

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
   */
  const disconnect = useCallback(
    (
      manualDisconnect: boolean = false,
      clearStorage: boolean = true,
      onDisconnect?: () => void
    ) => {
      // 清空 sessionStorage 备份（除非重连时明确指定不清空）
      if (clearStorage) {
        clearStepsFromStorage();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = null;
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
      setIsReceiving(false);
      setReconnectStatus('idle');
      reconnectAttemptsRef.current = 0;

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
    []
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
    disconnect(false, false); // 重连时：非手动断开 + 不清空 sessionStorage
    // 小沈修复 2026-04-21：新请求时清空 steps，重连时保留 steps
    if (reconnectAttemptsRef.current > 0) {
      softClearSteps(); // 重连：保留 steps，只清理运行时状态
    } else {
      clearSteps(); // 新请求：完全清空 steps
    }

    setIsReceiving(true);
    setIsConnected(true);
    setReconnectStatus('connecting');

    try {
      // 【北京老陈 2026-07-12 小欧】断线重连：复用 task_id 走 GET 读同一流态缓冲，避免双 agent
      const isReconnect = reconnectAttemptsRef.current > 0 && !!serverTaskId;
      if (!isReconnect) {
        lastSeqRef.current = 0; // 新请求重置 seq 偏移
      }
      const controller = new AbortController();
      abortControllerRef.current = controller; // 【修复 2026-05-11 小健】保存到ref，disconnect时可abort
      const timeoutId = setTimeout(() => controller.abort(), 180000); // 180s超时，qwen2.5:1.5b CPU首次推理约2分钟

      let response: Response;
      if (isReconnect) {
        // 重连：GET /chat/stream/{task_id}?after_seq=N 续传，不重新发起对话 — 北京老陈 2026-07-12 小欧
        const url = `${config.baseURL}/chat/stream/${serverTaskId}?session_id=${encodeURIComponent(sessionId || '')}&after_seq=${lastSeqRef.current}`;
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

      clearTimeout(timeoutId);

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
        // 【小强修复 2026-04-09】使用 IDLE_TIMEOUT，更准确的命名
        if (idleTimeoutRef.current) {
          clearTimeout(idleTimeoutRef.current);
        }
        idleTimeoutRef.current = window.setTimeout(() => {
          const timeSinceLastData = Date.now() - lastDataTimeRef.current;
          if (timeSinceLastData > IDLE_TIMEOUT && isReceiving) {
            console.warn(
              `[SSE] 空闲超时：已经${timeSinceLastData / 1000}秒未收到数据，判定连接断开`
            );
            throw new Error('SSE 空闲超时：长时间未收到数据');
          }
        }, IDLE_TIMEOUT);

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
                setServerTaskId,
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

        // 【小强修复 2026-03-18】更新最后数据时间
        lastDataTimeRef.current = Date.now();

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
              setServerTaskId,
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
          sendMessageInternal(content, sessionId);
        },
        onSetReconnectStatus: setReconnectStatus,
        onSetIsConnected: setIsConnected,
        onSetIsReceiving: setIsReceiving,
        onError,
        reconnectTimeoutRef,
        serverTaskId, // 【北京老陈 2026-07-12 小欧】重连耗尽用于发起取消
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

/**
 * 处理单行SSE数据
 */
const processSSEData = (
  line: string,
  handlers: {
    setExecutionSteps: React.Dispatch<React.SetStateAction<ExecutionStep[]>>;
    getCurrentExecutionSteps: () => ExecutionStep[];
    executionStepsRef: React.MutableRefObject<ExecutionStep[]>; // 【小新添加 2026-03-15】用于同步更新 ref
    saveStepsToStorage?: (steps: ExecutionStep[]) => void; // 【小强添加 2026-03-18】保存到 sessionStorage
    onStep?: (step: ExecutionStep) => void;
    onChunk?: (chunk: string, is_reasoning?: boolean) => void;
    onComplete?: (
      fullResponse: string,
      metadata?: string | SSEMetadata,
      executionSteps?: ExecutionStep[]
    ) => void;
    onError?: (error: string | SSEError) => void;
    onPaused?: () => void;
    onResumed?: () => void;
    onRetry?: (message: string, waitTime?: number) => void;
    onAuthorizationRequired?: (data: {
      confirm_id: string;
      tool_name: string;
      params: Record<string, unknown>;
      safety_level: string;
    }) => void;
    setCurrentResponse: React.Dispatch<React.SetStateAction<string>>;
    responseBufferRef: React.MutableRefObject<string>;
    setIsReceiving: React.Dispatch<React.SetStateAction<boolean>>;
    setIsConnected: React.Dispatch<React.SetStateAction<boolean>>;
    disconnect: (
      manualDisconnect?: boolean,
      clearStorage?: boolean,
      onDisconnect?: () => void
    ) => void;
    setServerTaskId?: (taskId: string) => void;
    // 【北京老陈 2026-07-12 小欧】回传后端事件 seq，用于断线重连 after_seq 续传
    onSeq?: (seq: number) => void;
    // 【小欧 2026-08-26 8.4.14】元信息帧状态注入（useSSE 闭包 state/ref 透传进模块级 processSSEData）
    setMetaFrames?: React.Dispatch<React.SetStateAction<TaskMetaFrames>>;
    usageAccumRef?: React.MutableRefObject<{
      prompt: number;
      completion: number;
      total: number;
    }>;
    lastUsageSeqRef?: React.MutableRefObject<number>;
  },
  _isProcessingRef: React.MutableRefObject<boolean>
) => {
  const {
    setExecutionSteps,
    saveStepsToStorage,
    onStep,
    onChunk,
    onComplete,
    onError,
    onPaused,
    onResumed,
    onRetry,
    setCurrentResponse,
    responseBufferRef,
    setIsReceiving,
    setIsConnected,
    disconnect: _disconnect,
    setServerTaskId,
    onSeq,
  } = handlers;

  // 2026-08-27 小欧 修复: SSE数据行可能带前导空格, 先trim再判断前缀
  const trimmedLine = line.trim();
  if (!trimmedLine || !trimmedLine.startsWith('data: ')) {
    return;
  }

  try {
    let jsonStr = trimmedLine.slice(6);
    jsonStr = jsonStr.trim();
    const rawData = JSON.parse(jsonStr);

    // 【北京老陈 2026-07-12 小欧】回传后端事件 seq，断线重连时用于 after_seq 续传避免重复
    if (typeof rawData.seq === 'number' && onSeq) {
      onSeq(rawData.seq);
    }

    // 【小强修复 2026-03-18】统一处理timestamp转换
    // 后端有些字段返回字符串格式timestamp，前端需要转换为毫秒数
    let timestampValue = Date.now();
    if (rawData.timestamp) {
      if (typeof rawData.timestamp === 'number') {
        timestampValue = rawData.timestamp;
      } else if (typeof rawData.timestamp === 'string') {
        // 尝试解析字符串时间戳
        const parsed = Date.parse(rawData.timestamp);
        timestampValue = isNaN(parsed) ? Date.now() : parsed;
      }
    }

    const step: ExecutionStep = {
      type: rawData.type as ExecutionStep['type'],

      // 根据不同type使用不同字段（后端字段拆分方案）
      thinking_prompt: rawData.thinking_prompt,
      action_description: rawData.action_description,
      content: rawData.content,
      error_message: rawData.error_message,
      message: rawData.message,

      // 保留字段
      step: rawData.step || 1, // 与后端一致：step
      thought: rawData.thought, // Agent.thought的值
      // 2026-07-18 小欧 FinalStep 终态规整：终态统一 type=final，由 outcome 声明；同步解析出后端字段
      outcome: rawData.outcome,
      error_type: rawData.error_type,
      action: rawData.action, // 执行动作名称，与后端一致
      observation: rawData.observation, // 保留原始对象，用于调试
      result: rawData.result, // simplify_observation处理后的文本
      action_input: rawData.action_input, // 工具调用参数

      // 【小沈修复】思考过程与正式内容区分字段
      // 【小查修复】统一使用 snake_case: is_reasoning
      is_reasoning:
        rawData.is_reasoning === true ||
        rawData.is_reasoning === 'true' ||
        rawData.is_reasoning === 1,
      // reasoning: rawData.reasoning || "",  // 【小强删除 2026-04-08】reasoning与content重复，后端已删除

      timestamp: timestampValue,
    };

    if (rawData.task_id && setServerTaskId) {
      setServerTaskId(rawData.task_id);
    }

    switch (rawData.type) {
      // 【小欧 2026-08-26 8.4.3】start/startinfo 拆双（4.9.2.7）：
      //  - start.content=context_summary -> 元信息帧 contextSummary（任务信息条上下文概况，三分归位③），
      //    不进右侧查看区流水线（4.4.4）；user_message 对话界面已可见不重复渲染（4.9.1）；
      //    model/provider 由顶栏徽标承载（4.8.3-A）。
      //  - startinfo -> 元信息帧 startInfo（驱动状态徽标），同样不入步骤列表。
      case 'start':
      case 'startinfo': {
        if (rawData.type === 'start') {
          const summary =
            typeof rawData.content === 'string' ? rawData.content : '';
          handlers.setMetaFrames?.((prev) => ({
            ...prev,
            contextSummary: summary,
            startTimestamp: Date.now(),
          }));
          break;
        }
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          startInfo: {
            task_id: rawData.task_id,
            display_name: rawData.display_name,
            provider: rawData.provider,
            model: rawData.model,
            ai_message_id: rawData.ai_message_id,
          },
        }));
        break;
      }

      // thought-start："开始思考"实时信号 —— 业务流标记，入列且同步 ref（ThinkingStream 光标）
      case 'thought-start': {
        const ts: ExecutionStep = {
          type: 'thought-start',
          content: '',
          step: rawData.step || 1,
          timestamp: timestampValue,
        };
        setExecutionSteps((prev) => {
          const next = [...prev, ts];
          handlers.executionStepsRef.current = next;
          // 2026-08-27 小欧 三堂会审: thought-start为瞬时光标信号, 仅内存帧不落sessionStorage, 故无持久化逻辑
          return next;
        });
        onStep?.(ts);
        break;
      }

      // usage：单任务 token 帧 —— 断线续传(E2)按 seq 去重防重复累加【R1-B13】
      case 'usage': {
        if (typeof rawData.seq === 'number') {
          if (rawData.seq <= (handlers.lastUsageSeqRef?.current ?? -1)) break;
          if (handlers.lastUsageSeqRef)
            handlers.lastUsageSeqRef.current = rawData.seq;
        }
        if (handlers.usageAccumRef) {
          handlers.usageAccumRef.current = {
            prompt:
              handlers.usageAccumRef.current.prompt +
              (rawData.prompt_tokens ?? 0),
            completion:
              handlers.usageAccumRef.current.completion +
              (rawData.completion_tokens ?? 0),
            total:
              handlers.usageAccumRef.current.total +
              (rawData.total_tokens ?? 0),
          };
        }
        const acc = handlers.usageAccumRef?.current ?? {
          prompt: 0,
          completion: 0,
          total: 0,
        };
        handlers.setMetaFrames?.((prev) => ({ ...prev, usage: { ...acc } }));
        break;
      }

      // stats：耗时/轮次流式帧
      case 'stats': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          stats: {
            step_count: rawData.step_count,
            llm_call_count: rawData.llm_call_count,
            retry_count: rawData.retry_count,
            duration: rawData.duration,
          },
        }));
        break;
      }

      // final_stats：终态统计独立步（duration/tool_stats/artifacts）
      case 'final_stats': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          finalStats: {
            duration: rawData.duration,
            tool_stats: rawData.tool_stats,
            artifacts: rawData.artifacts,
            final_status: rawData.final_status,
            retry_count: rawData.retry_count,
          },
        }));
        break;
      }

      // context_overview：上下文概况帧
      case 'context_overview': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          contextOverview: {
            summary: rawData.summary ?? '',
            message_count: rawData.message_count,
            estimated_tokens: rawData.estimated_tokens,
            truncated: rawData.truncated === true,
            injected_ratio: rawData.injected_ratio,
          },
        }));
        break;
      }

      // truncated：输出截断提示帧（severity=warn，字段=content）
      case 'truncated': {
        handlers.setMetaFrames?.((prev) => ({
          ...prev,
          truncated: {
            content: rawData.content ?? '',
            severity: rawData.severity ?? 'warn',
          },
        }));
        break;
      }

      case 'thought': {
        const stepNum = rawData.step || 1;
        console.log(
          `%c[STEP] [type=thought] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【小沈修改2026-04-16】使用后端字段存储
        step.step = rawData.step || 1;
        step.timestamp = rawData.timestamp || Date.now();
        // 后端有两个字段：content(完整思考内容)和thought(parsed获取的thought)
        step.content = rawData.content || ''; // 完整思考内容
        step.thought = rawData.thought || ''; // parsed的thought
        step.reasoning = rawData.reasoning || '';
        step.tool_name = rawData.tool_name || '';
        step.tool_params = rawData.tool_params || rawData.params || {}; // 兼容旧字段
        // console.log("🔍 [sse thought] step对象=", JSON.stringify(step));
        // 添加到步骤数组，显示思考过程
        // 【小新修复 2026-03-15 V2】在回调中同步更新 executionStepsRef.current
        // 根因：setExecutionSteps 更新 React state 是异步的，useEffect 依赖 executionSteps 更新
        //      但 useEffect 在 onComplete 调用时还未执行，导致 getCurrentExecutionSteps() 获取到旧值
        // 修复：在 setExecutionSteps 回调中同步更新 ref，确保其他代码立即获取到最新值
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        break;
      }

      case 'chunk': {
        // 精简日志：chunk不打印，避免日志过多

        // 传递 is_reasoning 区分思考过程和最终答案
        const is_reasoning =
          rawData.is_reasoning === true ||
          rawData.is_reasoning === 'true' ||
          rawData.is_reasoning === 1 ||
          rawData.is_reasoning === '1';
        const chunkContent = rawData.content || '';
        responseBufferRef.current += chunkContent;
        setCurrentResponse(responseBufferRef.current);
        onChunk?.(chunkContent, is_reasoning);

        // 【小新修复 2026-03-15 V3】chunk只保存当前小块内容，不保存累积
        // 核心原则：保存不能多也不能少，每个chunk只保存当前增量
        //
        // 实时显示逻辑（NewChatContainer.tsx）：
        //   - content累加显示：lastMessage.content + chunk（这是正确的，需要累加才能看到完整内容）
        //
        // 保存数据逻辑（此处）：
        //   - chunk保存当前小块：step.content = chunkContent（不是累积，只存当前块）
        //   - final保存完整内容：在final事件中保存message.content完整内容
        //
        // 历史消息显示逻辑（MessageItem.tsx）：
        //   - 遍历所有chunk逐个显示（每个chunk只显示自己的内容）
        //   - 如果没有is_reasoning=false的chunk，则显示message.content补充
        //
        // 错误做法会导致的问题：
        //   - 如果chunk保存累积内容 → 导出JSON每个chunk都重复 → 数据错误
        //   - 历史教训：不能为了解决刷新问题而破坏保存数据的正确性！
        step.content = chunkContent;

        // 【小沈带小强修改 2026-03-17】
        // 问题描述：前端导出 JSON 时只有 3 个步骤（start, thought, chunk），但数据库有 55 个步骤
        // 【小强修复 2026-04-10】使用回调函数模式，与 start/thought/action/observation 保持一致
        // 问题：之前使用直接同步更新，导致 ref 和 state 不同步
        // 解决：在 setExecutionSteps 回调函数内部更新 ref，确保同步
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        break;
      }

      case 'final': {
        const stepNum = rawData.step || 1;
        console.log(
          `%c[STEP] [type=final] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【小沈修改2026-04-16】添加step和timestamp字段
        step.step = rawData.step || 1;
        step.timestamp = rawData.timestamp || Date.now();

        // 【小强修复 2026-04-15】后端final类型没有content字段，直接使用response
        // 解析后端所有字段
        step.response = rawData.response || '';
        step.is_finished = rawData.is_finished;
        step.thought = rawData.thought || '';
        step.is_streaming = rawData.is_streaming;
        step.is_reasoning = rawData.is_reasoning;
        step.content = step.response; // content只用于前端显示，使用response的值

        if (step.content) {
          if (!responseBufferRef.current) {
            responseBufferRef.current = step.content;
            setCurrentResponse(responseBufferRef.current);
            onChunk?.(step.content);
          }
        }

        // 设置 display_name、model、provider 字段
        step.display_name = rawData.display_name;
        step.model = rawData.model;
        step.provider = rawData.provider;

        // 【小欧 2026-08-26 8.4/8.8】FinalStep._extra_fields：token 终值 + 四维累计
        step.prompt_tokens = rawData.accumulated_usage?.prompt_tokens;
        step.completion_tokens = rawData.accumulated_usage?.completion_tokens;
        step.total_tokens = rawData.accumulated_usage?.total_tokens;
        step.llm_call_count_token = rawData.llm_call_count_token;
        step.task_accumulated_tokens = rawData.task_accumulated_tokens;
        step.session_accumulated_tokens = rawData.session_accumulated_tokens;
        step.chain_accumulated_tokens = rawData.chain_accumulated_tokens;

        const displayName = rawData.display_name;

        // 【关键修复 2026-04-13】在回调之前先更新ref，确保onComplete获取完整数据
        // 问题：setExecutionSteps回调是异步的，导致onComplete拿到旧值
        // 解决：先直接更新ref，再调用onComplete
        const updatedSteps = [...handlers.executionStepsRef.current, step];
        handlers.executionStepsRef.current = updatedSteps;

        // 【小查修复】保存final到executionSteps，以便导出功能能获取到
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          // 【小强修改 2026-04-10】使用 setTimeout 延迟保存，不阻塞 UI
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);

        // 【关键修复 2026-04-13】在onComplete调用前手动构建完整的steps数组
        // 问题：setExecutionSteps回调是异步的，handlers.executionStepsRef.current已更新为最新值
        // 解决：直接使用已更新的ref
        const finalStepsWithCurrent = handlers.executionStepsRef.current;

        onComplete?.(
          responseBufferRef.current,
          {
            model: rawData.model,
            provider: rawData.provider,
            display_name: displayName,
          } as SSEMetadata,
          finalStepsWithCurrent
        );

        console.log(
          `[SSE] [连接断开] 时间=${new Date().toLocaleTimeString()} 收到steps=${handlers.getCurrentExecutionSteps().length}`
        );

        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      case 'error': {
        const stepNum = rawData.step || 1;
        console.log(
          `%c[STEP] [type=error] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【小强修复 2026-04-15】后端error类型只有以下字段，只解析后端存在的字段
        // 【小欧 2026-08-18 三堂会审】P4 起 error 文本统一由 MetaStep.content 承载(新)，
        //   兼容读 content，再回退旧 ErrorStep 的 error_message，杜绝实时显示退化为'未知错误'
        const errorMsg = rawData.content || rawData.error_message || '未知错误';
        step.content = errorMsg;
        step.error_message = errorMsg;
        step.error_type = rawData.error_type || '';

        // 解析后端存在的字段
        if (rawData.step) {
          step.step = rawData.step;
        }
        if (rawData.model) {
          step.model = rawData.model;
        }
        if (rawData.provider) {
          step.provider = rawData.provider;
        }
        if (rawData.details !== undefined) {
          step.details = rawData.details;
        }
        if (rawData.stack !== undefined) {
          step.stack = rawData.stack;
        }
        if (rawData.context) {
          step.context = {
            step: rawData.context.step,
            model: rawData.context.model,
            provider: rawData.context.provider,
            thought_content: rawData.context.thought_content,
          };
        }
        if (rawData.retry_after !== undefined) {
          step.retry_after = rawData.retry_after;
        }
        if (rawData.timestamp) {
          step.timestamp = rawData.timestamp;
        }
        // 【小欧 2026-08-26 8.4】error 收敛为事件通知：不进执行步骤列表、不落库不回放
        // （4.9.2.6）；失败态展示 = 任务信息条状态徽标(final.outcome=failed) + RightViewer
        // 经 onError→liveErrorText 直渲错误行（8.10，非 StatusLine）+ 静态统计块错误项。
        // 文本读 content（P4 已收敛），回退 error_message。
        // 【小沈修改2026-04-15】传递完整的错误对象，统一使用error_message，删除code字段
        onError?.({
          type: 'error',
          error_type: rawData.error_type || 'unknown_error',
          error_message: errorMsg,
          model: rawData.model,
          provider: rawData.provider,
          details: rawData.details,
          stack: rawData.stack,
          retryable: rawData.retryable,
          retry_after: rawData.retry_after,
          context: rawData.context,
          timestamp: rawData.timestamp || timestampValue,
        });
        // 【小强修复 2026-04-09】关键：不再调用onComplete（和v0.8.75一致），error步骤由onError处理
        // v0.8.75版本没有调用onComplete，UI显示正常
        setIsReceiving(false);
        setIsConnected(false);
        break;
      }

      // 【小欧 2026-08-26 8.4】action 新结构：exec_type(single/multi) + tools 数组
      // 单工具也是一个元素不做特判（4.9.2.9）；禁止保留 旧动作类型名 兼容分支
      case 'action': {
        const receiveTime = Date.now(); // 【收到数据】时间
        const actionStepNum = step.step; // step 序号
        const stepLabel = ` [type=action] [step=${actionStepNum}]`;

        step.exec_type = rawData.exec_type === 'multi' ? 'multi' : 'single';
        const tools: Array<{
          tool: string;
          target?: string;
          params?: Record<string, unknown>;
        }> = Array.isArray(rawData.tools)
          ? rawData.tools.map(
              (t: {
                tool: string;
                target?: string;
                params?: Record<string, unknown>;
              }) => ({
                tool: t.tool,
                target: t.target,
                params: t.params,
              })
            )
          : [];
        step.tools = tools;
        step.content = tools
          .map((t) => (t.target ? `${t.tool}(${t.target})` : t.tool))
          .join(' + ');

        // 【红色】收到数据
        console.log(
          `%c[ACTION]${stepLabel} [收到数据] 时间=${new Date(receiveTime).toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        // 【蓝色】ExecutionSteps保存开始时间
        const execStepsStartTime = Date.now();
        console.log(
          `%c[ACTION]${stepLabel} [ExecutionSteps保存开始] 时间=${new Date(execStepsStartTime).toLocaleTimeString()}`,
          'color: blue;'
        );

        setExecutionSteps((prev) => {
          // 【蓝色】ExecutionSteps保存完成
          const execStepsDoneTime = Date.now();
          const execStepsDuration = execStepsDoneTime - execStepsStartTime;
          console.log(
            `%c[ACTION]${stepLabel} [ExecutionSteps保存完成] 完成=${new Date(execStepsDoneTime).toLocaleTimeString()} 耗时=${execStepsDuration}ms`,
            'color: blue;'
          );

          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;

          // 【紫色】sessionStorage保存开始时间
          const storageStartTime = Date.now();
          console.log(
            `%c[ACTION]${stepLabel} [sessionStorage保存开始] 时间=${new Date(storageStartTime).toLocaleTimeString()}`,
            'color: #006400; font-weight: bold;'
          );

          setTimeout(() => {
            try {
              // 【紫色】sessionStorage保存完成
              const storageDoneTime = Date.now();
              const storageDuration = storageDoneTime - storageStartTime;
              console.log(
                `%c[ACTION]${stepLabel} [sessionStorage保存完成] 完成=${new Date(storageDoneTime).toLocaleTimeString()} 耗时=${storageDuration}ms`,
                'color: #006400; font-weight: bold;'
              );
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });

        // 【青色】渲染开始时间点
        const renderStartTime = Date.now();
        console.log(
          `%c[ACTION]${stepLabel} [渲染开始] 时间=${new Date(renderStartTime).toLocaleTimeString()}`,
          'color: cyan;'
        );

        onStep?.(step);

        // 【青色】渲染完成时间点
        const renderDoneTime = Date.now();
        const renderDuration = renderDoneTime - renderStartTime;
        console.log(
          `%c[ACTION]${stepLabel} [渲染完成] 完成=${new Date(renderDoneTime).toLocaleTimeString()} 耗时=${renderDuration}ms`,
          'color: cyan; font-weight: bold;'
        );

        break;
      }

      // 【小沈修复 2026-04-11】新增：observation类型处理
      // 【小沈改造 2026-05-22】支持observation为JSON对象（第13章设计方案）
      case 'observation': {
        const stepNum = rawData.step || 1;
        console.log(
          `%c[STEP] [type=observation] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );

        step.step = rawData.step || 1;
        step.timestamp = rawData.timestamp || Date.now();
        step.code = rawData.code; // 状态码（SUCCESS/ERROR/WARNING）

        // 【兼容层 2026-05-22 小资】支持两种格式，添加完整性验证
        // 先检查null（typeof null === 'object'是历史bug）
        // 2026-08-27 小欧 三堂会审: 适配后端08-18新契约 — observation步骤仅携带rawData.tool_result数组(顶层), 无observation字段
        if (Array.isArray(rawData.tool_result) && rawData.tool_result.length) {
          // 新契约(§10.3.3(3)): tool_result数组在rawData顶层, 每元素自包含{tool_name,llm_data,data_text,other_data}
          const tr = rawData.tool_result as Array<Record<string, unknown>>;
          step.tool_result = tr; // 供ToolResultRenderer早退/DefaultRenderer读取
          const el = (tr[0] || {}) as Record<string, unknown>;
          const llmData = (el.llm_data as Record<string, unknown>) || {};
          const status = (llmData.status as Record<string, unknown>) || {};
          // data_text承载原data对象(JSON字符串), 解析为data供专用渲染器读取data.* — 2026-08-27 小欧 三堂会审
          let dataObj: Record<string, unknown> = {};
          const dataText = el.data_text;
          if (typeof dataText === 'string' && dataText.trim()) {
            try {
              dataObj = JSON.parse(dataText) as Record<string, unknown>;
            } catch {
              dataObj = { raw: dataText };
            }
          } else if (dataText && typeof dataText === 'object') {
            dataObj = dataText as Record<string, unknown>;
          }
          step.execution_result = {
            data: dataObj,
            llm_data: llmData,
            other_data: (el.other_data as Record<string, unknown>) || {},
          }; // 2026-08-27 小欧 三堂会审: 构造execution_result供专用渲染器读取data/llm_data, 修复删早退后渲染空回归
          step.tool_name = (el.tool_name as string) || '';
          step.tool_params = (el.tool_params as Record<string, unknown>) || {};
          step.return_direct = Boolean(
            (el.other_data as Record<string, unknown>)?.return_direct
          );
          step.summary = (llmData.summary as string) || '';
          step.execution_status =
            (status.exec_code as 'success' | 'error' | 'warning') || undefined;
          step.error_message = (status.message as string) || undefined;
          step.content = step.summary;
          step.parallel_results =
            (rawData.parallel_results as typeof step.parallel_results) ||
            undefined;
        } else if (
          rawData.observation !== null &&
          rawData.observation !== undefined &&
          typeof rawData.observation === 'object'
        ) {
          // 兼容旧格式（observation 对象）
          const obsData = rawData.observation as Partial<{
            llm_data: Record<string, unknown>;
            tool_result: unknown;
            other_data: Record<string, unknown>;
            summary: string;
            tool_name: string;
            tool_params: Record<string, unknown>;
            return_direct: boolean;
            execution_status?: string;
            error_message?: string;
          }>;
          const llmDataRaw = obsData.llm_data;
          const llmData = (
            Array.isArray(llmDataRaw) ? llmDataRaw[0] : llmDataRaw
          ) as Record<string, unknown> | undefined;
          const otherData = obsData.other_data as
            | Record<string, unknown>
            | undefined;
          step.observation = obsData;
          step.tool_result = obsData.tool_result;
          step.execution_result = obsData;
          step.tool_name =
            ((llmData?.action as Record<string, unknown>)?.tool as string) ??
            obsData.tool_name ??
            '';
          step.tool_params =
            ((llmData?.action as Record<string, unknown>)?.params as Record<
              string,
              unknown
            >) ??
            obsData.tool_params ??
            {};
          step.return_direct =
            (otherData?.return_direct as boolean) ??
            obsData.return_direct ??
            false;
          step.summary = (llmData?.summary as string) ?? obsData.summary ?? '';
          step.execution_status =
            ((llmData?.status as Record<string, unknown>)?.exec_code as
              | 'success'
              | 'error'
              | 'warning') ??
            (obsData.execution_status as 'success' | 'error' | 'warning') ??
            undefined;
          step.error_message =
            ((llmData?.status as Record<string, unknown>)?.message as string) ??
            obsData.error_message;
          step.content = step.summary;
          step.parallel_results = (
            obsData as { parallel_results?: typeof step.parallel_results }
          ).parallel_results;
        } else {
          // 旧格式：observation是字符串或null/undefined
          const obsStr =
            rawData.observation != null ? String(rawData.observation) : '';
          step.observation = obsStr;
          step.tool_name = rawData.tool_name ?? '';
          step.tool_params = rawData.tool_params ?? {};
          step.return_direct = rawData.return_direct ?? false;
          step.content = obsStr;
        }

        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);
        break;
      }

      // 【北京老陈 2026-07-13 小欧】incident 类型已废弃: 后端统一用 type=cancelled/paused/retrying/resumed 直接表示

      // 【北京老陈 2026-07-12 小欧】直接处理 cancelled/paused/resumed/retrying 类型
      case 'cancelled':
      case 'paused':
      case 'resumed':
      case 'retrying': {
        const stepNum = rawData.step || 1;
        console.log(
          `%c[STEP] [type=${rawData.type}] [step=${stepNum}] [收到数据] 时间=${new Date().toLocaleTimeString()}`,
          'color: red; font-weight: bold;'
        );
        // 小欧 2026-07-13: 后端 MetaStep 统一以 content 字段承载文本(与 ThoughtStep/FinalStep 契约一致),
        // 前端须读 content 而非旧 message 字段, 否则用户取消/重试提示显示为空(真实跨层缺陷, 已修)。
        const statusMessage = rawData.content || '';

        // 直接使用rawData.type作为step.type
        step.type = rawData.type as ExecutionStep['type'];
        step.content = statusMessage;

        // 统一调用onStep（所有类型都需要添加到executionSteps）
        setExecutionSteps((prev) => {
          const newSteps = [...prev, step];
          handlers.executionStepsRef.current = newSteps;
          setTimeout(() => {
            try {
              saveStepsToStorage?.(newSteps);
            } catch (e) {
              console.warn('[SSE] sessionStorage 保存失败，可能容量不足:', e);
            }
          }, 0);
          return newSteps;
        });
        onStep?.(step);

        // 根据type调用对应的回调
        switch (rawData.type) {
          case 'cancelled':
            onComplete?.(
              responseBufferRef.current,
              undefined,
              handlers.executionStepsRef.current
            );
            setIsReceiving(false);
            setIsConnected(false);
            break;
          case 'paused':
            onPaused?.();
            if (rawData.confirm_id) {
              // 【北京老陈 2026-07-13 小欧】HITL 授权请求：paused + confirm_id 触发授权弹窗
              handlers.onAuthorizationRequired?.({
                confirm_id: rawData.confirm_id,
                tool_name: rawData.tool_name,
                params: rawData.params,
                safety_level: rawData.safety_level,
              });
            }
            break;
          case 'resumed':
            onResumed?.();
            break;
          case 'retrying':
            // 小欧 2026-07-13: 同上, 读取后端 content 字段作为重试提示文本。
            onRetry?.(rawData.content || '正在重试...', rawData.wait_time);
            break;
          default:
            console.warn('[SSE] 未知的type:', rawData.type);
            onRetry?.(
              rawData.content || `事件: ${rawData.type}`,
              rawData.wait_time
            );
            break;
        }
        // 添加timestamp字段
        if (rawData.timestamp) {
          step.timestamp = rawData.timestamp as number;
        }
        // 添加wait_time字段（仅retrying使用）
        if (rawData.wait_time !== undefined) {
          step.wait_time = rawData.wait_time;
        }
        break;
      }
    }
  } catch (error) {
    console.error('[SSE] 解析数据失败:', error);
  }
};

export default useSSE;
