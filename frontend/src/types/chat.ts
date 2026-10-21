// 编辑历史: 2026-07-16 小欧 - Message 接口增 thought 字段
// 编辑历史: 2026-08-22 小欧 - sessionModel 结构化: 新增 SessionModelOverride 接口; HistoryLoadResult model_override→sessionModel
// 编辑历史: 2026-08-22 小欧 - model结构化归一: SessionModelOverride 补 api_base
// 编辑历史: 2026-08-26 小欧 - 8.4.7 移除安全校验旧字段、ActionToolMessage→ActionMessage、新增 StartInfoMessage/StartMessage.content
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 新增ModelListItem接口(模型列表项结构)
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从./execution(断类型环)
// 编辑历史: 2026-08-27 小欧 - 修复base-4: 补isStartInfoMessage守卫并将StartInfoMessage纳入StreamMessage联合
// 编辑历史: 2026-09-01 小欧 - prettier格式统一: 修复函数签名多行→单行(行长度超80字符), 防止格式再次出错
// 编辑历史: 2026-09-07 小欧 - 4.4.1旧case清零: 删StatusValue/StatusMessage的cancelled分支与isStatusMessage的cancelled判断(取消收尾单一由final+cancelled承担)
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.6: HistoryLoadResult 补 linkEnabled(会话 link 开关镜像);
//   ChatRequest 删死字段 context_link_mode(后端 5.7.9 已删该请求字段) 并补 link_enabled(随消息携带的新契约字段) — 小欧-2026-10-03
// 编辑历史: 2026-10-10 小欧 - 文档[16] §3.6.2/§3.6.6: 新增 WorkspaceEntry / UnusableEntry / WorkspacesResponse 三类型（会话使用的目录；不进 SendOpts，前端不携带只调 GET/PATCH）
/**
 * 流式API响应类型定义
 *
 * 用于定义ReAct流式API返回的8种消息类型
 * 与后端设计文档完全对应
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-03-09
 */

import type { ExecutionStep } from './execution';

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
 * 2026-10-04 小欧 文档[8]§4.1.4 死契约清理(禁 backward, 不留兼容壳): 删 ObservationData 与 ObservationMessage ——
 *   二者描述的是后端 08-18 之前的旧 observation 消息契约(parallel_results/tool_params/return_direct/
 *   execution_status 等键后端从不下发), 全仓零生产消费(仅本文件 StreamMessage 联合成员 + 一个无人调用的
 *   类型守卫 isObservationMessage); 现行契约由 sseParser 解析进 ExecutionStep, 载体是 tool_result 数组。
 *   同时删 isObservationMessage 守卫与其在 StreamMessage 中的联合成员 — 小欧-2026-10-04
 */

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
export type StatusValue =
  | 'paused'
  | 'resumed'
  | 'retrying'
  | 'installing'
  | 'summarizing';

/**
 * status类型 - 执行状态（生命周期 Step 统一约定 v3.2）
 * 发送时机：状态变化时（取消/暂停/恢复/重试）
 * 【北京老陈 2026-07-13 小欧】incident_value 已废弃，直接用 type 表示终态/生命周期
 */
