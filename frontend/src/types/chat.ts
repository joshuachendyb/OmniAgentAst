/**
 * 流式API响应类型定义
 * 
 * 用于定义ReAct流式API返回的8种消息类型
 * 与后端第9章设计文档完全对应
 * 
 * @author 小新
 * @version 1.0.0
 * @since 2026-03-09
 */

import type { ExecutionStep } from "../utils/sse";

// ============================================================
// 安全检查相关类型
// ============================================================

/**
 * 安全检查结果
 */
export interface SecurityCheck {
  is_safe: boolean;
  risk_level: 'low' | 'medium' | 'high' | 'critical' | null;
  risk: string | null;
  blocked: boolean;
}

// ============================================================
// 消息类型定义（8种）
// ============================================================

/**
 * start类型 - 任务开始
 * 发送时机：后端接收到请求，开始处理时
 */
export interface StartMessage {
  type: 'start';
  display_name: string;
  model: string;
  provider: string;
  task_id: string;
  security_check?: SecurityCheck;
}

/**
 * thought类型 - LLM思考
 * 发送时机：ReAct第1阶段，LLM分析任务
 * 【小查修复2026-03-09】action_tool和params改为可选
 */
export interface ThoughtMessage {
  type: 'thought';
  step: number;
  content: string;
  thought?: string;    // LLM的思考过程（来自JSON的thought字段）
  reasoning?: string;  // LLM的分析推理（来自JSON的reasoning字段）
  tool_name?: string;  // 工具名称（统一使用 tool_name）
  tool_params?: Record<string, any>;  // 工具参数（统一使用 tool_params）
}

/**
 * action_tool类型 - 执行动作
 * 发送时机：ReAct第2阶段，工具执行时
 * 【小强修改2026-04-15】删除raw_data，统一使用execution_result
 */
export interface ActionToolMessage {
  type: 'action_tool';
  step: number;
  tool_name: string;
  tool_params: Record<string, any>;
  execution_status: 'success' | 'error' | 'warning';
  summary: string;
  execution_result?: Record<string, any> | null;  // 【修改2026-04-15】raw_data → execution_result
  execution_time_ms?: number;  // 【新增2026-04-15】
  action_retry_count: number;
}

/**
 * observation类型 - 工具执行完成提示
 * 发送时机：ReAct第3阶段，工具执行完成后
 * 【2026-04-07 小资精简】后端删除第二次LLM调用后，observation只保留基础字段
 * 工具执行结果已在 action_tool 阶段完整显示，本阶段仅作轻量提示
 * 【2026-04-07 小沈新增】添加tool_name字段，显示工具名称
 */
export interface ObservationMessage {
  type: 'observation';
  step: number;
  timestamp: number;
  content: string;
  tool_name?: string;  // 工具名称（可选）
}

/**
 * chunk类型 - 流式内容片段
 * 发送时机：普通对话时，AI生成文本的流式片段
 */
export interface ChunkMessage {
  type: 'chunk';
  content: string;
  is_reasoning: boolean; // 统一使用 snake_case（与后端一致）
}

/**
 * final类型 - 最终回复
 * 发送时机：任务完成时
 */
export interface FinalMessage {
  type: 'final';
  content: string;
}

/**
 * error类型 - 错误
 * 发送时机：发生错误时
 * 【小查修复2026-03-13】补充完整11个字段，与API文档对齐
 * 【小沈修改2026-04-15】删除code字段，统一使用error_message字段
 */
