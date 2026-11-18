// 编辑历史: 2026-08-30 小欧 - adaptTaskDetail修复: ①accumulated_usage为null时回退读task_accumulated_tokens(每轮即时落库更可靠); ②tool_stats过滤tool_name为null的条目; TaskDetail新增task_accumulated_tokens字段
// 编辑历史: 2026-09-01 小欧 - 任务统计增强v0.8: TaskArtifact补tool_name(4字段对齐artifacts)、TaskDetail补provider/model/created_at/updated_at、adaptTaskDetail透传四字段 - 小欧-2026-09-01
// 编辑历史: 2026-09-02 小欧 - 会话信任功能修复 v1.5(定案): TrustedTool增path字段、getTrust映射path(null=工具级)、revokeTrust增可选path登录?path=精确撤销(tool,path) — 小欧-2026-09-02
// 编辑历史: 2026-09-28 小欧 - 活跃任务注入(设计): SessionTaskItem加merged_inputs字段 — 小欧-2026-09-28
// 编辑历史: 2026-10-03 小欧 - SessionTaskItem 补 context_root_task_id(后端 5.7.4 已返回),
//   作为 TaskListPanel 组号徽标的唯一分组键; context_link_mode 保留(列仍在返回, 供快照展示, 非分组键) — 小欧-2026-10-03
// 编辑历史: 2026-10-10 小欧 (- TaskDetail 加 history_context_first
//   (历史任务回显首帧); 其类型复用 ContextOverviewFrame 单一真源, 禁在本文件手写窄类型副本(禁 backward)
// 编辑历史: 2026-10-11 10:13:16 小欧 - 北京老陈令「final 的时候回填事件列表」: TaskDetail 补 process_events(事件列表快照条目本体, 类型复用 useTaskInfo.ProcessEvent 单一真源, 内联 import() 避 api→hooks 反向依赖); adaptTaskDetail 同款透传(Array.isArray 守卫, 存量 null 兜底); executionApi 新增 saveTaskProcessEvents(POST /chat/execution/task/{id}/process-events, 失败只 reject 不抛业务链) — 小欧-2026-10-11
// 编辑历史: 2026-10-30 小欧 - 现场证据(北京老陈): 任务运行期间前端每 5s 轮询 listTasks,
//   用户没做任何操作却弹「后端响应超时，请重试」; 后台轮询不是用户动作(他不知道、也无法"重试"),
//   故本端点置 _silent 不弹全局 toast, 失败由各调用方自行收口自愈 — 小欧-2026-10-30
// 编辑历史: 2026-11-13 商量 - SessionTaskItem 补 creation_source(后端 chat_tasks 新列), 供 TaskListPanel 续跑徽标判定 — 商量-2026-11-13
// 编辑历史: 2026-11-14 商量 - SessionTaskItem.merged_inputs 由 string[] 升级 {content,msg_kind}[], 供同槽异标; 禁 backward 双读 — 商量-2026-11-14
// 编辑历史: 2026-11-17 小欧 - [46b] P2b 任务列表数据契约对齐: SessionTaskItem 补 ref_ledger/tool_paths 两快照字段(后端 /tasks 一次携带, 冷启动台账/推荐行数据源);
//   saveTaskProcessEvents 增可选第3参 refLedger 随 process-events 捎带台账快照(feature 层调用点传参, service 层不依赖 feature store) — 小欧-2026-11-17
// 编辑历史: 2026-11-18 小欧 - [46b] 会审整改: 抽 RefLedgerWireEntry 供读侧(ref_ledger 快照)与写侧
//   (saveTaskProcessEvents 第3参)共用一种形状 —— 原写侧 path 可选、读侧必有值, 同一实体两套形状;
//   空台账不再请求携带(空数组等价不携带) — 小欧-2026-11-18
// 编辑历史: 2026-11-18 小欧 - listTasks 走 dedupeGet(只合并同时在飞, 轮询必须每次发新请求)、
//   getTrust 走 sharedGet(信任清单只随写变化); 首屏两处各自取数不再叠加重复请求 — 小欧-2026-11-18
// 编辑历史: 2026-11-18 opencode - RefLedgerWireEntry 补 kind(引用种类随快照落库): 冷启动后
//   url 台账条目按外链打开, 不再被当文件重读 — opencode-2026-11-18
import api, { dedupeGet, sharedGet } from './client';
import type { ApiRequestConfig } from './client';

// ============================================================
// 【小新重构2026-03-09】ReAct任务控制API
// ============================================================

interface TaskControlResponse {
  success: boolean;
  message: string;
}

