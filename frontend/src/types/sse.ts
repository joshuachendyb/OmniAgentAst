// 编辑历史: 2026-08-28 小欧 - 由 utils/sse.ts 抽离SSE专属类型归一至横切层; ExecutionStep已居types/execution.ts故不重复导出 - 小欧-2026-08-28
// 编辑历史: 2026-08-30 小欧 - 13.14 新增 roundUsage/taskAccumulated/sessionAccumulated/chainAccumulated 四字段（后端直发P/C/T三数字，废止前端累加） - 小欧-2026-08-30
// 编辑历史: 2026-10-10 小欧 (本日汇总, 仅留此一条) - 结构定稿: ContextOverviewFrame 只保留
//   conv_context/inject_context 双分组, compressed 定为 string(禁backward), 删 compress_saved_pct
// 编辑历史: 2026-09-06 小欧 - B2方案C: error 事件补充可选 step 字段(blocked/timeout 带 step 供 sseOnError 聚合 deniedStepSet 停齿轮) —
//   小欧-2026-09-06
// 编辑历史: 2026-09-06 小欧 - B2方案C(6.4): SSEError 补可选 tool_name(被拒工具名)——blocked/timeout 错误
//   携带, 供 sseOnError 聚合被拒工具点名条(deniedEntries: tool+reason)承灰字链路数据源 — 小欧-2026-09-06
// 编辑历史: 2026-09-08 小欧 - 六章6.3.1(回归总原则): SSEError 补可选 from_backend(后端业务错误来源标记,
//   useChatCallbacks 据此分道只进页面级错误提示不弹窗); 6.3.4 补可选 request_level(请求级step=0标记, 位4图标分层);
//   新增 LiveError 接口(页面级错误数据源对象形态) — 小欧-2026-09-08
// 编辑历史: 2026-09-10 小欧 - 阶段一S1清死代码: ReconnectConfig接口删enabled字段; 阶段二S2提前实施:
//   UseSSEReturn新增executionStepsRef可选字段(供外部直接读取ref) — 小欧-2026-09-10
// 编辑历史: 2026-09-11 小欧 - 三堂会审修复: FinalStatsFrame.artifacts补tool_name?(与后端4字段契约对齐, 见handle_action.py 11.6.2; 原3字段漏tool_name致产出物编译错) — 小欧-2026-09-11
// 编辑历史: 2026-09-12 小欧 - 三堂会审修复: TaskMetaFrames 删 usage 死字段(与 taskAccumulated 完全同值的 P/C/T 映射, 消费已归一 taskAccumulated, sseParser/useTaskInfo 同步收敛) — 小欧-2026-09-12
// 编辑历史: 2026-09-12 小欧 - 三堂会审修复: SSEConfig删taskId死字段(全仓无config.taskId消费点, useSSE只读baseURL/sessionId/token) — 小欧-2026-09-12
// 编辑历史: 2026-09-17 小欧 - 实施: 新增 ClockSignals 信号打包类型(heartbeatTs/lastBizTsRef/lastDataTsRef) + UseSSEReturn 新增 waitClock 字段 - 小欧-2026-09-17
// 编辑历史: 2026-09-17 小欧 - 对齐设计: ClockSignals 移至 UseSSEReturn 前(与设计一致), 字段序 lastBizTsRef/lastDataTsRef/heartbeatTs, 注释改行内式 - 小欧-2026-09-17
// 编辑历史: 2026-09-29 21:37:55 小欧 - [63] 5.7: UseSSEReturn 接口整删（useSSE 已删/5.6，零消费者），
//   ExecutionStep 导入随之失效删除；ClockSignals 保留（5.3/5.4 钟面信号与 5.5 waitClock 在用） — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-10-04 小欧 - ContextOverviewFrame 补两个 injected 键(后端一直在发, parser 此前丢弃),
//   与 types/execution.ts 的平行声明对齐 — 小欧 2026-10-04
// 编辑历史: 2026-10-04 小欧 - TaskMetaFrames 加 contextWindow(运行时上下文窗口, 来自 usage 帧), emptyMetaFrames 同步置 null
// 编辑历史: 2026-10-08 小欧 - ContextOverviewFrame: 删 injected_ratio(>1 才代表压缩生效, 标签"压缩比"方向相反),
//   改 compressed(是否压缩) + compress_saved_pct(省了多少%); 字段契约须与后端 build_context_overview 同步。

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
  // 2026-09-11 小欧 三堂会审修复: artifacts 补 tool_name?——后端 final_stats 实为 4 字段契约
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
  // 小欧 2026-09-11 M5a(finalStats补全): 补全统计键——与后端 build_final_stats_step 7 键对齐(3.4 FinalStatsStep._extra_fields) — 小欧-2026-09-11
  step_count?: number;
  llm_call_count?: number;
}
export interface ContextOverviewFrame {
  // 2026-10-10 小欧: 结构定稿, 只认这两个分组(禁 backward: 不再加其他形状)
  conv_context?: ConvContextFrame;
  inject_context?: InjectContextFrame;
  content?: string;
}
// 2026-10-09 小欧: conv 侧独立成 interface —— 「对话上下文」段只读这一个, 不越界
export interface ConvContextFrame {
  message_count?: number | '';
  estimated_tokens?: number | '';
  truncated?: boolean | '';
}
// 2026-10-09 小欧: inject 侧独立成 interface —— 「历史上下文」段只读这一个
export interface InjectContextFrame {
  injected_message_count?: number | '';
  injected_estimated_tokens?: number | '';
  // 后端成品情况文字(压缩率/无注入/压缩失败), 前端原样直显不拼装不拆解不改写。
  //   2026-10-10: 「第N个link任务, 」前缀归 content(身份标识), 不在本字段
  compressed?: string;
  summary?: string;
}
export interface TaskMetaFrames {
  contextSummary: string; // start.content
  startInfo: StartInfoFrame | null;
  startTimestamp: number; // start 事件时间戳（供 useTaskInfo 过程条首行使用）
  // 2026-09-12 小欧: 删 usage 死字段(与 taskAccumulated 完全同值的 P/C/T 映射, useTaskInfo 已归一到 taskAccumulated) — 小欧-2026-09-12
  roundUsage?: { prompt: number; completion: number; total: number } | null; // 本轮三值（后端 prompt_tokens 直取）
  // 2026-10-04 小欧: usage 帧带来的运行时上下文窗口(message_builder.MAX_CONTEXT_TOKENS), 供"本轮 P / 窗口"占用率
  contextWindow?: number | null;
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
  contextWindow: null,
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
  from_backend?: boolean; // 2026-09-08 小欧 6.3.1: 后端业务错误来源标记(sseParser onError 无条件 true), useChatCallbacks 据此分道只进页面级错误提示不弹窗 — 小欧-2026-09-08
  request_level?: boolean; // 2026-09-08 小欧 6.3.4: 请求级错误标记(sseParser 读原始 step===0), 位4图标请求级⛔区分执行级红圆底白× — 小欧-2026-09-08
}

/**
 * 页面级实时错误数据源对象形态
 * 文档：前端消息分类处理分析及设计 6.3.4（2026-09-08 裁定）
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
  // 2026-09-12 小欧 三堂会审修复: 删 taskId 死字段(YAGNI, 全仓无任何 config.taskId 消费点, useSSE 只读 baseURL/sessionId/token) — 小欧-2026-09-12
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
 * 2026-09-17 小欧 实施: 心跳等待感知钟面数据信号(打包透传, 链路只走单一 prop waitClock)
 */
export interface ClockSignals {
  lastBizTsRef: React.MutableRefObject<number>; // 最近一次业务事件到达(ms)
  lastDataTsRef: React.MutableRefObject<number>; // 最近一次任意数据到达(含心跳, ms)
  heartbeatTs: number; // 心跳到达时刻(ms), 0=未收到
}

/**
 * 错误类型分类
 * 【小强修复 2026-04-11】使用统一错误处理中心
 */ export type SSEErrorType =
  | 'idle_timeout'
  | 'request_timeout'
  | 'network'
  | 'server'
  | 'unknown'
  | 'empty_response'
  | 'connection_refused'
  | 'http_500'
  | 'fc_format_error'; // 小欧 2026-06-25: FC格式错误（可恢复）
