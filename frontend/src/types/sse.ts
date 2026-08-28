// 编辑历史: 2026-08-28 小欧 - 由 utils/sse.ts 抽离SSE专属类型归一至横切层; ExecutionStep已居types/execution.ts故不重复导出 - 小欧-2026-08-28
import type { ExecutionStep } from './execution';

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
export type SSEErrorType =
  | 'idle_timeout'
  | 'request_timeout'
  | 'network'
  | 'server'
  | 'unknown'
  | 'empty_response'
  | 'connection_refused'
  | 'http_500'
  | 'fc_format_error'; // 小欧 2026-06-25: FC格式错误（可恢复）