interface ConfirmRequest {
  confirm_id: string;
  confirmed: boolean;
  trust_session?: boolean;
}

export const taskControlApi = {
  cancel: async (
    taskId: string,
    sessionId?: string
  ): Promise<TaskControlResponse> => {
    const url = sessionId
      ? `/chat/stream/cancel/${taskId}?session_id=${sessionId}`
      : `/chat/stream/cancel/${taskId}`;
    const response = await api.post<TaskControlResponse>(url);
    return response.data;
  },

  pause: async (
    taskId: string,
    sessionId?: string
  ): Promise<TaskControlResponse> => {
    const url = sessionId
      ? `/chat/stream/pause/${taskId}?session_id=${sessionId}`
      : `/chat/stream/pause/${taskId}`;
    const response = await api.post<TaskControlResponse>(url);
    return response.data;
  },

  resume: async (
    taskId: string,
    sessionId?: string
  ): Promise<TaskControlResponse> => {
    const url = sessionId
      ? `/chat/stream/resume/${taskId}?session_id=${sessionId}`
      : `/chat/stream/resume/${taskId}`;
    const response = await api.post<TaskControlResponse>(url);
    return response.data;
  },

  confirm: async (
    confirmId: string,
    confirmed: boolean,
    trustSession?: boolean
  ): Promise<TaskControlResponse> => {
    const body: ConfirmRequest = {
      confirm_id: confirmId,
      confirmed: confirmed,
    };
    if (trustSession !== undefined) {
      body.trust_session = trustSession;
    }
    const response = await api.post<TaskControlResponse>(
      '/chat/stream/confirm',
      body
    );
    return response.data;
  },
};

// ============================================================
// 【小欧 2026-08-26 8.2/8.5/8.7/8.C】任务清单/任务详情/执行步骤/信任
// ============================================================

/**
 * 引用台账 wire 条目(读写共用一种形状) — 小欧 2026-11-18
 *
 * 读侧: SessionTaskItem.ref_ledger(后端 chat_tasks.ref_ledger_json 快照);
 * 写侧: saveTaskProcessEvents 第3参(前端 final 帧上交)。
 * UI 台账条目(SentRefLedgerEntry)另带 taskId, 是本形状 + 归属任务的投影。
 */
export interface RefLedgerWireEntry {
  label: string;
  /** 可点开的相对 posix 路径; 缺 path 的条目在入台账/落库前即被丢弃, 故写侧必有值 */
  path: string;
  lineRange?: { start: number; end: number };
  /** 2026-11-18 opencode - 种类随快照落库: 冷启动后 url 条目仍按外链打开而非文件重读 */
  kind?: 'file' | 'selection' | 'attachment' | 'url';
  ts: number;
}

export interface SessionTaskItem {
  task_id: string;
  user_input: string;
  /** 2026-11-14 商量: 契约升级 {content,msg_kind}[] — 同槽异标; 禁 backward 双读 */
  merged_inputs?: { content: string; msg_kind: string }[];
  response?: string;
  status: string;
  duration: number | null;
  model: string | null;
  provider: string | null;
  total_steps: number;
  llm_call_count: number;
  created_at: string;
  updated_at: string;
  context_link_mode?: 'linked' | 'independent';
  // 本任务所属对话组根任务ID(后端已返回)。TaskListPanel 组号徽标的唯一分组键(落库恒非空)。
  context_root_task_id?: string;
  // 任务创建来源(后端 chat_tasks.creation_source): user=用户, system_resume=后台命令完成续跑 — 商量-2026-11-13
  creation_source?: 'user' | 'system_resume' | 'system_triggered';
  /** [46b] P2b 小欧 2026-11-17: 本任务引用台账快照(后端持久化, 冷启动不缺失; 上线前存量为 []) */
  ref_ledger?: RefLedgerWireEntry[];
  /** [46b] P2b 小欧 2026-11-17: 本任务工具触达的相对 posix 路径(去重, 推荐行 roundHits 依据) */
  tool_paths?: string[];
}

export interface SessionTasksResponse {
  tasks: SessionTaskItem[];
  total: number;
  // 2026-08-30 小欧 设计文档 v1.103: 最新任务显式锚点(排序一义后顶栏/默认选中/链token锚点统一消费)
  latest_task_id: string | null;
}

export interface TaskArtifact {
  name: string;
  path: string;
  type: string;
  tool_name: string;
}

