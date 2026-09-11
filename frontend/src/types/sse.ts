// 编辑历史: 2026-08-28 小欧 - 由 utils/sse.ts 抽离SSE专属类型归一至横切层; ExecutionStep已居types/execution.ts故不重复导出 - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 13.14 新增 roundUsage/taskAccumulated/sessionAccumulated/chainAccumulated 四字段（后端直发P/C/T三数字，废止前端累加） - 小欧-2026-08-30
// 编辑历史: 2026-09-06 小欧 - B2方案C(北京老陈裁定): error 事件补充可选 step 字段(blocked/timeout 带 step 供 sseOnError 聚合 deniedStepSet 停齿轮) — 小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4, 北京老陈裁定): SSEError 补可选 tool_name(被拒工具名)——blocked/timeout 错误
//   携带, 供 sseOnError 聚合被拒工具点名条(deniedEntries: tool+reason)承灰字链路数据源 — 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 六章6.3.1(北京老陈裁定回归总原则): SSEError 补可选 from_backend(后端业务错误来源标记,
//   useChatCallbacks 据此分道只进P3不弹窗); 6.3.4 补可选 request_level(请求级step=0标记, 位4图标分层);
//   新增 LiveError 接口(P3数据源对象形态) — 小欧-2026-09-08
// 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: ReconnectConfig接口删enabled字段; 阶段二S2提前实施:
//   UseSSEReturn新增executionStepsRef可选字段(供外部直接读取ref) — 小欧-2026-09-10
// 编辑历史: 2026-09-11 小欧 - 三堂会审P1-2: FinalStatsFrame.artifacts补tool_name?(与后端4字段契约对齐, 见handle_action.py 11.6.2; 原3字段漏tool_name致产出物编译错) — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - P1-11三堂会审修复: TaskMetaFrames 删 usage 死字段(与 taskAccumulated 完全同值的 P/C/T 映射, 消费已归一 taskAccumulated, sseParser/useTaskInfo 同步收敛) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - P0-3三堂会审修复: SSEConfig删taskId死字段(全仓无config.taskId消费点, useSSE只读baseURL/sessionId/token) — 小欧-2026-09-12
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
  // 2026-09-11 小欧 三堂会审P1-2: artifacts 补 tool_name?——后端 final_stats 实为 4 字段契约
  //   (tool_name/name/path/type, 见 backend/app/services/agent/handlers/handle_action.py 11.6.2),
  //   原 3 字段漏 tool_name 致 StaticStatsBlock 产出物列表编译错(TS2339) — 小欧-2026-09-11
  artifacts?: Array<{
    tool_name?: string;
    name: string;
    path: string;
    type: string;
  }> | null;
  final_status?: 'completed' | 'failed' | 'cancelled';
  retry_count?: number;
  // 小欧 2026-09-11 第七章 M5a(R7): 补全统计键——与后端 build_final_stats_step 7 键对齐(3.4 FinalStatsStep._extra_fields) — 小欧-2026-09-11
  step_count?: number;
  llm_call_count?: number;
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
  // 2026-09-12 小欧 P1-11: 删 usage 死字段(与 taskAccumulated 完全同值的 P/C/T 映射, useTaskInfo 已归一到 taskAccumulated) — 小欧-2026-09-12
  roundUsage?: { prompt: number; completion: number; total: number } | null; // 本轮三值（后端 prompt_tokens 直取）
  taskAccumulated?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null; // 任务累计三值
  sessionAccumulated?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null; // 会话累计三值（顶栏）
  chainAccumulated?: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  } | null; // 链累计三值
  stats: StatsFrame | null; // 保留上一帧
  finalStats: FinalStatsFrame | null;
  contextOverview: ContextOverviewFrame | null; // 保留上一帧
  truncated: { content: string; severity: 'info' | 'warn' | 'error' } | null;
}
export const emptyMetaFrames = (): TaskMetaFrames => ({
  contextSummary: '',
  startInfo: null,
  startTimestamp: 0,
  roundUsage: null,
  taskAccumulated: null,
  sessionAccumulated: null,
  chainAccumulated: null,
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
  // 可选字段（11个）
  step?: number; // 2026-09-06 小欧 B2(方案C): 事件所属工具执行轮 step 号, 供 blocked/timeout 错误聚合 deniedStepSet 停齿轮 — 小欧-2026-09-06
  tool_name?: string; // 2026-09-06 小欧 B2(6.4): 被拒工具名(blocked/timeout 由后端事件带), 供被拒工具点名条灰字 — 小欧-2026-09-06
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
  from_backend?: boolean; // 2026-09-08 小欧 6.3.1: 后端业务错误来源标记(sseParser onError 无条件 true), useChatCallbacks 据此分道只进P3不弹窗 — 小欧-2026-09-08
  request_level?: boolean; // 2026-09-08 小欧 6.3.4: 请求级错误标记(sseParser 读原始 step===0), 位4图标请求级⛔区分执行级红圆底白× — 小欧-2026-09-08
}

/**
 * P3 页面级实时错误数据源对象形态
 * 文档：[10]前端消息分类处理分析及设计 6.3.4（北京老陈 2026-09-08 裁定）
 * useChatFacade onError 包装器不再把 SSEError 压成 string, 改构 LiveError{text, requestLevel} 上抛;
 * 前端本地错误(string) 缺 requestLevel → false, 位4 沿用执行级样式。
 */
export interface LiveError {
  text: string;
  requestLevel: boolean;
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
  // 2026-09-12 小欧 P0-3三堂会审修复: 删 taskId 死字段(YAGNI, 全仓无任何 config.taskId 消费点, useSSE 只读 baseURL/sessionId/token) — 小欧-2026-09-12
}

/**
 * SSE重连配置
 */
export interface ReconnectConfig {
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
  executionStepsRef: React.MutableRefObject<ExecutionStep[]>; // 小欧 2026-09-10 S2: 暴露 ref 供外部直接读取（必填，useSSE 总会返回）
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
