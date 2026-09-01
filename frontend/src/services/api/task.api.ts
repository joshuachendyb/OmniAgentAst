// 编辑历史: 2026-08-30 小欧 - adaptTaskDetail修复: ①accumulated_usage为null时回退读task_accumulated_tokens(每轮即时落库更可靠); ②tool_stats过滤tool_name为null的条目; TaskDetail新增task_accumulated_tokens字段
// 编辑历史: 2026-09-01 小欧 - 任务统计增强v0.8: TaskArtifact补tool_name(4字段对齐artifacts)、TaskDetail补provider/model/created_at/updated_at、adaptTaskDetail透传四字段 - 小欧-2026-09-01
import api from './client';

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

export interface SessionTaskItem {
  task_id: string;
  user_input: string;
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
}

export interface SessionTasksResponse {
  tasks: SessionTaskItem[];
  total: number;
  // 2026-08-30 小欧 设计文档[2]12.6 v1.103: B1 最新任务显式锚点(排序一义后顶栏/默认选中/链token锚点统一消费)
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
  };
}

export const sessionTaskApi = {
  listTasks: (sessionId: string): Promise<SessionTasksResponse> =>
    api.get(`/sessions/${sessionId}/tasks`).then((r) => r.data),
};

export const executionApi = {
  getTaskDetail: async (taskId: string): Promise<TaskDetail> => {
    const r = await api.get(`/chat/execution/task/${taskId}`);
    return adaptTaskDetail(r.data);
  },
  getTaskSteps: (
    taskId: string
  ): Promise<{ task_id: string; steps: unknown[]; count: number }> =>
    api.get(`/chat/execution/task/${taskId}/steps`).then((r) => r.data),
};

export const trustApi = {
  getTrust: async (sessionId: string): Promise<string[]> => {
    const r = await api.get(`/sessions/${sessionId}/trust`);
    return ((r.data?.trusted_tools ?? []) as Array<{ tool_name: string }>).map(
      (x) => x.tool_name
    );
  },
  revokeTrust: (sessionId: string, toolName: string): Promise<void> =>
    api
      .delete(`/sessions/${sessionId}/trust/${encodeURIComponent(toolName)}`)
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
