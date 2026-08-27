// 编辑历史: 2026-07-16 小欧 - Message 接口增 thought 字段
// 编辑历史: 2026-08-22 小欧 - sessionModel 结构化: 新增 SessionModelOverride 接口; HistoryLoadResult model_override→sessionModel
// 编辑历史: 2026-08-22 小欧 - model结构化归一: SessionModelOverride 补 api_base
// 编辑历史: 2026-08-26 小欧 - 8.4.7 移除安全校验旧字段、ActionToolMessage→ActionMessage、新增 StartInfoMessage/StartMessage.content
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 新增ModelListItem接口(模型列表项结构)
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

import type { ExecutionStep } from '../utils/sse';

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
  content?: string; // context_summary 上下文摘要（4.9.2.7）
}

/**
 * startinfo类型 - 轻量占位（仅 SSE 不落库）
 * 【小欧 2026-08-26 8.4】驱动任务信息条状态徽标（4.9.2.7）
 */
export interface StartInfoMessage {
  type: 'startinfo';
  task_id: string;
  display_name?: string;
  provider?: string;
  model?: string;
  ai_message_id?: string;
}

/**
 * thought类型 - LLM思考
 * 发送时机：ReAct第1阶段，LLM分析任务
 * 【小查修复2026-03-09】动作类型字段和params改为可选
 */
export interface ThoughtMessage {
  type: 'thought';
  step: number;
  content: string;
  thought?: string; // LLM的思考过程（来自JSON的thought字段）
  reasoning?: string; // LLM的分析推理（来自JSON的reasoning字段）
  tool_name?: string; // 工具名称（统一使用 tool_name）
  tool_params?: Record<string, unknown>; // 工具参数（统一使用 tool_params）
}

/**
 * action类型 - 工具调用步骤新结构（4.9.2.9，禁止保留旧动作类型名）
 * 【小欧 2026-08-26 8.4】exec_type single/multi + tools 数组（单工具也一个元素）
 */
export interface ActionMessage {
  type: 'action';
  step: number;
  exec_type: 'single' | 'multi';
  tools: Array<{
    tool: string;
    target?: string; // file→file_path / shell→command / network→url 等（后端已提取）
    params?: Record<string, unknown>; // 供回放重建 FC 参数
  }>;
}

/**
 * Observation数据结构
 * 【Phase 2 2026-06-22 小欧】observation改为llm_data+tool_result+other_data三字段
 */
export interface ObservationData {
  llm_data?: Record<string, unknown>; // 完整llm_data（含summary/action/status/duration_ms/metrics）
  tool_result?: unknown; // 完整data（工具返回的业务数据）
  other_data?: {
    // 控制字段
    return_direct?: boolean;
    warning?: string;
    attachment?: unknown;
    retry_count?: number;
    [key: string]: unknown;
  };
  // 并行tool call时保留每个call的完整数据映射 — 小健 2026-06-25
  parallel_results?: Array<{
    tool_name: string;
    tool_params: Record<string, unknown>;
    llm_data: Record<string, unknown>;
    tool_result: unknown;
    other_data: Record<string, unknown>;
  }>;
  // 兼容旧格式字段（Phase 1遗留，可选）
  summary?: string;
  tool_name?: string;
  tool_params?: Record<string, unknown>;
  return_direct?: boolean;
  execution_status?: string;
  error_message?: string;
  warning?: string;
  next_actions?: Array<{
    tool: string;
    description: string;
    when?: string;
    params?: Record<string, unknown>;
  }>;
  attachment?: unknown;
}

/**
 * observation类型 - 工具执行完成提示
 * 发送时机：ReAct第3阶段，工具执行完成后
 * 【2026-05-22 小沈】observation改为JSON对象（第13章设计方案）
 * 【向后兼容】保留content字段，但优先使用observation.summary
 */
export interface ObservationMessage {
  type: 'observation';
  step: number;
  timestamp: number;
  observation: ObservationData; // observation JSON对象
  code?: string; // 状态码（SUCCESS/ERROR/WARNING）
  content?: string; // 【废弃】保留向后兼容，使用observation.summary
  tool_name?: string; // 【废弃】保留向后兼容，使用observation.tool_name
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
  error_type: string; // 必填
  error_message: string; // 必填 【修改2026-04-15】message → error_message
  timestamp: string; // 必填
  model?: string; // 可选
  provider?: string; // 可选
  details?: string; // 可选
  stack?: string; // 可选
  retryable?: boolean; // 可选
  retry_after?: number; // 可选
  context?: {
    // 可选 【新增2026-04-15】
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
}

/**
 * status类型值
 */
export type StatusValue = 'cancelled' | 'paused' | 'resumed' | 'retrying';

/**
 * status类型 - 执行状态（生命周期 Step 统一约定 v3.2）
 * 发送时机：状态变化时（取消/暂停/恢复/重试）
 * 【北京老陈 2026-07-13 小欧】incident_value 已废弃，直接用 type 表示终态/生命周期
 */
export interface StatusMessage {
  type: 'cancelled' | 'paused' | 'retrying' | 'resumed';
  message: string;
  timestamp: string; // 必填，时间戳
  confirm_id?: string; // 仅 paused(HITL) 时可选
  tool_name?: string; // 仅 paused(HITL) 时可选
  params?: Record<string, unknown>; // 仅 paused(HITL) 时可选
  safety_level?: string; // 仅 paused(HITL) 时可选
  wait_time?: number; // 仅 retrying 时可选，重试等待秒数
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
  | ActionMessage
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

export function isActionMessage(msg: StreamMessage): msg is ActionMessage {
  return msg.type === 'action';
}

export function isObservationMessage(
  msg: StreamMessage
): msg is ObservationMessage {
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
  return (
    msg.type === 'cancelled' ||
    msg.type === 'paused' ||
    msg.type === 'retrying' ||
    msg.type === 'resumed'
  );
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
  context_link_mode?: 'linked' | 'independent'; // 默认 independent（后端 ChatRequest 同名默认）
}

/**
 * API响应基础类型
 */
export interface ApiResponse<T = unknown> {
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
  thought?: string; // 小欧 2026-07-16 LLM推理过程
  isStreaming?: boolean;
  isError?: boolean;
  // 【小沈修复2026-04-23】P0-1: 添加发送状态，用于显示发送失败标识
  sendStatus?: 'sending' | 'sent' | 'failed';
  // 错误相关字段（与API文档对齐）
  // 【小沈修改2026-04-16】删除errorDetails/errorStack/errorRetryable，后端已删除这些字段
  errorMessage?: string; // error_message - 错误消息内容
  errorType?: string; // error_type
  errorTimestamp?: string; // timestamp
  errorContext?: {
    // context 【新增2026-04-15】
    step?: number;
    model?: string;
    provider?: string;
    thought_content?: string;
  };
  errorRetryAfter?: number; // retry_after
  model?: string;
  provider?: string;
  display_name?: string;
  is_reasoning?: boolean;
}

/**
 * 会话级模型覆盖(L2) — 结构化 provider+model, 与后端 SessionModelOverride 对齐
 * 2026-08-22 小欧 归一报告v1.25 6.1: 补 api_base?(端点定位) 与后端 ModelRef 形态一致
 */
export interface SessionModelOverride {
  provider: string;
  model: string;
  api_base?: string;
  display_name?: string;
}

// 2026-08-27 小欧 三堂会审: 模型列表项结构, 与后端/config/models返回对齐
export interface ModelListItem {
  provider: string;
  model: string;
  display_name: string;
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
  sessionModel?: SessionModelOverride | null;
}