export interface TaskDetail {
  task_id: string;
  session_id: string;
  status: string;
  duration: number | null;
  total_steps: number;
  llm_call_count: number;
  retry_count: number;
  error_type: string | null;
  error_message: string | null;
  accumulated_usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  } | null;
  task_accumulated_tokens: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  } | null;
  artifacts: TaskArtifact[] | null;
  tool_stats: Record<string, number>;
  provider: string | null;
  model: string | null;
  created_at: string | null;
  updated_at: string | null;
  // 2026-10-10 小欧: 首帧 history_context(历史任务回显历史上下文用, 后端详情接口直给)
  //   类型复用 ContextOverviewFrame(单一真源), 禁在本文件手写窄类型副本(禁 backward)
  history_context_first?: import('@/types/sse').ContextOverviewFrame | null;
  // 2026-10-11 小欧 北京老陈令「final 的时候回填事件列表」: 事件列表快照条目本体
  //   {kind, text, time}。类型复用 useTaskInfo 的 ProcessEvent(单一真源, 禁手写副本);
  //   用内联 import() 避免 api→hooks 反向依赖(同 history_context_first 写法)。
  process_events?:
    | import('@/features/chat/hooks/useTaskInfo').ProcessEvent[]
    | null;
}

export function adaptTaskDetail(raw: {
  task: Record<string, unknown>;
  tool_stats: Array<{ tool_name: string; call_count: number }>;
}): TaskDetail {
  const t = raw.task ?? {};
  let usage: TaskDetail['accumulated_usage'] = null;
  if (typeof t.accumulated_usage === 'string' && t.accumulated_usage) {
    try {
      usage = JSON.parse(t.accumulated_usage);
    } catch {
      usage = null;
    }
  } else if (t.accumulated_usage && typeof t.accumulated_usage === 'object') {
    usage = t.accumulated_usage as TaskDetail['accumulated_usage'];
  }
  // 小欧 2026-08-30: accumulated_usage为null时回退读task_accumulated_tokens(每轮即时落库,更可靠)
  let taskAcc: TaskDetail['task_accumulated_tokens'] = null;
  if (
    typeof t.task_accumulated_tokens === 'string' &&
    t.task_accumulated_tokens
  ) {
    try {
      taskAcc = JSON.parse(t.task_accumulated_tokens);
    } catch {
      taskAcc = null;
    }
  } else if (
    t.task_accumulated_tokens &&
    typeof t.task_accumulated_tokens === 'object'
  ) {
    taskAcc =
      t.task_accumulated_tokens as TaskDetail['task_accumulated_tokens'];
  }
  if (!usage && taskAcc) usage = taskAcc;
  const toolStats: Record<string, number> = {};
  for (const it of raw.tool_stats ?? []) {
    if (it.tool_name && it.tool_name !== 'null')
      toolStats[it.tool_name] = it.call_count;
  }
  return {
    task_id: String(t.task_id ?? ''),
    session_id: String(t.session_id ?? ''),
    status: String(t.status ?? ''),
    duration: (t.duration as number | null) ?? null,
    total_steps: Number(t.total_steps ?? 0),
    llm_call_count: Number(t.llm_call_count ?? 0),
    retry_count: Number(t.retry_count ?? 0),
    error_type: (t.error_type as string | null) ?? null,
    error_message: (t.error_message as string | null) ?? null,
    accumulated_usage: usage,
    task_accumulated_tokens: taskAcc,
    artifacts: (t.artifacts as TaskArtifact[] | null) ?? null,
    tool_stats: toolStats,
    provider: (t.provider as string | null) ?? null,
    model: (t.model as string | null) ?? null,
    created_at: (t.created_at as string | null) ?? null,
    updated_at: (t.updated_at as string | null) ?? null,
    // 2026-10-10 小欧: 后端直给, 无则 null(无首帧走空, 卡片如实显示空)
    history_context_first:
      (t.history_context_first as TaskDetail['history_context_first']) ?? null,
    // 2026-10-11 小欧 北京老陈令: 事件列表快照(final 时前端回填, 存条目本体{kind,text,time})。
    //   存量行为 null, 前端兜底空数组后与改动前一致 — 小欧-2026-10-11
    process_events: Array.isArray(t.process_events)
      ? (t.process_events as TaskDetail['process_events'])
      : null,
  };
}