export interface StatusMessage {
  type: 'paused' | 'retrying' | 'resumed' | 'installing' | 'summarizing';
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
  | StartInfoMessage
  | ThoughtMessage
  | ActionMessage
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
export function isStartMessage(
  msg: StreamMessage
): msg is StartMessage | StartInfoMessage {
  // 2026-08-27 小欧 修复base-4: startinfo 同属 start 类事件, 一并识别(满足守卫覆盖)
  return msg.type === 'start' || msg.type === 'startinfo';
}

export function isStartInfoMessage(
  msg: StreamMessage
): msg is StartInfoMessage {
  // 2026-08-27 小欧 修复base-4: 新增 startinfo 专用类型守卫
  return msg.type === 'startinfo';
}

export function isThoughtMessage(msg: StreamMessage): msg is ThoughtMessage {
  return msg.type === 'thought';
}

export function isActionMessage(msg: StreamMessage): msg is ActionMessage {
  return msg.type === 'action';
}

// 2026-10-04 小欧: 删 isObservationMessage 守卫(随 ObservationMessage 一起下线, 全仓零调用) — 小欧-2026-10-04

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
    msg.type === 'paused' ||
    msg.type === 'retrying' ||
    msg.type === 'resumed' ||
    msg.type === 'installing' ||
    msg.type === 'summarizing'
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
  // 会话 link 开关值随消息携带(后端新增契约字段)。禁复用 context_link_mode(旧"临时模式"通道, 复活即双通道)。
  link_enabled?: boolean;
  allow_interject?: boolean; // 2026-10-06 小欧 - 文档[11] 3.4.3: 请求体随消息携带(后端唯一写入口)
  // 2026-10-21 小杨 - 文档[28] 4.1.6(M20)：引用条目随消息同批上行（搭便车，不单独上传）。
  //   后端 models.py 的 ChatRef 与本类型一一对应；正文当轮即弃，不入库。
  refs?: ChatRefPayload[];
}

/**
 * 输入框引用条目（前端 → 后端随消息上行的引用载荷）
 * 2026-10-21 小杨 - 文档[28] 4.1.6(M20)/4.4.3 新建
 *
 * 语义：kind=file 整文件引用 / kind=selection 行区间引用。
 * ⚠ `content` 是**当轮内存态**（用户选中/读到的正文），发完即弃，不入库、不进历史。
 *   path 才是长期有效信息（Agent 日后可凭 path 重读）。
 */
export interface ChatRefPayload {
  kind: 'file' | 'selection';
  label: string;
  path: string;
  content: string;
  size?: number;
  lineRange?: { start: number; end: number } | null;
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
  // 【小沈修复2026-04-23】添加发送状态，用于显示发送失败标识
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
  // 会话级 link 开关镜像(后端真源, 随会话加载下发)
  linkEnabled?: boolean;
  allowInterject?: boolean; // 2026-10-06 小欧 - 文档[11] 3.4.6: 历史读取结果镜像
}

/**
 * 发送选项（对象参数 — 文档[11] 决策 14: 两个相邻 boolean 位置参数 TS 拦不住错位；
 * 集中单点定义，消费方 import，不散在各处写字面量（DRY）。
 */
export interface SendOpts {
  linkEnabled: boolean;
  allowInterject: boolean;
  /**
   * 2026-10-21 小杨 - 文档[28] 4.1.6(M20)：本轮引用条目（当轮有效，不入库）。
   * 未传或空数组 = 无引用（body 不带 refs 键，零退化）。
   */
  refs?: ChatRefPayload[];
}

/**
 * 会话使用的目录（后端 chat_session_workspaces 表）
 * 2026-10-10 小欧 - 文档[16] §3.6.2 新增
 * ⚠ 不进 SendOpts：前端不携带目录列表，只调 GET/PATCH 端点（独立端点，决策77简化）
 */
export interface WorkspaceEntry {
  path: string;
}

/**
 * 不可用目录（禁区/非法/非目录），后端 classify_workspace_rows 判定
 * 2026-10-10 小欧 - 文档[16] §3.6.2 新增
 * kind 与后端 unusable 项的机器可读分类一一对应（reconcile 按 kind 行事）
 */
export interface UnusableEntry {
  path: string;
  reason: string;
  kind: 'illegal' | 'denied' | 'missing';
}

/**
 * GET /sessions/{id}/workspaces 响应
 * 2026-10-10 小欧 - 文档[16] §3.6.1/3.6.6
 * project_root/allowed_dirs 为只读字段（决策82），只展示不提交
 */
export interface WorkspacesResponse {
  session_id: string;
  workspaces: WorkspaceEntry[];
  unusable: UnusableEntry[];
  project_root: string;
  allowed_dirs: string[];
}
