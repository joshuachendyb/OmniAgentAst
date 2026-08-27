// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: 从utils/sse.ts抽ExecutionStep至此, 断 chat→sse→api→chat 类型环(sse↔api循环)
/**
 * 执行步骤类型 - 与后端字段完全对应，便于调试和理解
 * 原定义位于 utils/sse.ts，因 sse.ts 与 services/api.ts 相互引用形成类型环，
 * 故将 ExecutionStep 提升为本独立类型模块（sse.ts 保留 re-export 兼容历史引用）。
 *
 * 【重要】type 取值与后端一致，详见 utils/sse.ts 内分类说明。
 */

export interface ExecutionStep {
  // === 通用字段 ===
  // 【小欧 2026-08-26 8.4】①'动作类型名'全链替换为'action'（后端 ActionStep.TYPE 已改，
  //   禁止 backward，见 4.9.2.9）；②新增 MetaStep 类事件 type：
  //   thought-start/usage/stats/final_stats/context_overview/truncated/startinfo
  //   （数据源仍是一条 executionSteps 不拆流，渲染入口按 7.10 分流）
  type:
    | 'thought'
    | 'action'
    | 'observation'
    | 'chunk'
    | 'final'
    | 'error'
    | 'start'
    | 'startinfo'
    | 'thought-start'
    | 'usage'
    | 'stats'
    | 'final_stats'
    | 'context_overview'
    | 'truncated'
    | 'cancelled'
    | 'paused'
    | 'resumed'
    | 'retrying';
  content?: string; // 前端显示用：根据type使用不同字段填充小查修复202

  // 【6-03-09】添加task_id字段，用于分页请求
  task_id?: string; // 任务ID，用于分页请求

  // 【小强添加 2026-03-24】用户消息前40字
  user_message?: string; // 用户发送的消息内容预览

  // === 思考/动作提示字段（后端字段拆分） ===
  thinking_prompt?: string; // thought 类型的提示文本
  action_description?: string; // action 类型的描述文本
  action?: string; // 执行动作名称（历史兼容，保留原始字段）
  action_input?: unknown; // 工具调用参数（历史兼容，保留原始字段）

  // 【小新重构2026-03-09】thought类型需要的字段
  // 【小健建议2026-03-23】明确用途：LLM思考后决定的下一步动作
  tool_name?: string; // 【thought类型】LLM思考后决定的下一步动作
  tool_params?: Record<string, unknown>; // 【thought类型】LLM思考后决定的参数

  step?: number;
  thought?: string;
  observation?: unknown; // ObservationData对象或字符串
  // 【小欧 2026-08-26 4.9.3】observation 新字段：工具结果数组，优先于 content/summary 读取
  tool_result?: unknown;
  result?: string;
  code?: string; // 【新增2026-05-22】状态码（SUCCESS/ERROR/WARNING）

  // === 【小新重构】type=action 新字段（与thought类型共用tool_name/tool_params）===
  execution_status?: 'success' | 'error' | 'warning'; // 执行状态（新）
  summary?: string; // 执行摘要（新）
  execution_result?: Record<string, unknown> | null; // 执行结果 【修改2026-04-15】raw_data → execution_result
  execution_time_ms?: number; // 执行耗时 【新增2026-04-15】
  action_retry_count?: number; // 重试次数（新）

  // === type=observation 字段（精简版，2026-04-07 小资修改） ===
  // 后端删除第二次LLM调用后，observation只保留基础字段
  // 工具执行结果已在 action 阶段完整显示（execution_status/summary/execution_result）
  // 【注意】obs_* 字段已删除，如需使用工具结果请从 action 阶段获取
  // tool_name 已在上面 动作类型 字段定义（第97行），此处不再重复

  // === type=chunk/final/start 字段 ===
  model?: string; // AI模型
  provider?: string; // AI提供商
  display_name?: string; // 显示名称

  // === type=final 字段 【新增2026-04-15】===
  response?: string; // 最终回答内容
  is_streaming?: boolean; // 是否流式输出
  is_finished?: boolean; // 是否已完成
  // === type=final 终态声明字段（2026-07-18 小欧 FinalStep 终态规整）===
  // 终态统一由 FinalStep 承载，outcome 声明具体终态结果；取消/失败不再单独 type
  outcome?: 'completed' | 'failed' | 'cancelled'; // 终态类型：完成/失败/取消
  error_type?: string; // 失败时的错误类型
  error_message?: string; // 失败/取消时的错误信息

  // === type=observation 字段 【新增2026-04-15】===
  return_direct?: boolean; // 是否直接返回
  // 并行tool call时保留每个call的完整数据映射 — 小健 2026-06-25
  parallel_results?: Array<{
    tool_name: string;
    tool_params: Record<string, unknown>;
    llm_data: Record<string, unknown>;
    tool_result: unknown;
    other_data: Record<string, unknown>;
  }>;

  // === 思考过程与正式内容区分字段（统一使用 is_reasoning snake_case）===
  is_reasoning?: boolean; // 是否为思考过程（true=思考过程，false=正式内容）
  reasoning?: string; // 思考过程内容（当 is_reasoning=true 时使用）

  // === 错误/中断字段 ===
  // 【三堂会审修复 2026-08-23 小欧】error_message/error_type 原在此重复声明(:153/:154 已定义),
  //   TS2300 Duplicate identifier 致 tsc --noEmit 失败, 删重复保留终态声明处单一权威定义
  message?: string; // interrupted 类型的中断信息

  // 【小新修复 2026-03-14】error类型完整字段（避免使用 as any）
  // 【小沈修改2026-04-15】删除code字段，统一使用error_message(字段定义见上 :153/:154)
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
  wait_time?: number; // 等待时间（秒）

  // === 【小欧 2026-08-26 8.4】action 新结构字段（exec_type single/multi + tools 数组）===
  exec_type?: 'single' | 'multi';
  tools?: Array<{
    tool: string;
    target?: string;
    params?: Record<string, unknown>;
  }>;

  // === 【小欧 2026-08-26 8.4/8.6】MetaStep 扩展字段（旧任务 null 须 ?. 防空）===
  severity?: 'info' | 'warn' | 'error';
  ai_message_id?: string;
  // usage（每轮 LLM 响应 usage）+ 四维累计（final._extra_fields 同名）
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  llm_call_count_token?: number;
  task_accumulated_tokens?: number;
  session_accumulated_tokens?: number;
  chain_accumulated_tokens?: number;
  // stats 流式统计
  step_count?: number;
  llm_call_count?: number;
  retry_count?: number;
  duration?: number; // 秒
  // final_stats 终态统计
  tool_stats?: Record<string, number>;
  artifacts?: Array<{ name: string; path: string; type: string }> | null;
  final_status?: 'completed' | 'failed' | 'cancelled';
  // context_overview
  message_count?: number;
  estimated_tokens?: number;
  injected_ratio?: number;

  // === 前端额外字段 ===
  timestamp: number; // 前端生成的时间戳
  contentStart?: number; // content起始位置（用于流式定位）
  contentEnd?: number; // content结束位置
}