export const sessionTaskApi = {
  // 2026-10-30 小欧 - 补第三类: 「无用户动作的后台轮询」不该弹"请重试"。
  //   本端点是唯一后台轮询入口(observeByPolling 每 5s / useSessionTasks.refresh / findLiveTask),
  //   超时属"后端忙"的瞬时表现, 下次触发自愈; 弹窗只会让用户以为系统出故障。
  //   静默 ≠ 无痕迹: client.ts 的 [SlowReq] 与 logIfSlow 照旧打 URL+耗时, 取证不丢。
  listTasks: (sessionId: string): Promise<SessionTasksResponse> => {
    // 2026-11-18 小欧 - 并发取同一会话任务列表只发一次 — 小欧-2026-11-18
    return dedupeGet(`tasks:${sessionId}`, () => {
      const cfg: ApiRequestConfig = { _silent: true };
      return api.get(`/sessions/${sessionId}/tasks`, cfg).then((r) => r.data);
    });
  },
};

export const executionApi = {
  getTaskDetail: async (taskId: string): Promise<TaskDetail> => {
    // 2026-11-18 小欧 - 首屏两个面板同刻各取一次同一任务详情, 合并同时在飞的请求(轮询另发新请求) — 小欧-2026-11-18
    const data = await dedupeGet(
      `task:${taskId}`,
      async () => (await api.get(`/chat/execution/task/${taskId}`)).data
    );
    return adaptTaskDetail(data);
  },
  getTaskSteps: (
    taskId: string
  ): Promise<{ task_id: string; steps: unknown[]; count: number }> =>
    api.get(`/chat/execution/task/${taskId}/steps`).then((r) => r.data),
  // 2026-10-11 小欧 北京老陈令「final 的时候回填事件列表」: 回填事件列表快照。
  //   数据源是 useTaskInfo 产出的 processEvents(浮层显示的那份), 排除 heartbeat 已在调用方 filter 完成,
  //   本方法**不做条数限制**(后端仅留 10000 兜底防灌爆)。失败只 reject 不抛给调用方业务链路。
  saveTaskProcessEvents: (
    taskId: string,
    events: import('@/features/chat/hooks/useTaskInfo').ProcessEvent[],
    // [46b] P2b 小欧 2026-11-17: 收尾捎带台账快照(可选第3参, feature 层调用点取好后传入,
    //   service 层不依赖 feature store); 缺省不携带, 后端不覆盖台账列
    // 2026-11-18 小欧 会审整改: 改用 RefLedgerWireEntry(与读侧 ref_ledger 同一种形状, 原 path 可选
    //   与读侧必有值自相矛盾); 调用方传空数组等价于不携带
    refLedger?: RefLedgerWireEntry[]
  ): Promise<{ success: boolean; count: number }> =>
    api
      .post(`/chat/execution/task/${taskId}/process-events`, {
        events,
        ...(refLedger?.length ? { ref_ledger: refLedger } : {}),
      })
      .then((r) => r.data),
};

export interface TrustedTool {
  toolName: string;
  path: string | null;
}

export const trustApi = {
  getTrust: async (sessionId: string): Promise<TrustedTool[]> => {
    // 2026-11-18 小欧 - 信任清单只随授权/撤销变化(均为写请求), 走共享读; 只取正文(整份
    //   AxiosResponse 含函数, 深拷贝会抛 DataCloneError) — 小欧-2026-11-18
    const r = await sharedGet(
      `trust:${sessionId}`,
      async () => (await api.get(`/sessions/${sessionId}/trust`)).data
    );
    return (r.data?.trusted_tools ?? []).map(
      (t: { tool_name: string; path: string | null }) => ({
        toolName: t.tool_name,
        path: t.path ?? null,
      })
    );
  },
  revokeTrust: (
    sessionId: string,
    toolName: string,
    path?: string | null
  ): Promise<void> =>
    api
      .delete(
        `/sessions/${sessionId}/trust/${encodeURIComponent(toolName)}${
          path ? `?path=${encodeURIComponent(path)}` : ''
        }`
      )
      .then(() => undefined),
};

export interface ChainTokenLayer {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface ChainTokenResponse {
  success: boolean;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  task_accumulated_tokens: ChainTokenLayer | null;
  session_accumulated_tokens: ChainTokenLayer | null;
  chain_accumulated_tokens: ChainTokenLayer | null;
}

export const tokenUsageApi = {
  getChainTokens: async (params: {
    sessionId: string;
    taskId?: string;
  }): Promise<ChainTokenResponse> => {
    const q: string[] = [`session_id=${encodeURIComponent(params.sessionId)}`];
    if (params.taskId) q.push(`task_id=${encodeURIComponent(params.taskId)}`);
    const response = await api.get<ChainTokenResponse>(
      `/token-usage?${q.join('&')}`
    );
    return response.data;
  },
};