export interface ErrorMessage {
  type: 'error';
  error_type: string;       // 必填
  error_message: string;   // 必填 【修改2026-04-15】message → error_message
  timestamp: string;       // 必填
  model?: string;         // 可选
  provider?: string;      // 可选
  details?: string;       // 可选
  stack?: string;         // 可选
  retryable?: boolean;    // 可选
  retry_after?: number;   // 可选
  recoverable?: boolean;  // 可选 【新增2026-04-15】
  context?: {             // 可选 【新增2026-04-15】
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

/**
 * status类型值
 */
export type StatusValue = 'interrupted' | 'paused' | 'resumed' | 'retrying';

/**
 * status类型 - 执行状态
 * 发送时机：状态变化时（暂停、恢复、中断、重试）
 * 【2026-03-11 重命名】status_value -> incident_value
 * 【2026-03-14 小查修复】按API文档要求补充完整字段（5个字段）
 */
export interface StatusMessage {
  type: 'incident';
  incident_value: StatusValue;
  message: string;
  timestamp: string;       // 必填，时间戳
  wait_time?: number;    // 仅 retrying 时可选，重试等待秒数
}

// ============================================================
// 联合类型
// ============================================================

/**
 * 流式消息联合类型 - 所有可能的响应类型
 */
export type StreamMessage = 
  | StartMessage 
  | ThoughtMessage 
  | ActionToolMessage 
  | ObservationMessage 
  | ChunkMessage 
  | FinalMessage 
  | ErrorMessage 
  | StatusMessage;

// ============================================================
// 辅助类型
// ============================================================

/**
 * 检查是否为指定类型
 */
export function isStartMessage(msg: StreamMessage): msg is StartMessage {
  return msg.type === 'start';
}

export function isThoughtMessage(msg: StreamMessage): msg is ThoughtMessage {
  return msg.type === 'thought';
}

export function isActionToolMessage(msg: StreamMessage): msg is ActionToolMessage {
  return msg.type === 'action_tool';
}

export function isObservationMessage(msg: StreamMessage): msg is ObservationMessage {
  return msg.type === 'observation';
}

export function isChunkMessage(msg: StreamMessage): msg is ChunkMessage {
  return msg.type === 'chunk';
}

export function isFinalMessage(msg: StreamMessage): msg is FinalMessage {
  return msg.type === 'final';
}

export function isErrorMessage(msg: StreamMessage): msg is ErrorMessage {
  return msg.type === 'error';
}

export function isStatusMessage(msg: StreamMessage): msg is StatusMessage {
  return msg.type === 'incident';
}

// ============================================================
// 聊天相关类型
// ============================================================

/**
 * 聊天消息（用户发送的消息）
 */
export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

/**
 * 聊天请求参数
 */
export interface ChatRequest {
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
  provider?: string;
  model?: string;
  task_id?: string;
  session_id?: string;
}

/**
 * API响应基础类型
 */
export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data?: T;
}

/**
 * 任务控制响应
 */
export interface TaskControlResponse {
  success: boolean;
  message: string;
}

/**
 * 分页响应
 */
export interface NextPageResponse {
  success: boolean;
  data?: any;
  next_page_token?: string;
  has_more: boolean;
}

// ============================================================
// NewChatContainer 专用类型 - 小新 2026-03-13
// ============================================================

/**
 * 聊天消息（扩展）
 * 【小查修复2026-03-13】扩展error相关字段，与API文档11个字段对齐
 */
export interface Message extends ChatMessage {
  id: string;
  timestamp: Date;
  executionSteps?: ExecutionStep[];
  isStreaming?: boolean;
  isError?: boolean;
  // 错误相关字段（与API文档对齐）
  // 【小沈修改2026-04-15】删除errorCode，添加errorRecoverable和errorContext
  errorMessage?: string;     // error_message - 错误消息内容
  errorType?: string;        // error_type
  errorDetails?: string;     // details
  errorStack?: string;       // stack
  errorRetryable?: boolean;  // retryable
  errorRetryAfter?: number;  // retry_after
  errorTimestamp?: string;   // timestamp
  errorRecoverable?: boolean; // recoverable 【新增2026-04-15】
  errorContext?: {           // context 【新增2026-04-15】
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
  model?: string;
  provider?: string;
  display_name?: string;
  is_reasoning?: boolean;
}

/**
 * 历史消息加载结果
 */
export interface HistoryLoadResult {
  messages: Message[];
  title: string;
  sessionId: string;
  version?: number;
  title_locked?: boolean;
}
