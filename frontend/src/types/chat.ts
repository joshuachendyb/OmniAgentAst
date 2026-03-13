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
  reasoning?: string;
  action_tool?: string;  // 可选：某些thought可能不包含动作
  params?: Record<string, any>;  // 可选：某些thought可能不包含参数
}

/**
 * action_tool类型 - 执行动作
 * 发送时机：ReAct第2阶段，工具执行时
 */
export interface ActionToolMessage {
  type: 'action_tool';
  step: number;
  tool_name: string;
  tool_params: Record<string, any>;
  execution_status: 'success' | 'error' | 'warning';
  summary: string;
  raw_data?: Record<string, any> | null;
  action_retry_count: number;
}

/**
 * observation类型 - 执行结果判断
 * 发送时机：ReAct第3阶段，工具执行完成后
 * 【2026-03-11 重命名】字段加 obs_ 前缀，避免与其他type字段混淆
 */
export interface ObservationMessage {
  type: 'observation';
  step: number;
  obs_execution_status: 'success' | 'error' | 'warning';
  obs_summary: string;
  obs_raw_data?: Record<string, any> | null;
  content: string;
  obs_reasoning?: string;
  obs_action_tool: string;
  obs_params: Record<string, any>;
  is_finished: boolean;
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
 */
export interface ErrorMessage {
  type: 'error';
  code: string;
  message: string;
  error_type?: string;
  details?: string;
  stack?: string;
  retryable?: boolean;
  retry_after?: number;
}

/**
 * status类型值
 */
export type StatusValue = 'interrupted' | 'paused' | 'resumed' | 'retrying';

/**
 * status类型 - 执行状态
 * 发送时机：状态变化时（暂停、恢复、中断、重试）
 * 【2026-03-11 重命名】status_value -> incident_value
 */
export interface StatusMessage {
  type: 'incident';
  incident_value: StatusValue;
  message: string;
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
  errorType?: string;        // error_type
  errorCode?: string;       // code
  errorDetails?: string;    // details
  errorStack?: string;      // stack
  errorRetryable?: boolean; // retryable
  errorRetryAfter?: number; // retry_after
  errorTimestamp?: string;  // timestamp
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
