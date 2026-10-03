// 编辑历史: 2026-10-01 小欧 - 解 [1] E4/E2-1（见 doc-10月优化/[1]刷新后显示其他任务结果）：
//   ①ApiMessage 增可选 task_id（后端 MessageResponse 配对任务ID）——此前消息只带 execution_steps 而无归属，
//     消费方无法判断步骤属于哪个任务，这是前端"跨任务降级把别的任务步骤当本任务显示"的契约层根因；
//   ②删 saveExecutionSteps（随 [1] E8 后端 execution_steps 端点与空壳退役，前端零调用方）— 小欧-2026-10-01
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.2: GetSessionMessagesResponse 补 link_enabled(会话 link 开关真源
//   随会话加载主路径下发, 前端唯一读取点); getSessionMessages 映射处补值(缺省 false)。不新增 setSessionLink
//   ——值随消息落库, PATCH 端点前端零调用方, 按 YAGNI 不引入 — 小欧-2026-10-03
import api from './client';
import type { ExecutionStep } from '@/types/execution';
import type { SessionModelOverride } from '@/types/chat';

export interface Session {
  session_id: string;
  title: string;
  title_locked: boolean;
  title_source: 'user' | 'auto';
  title_updated_at: string | null;
  version?: number;
  created_at: string;
  updated_at: string;
  message_count: number;
  is_valid: boolean;
}

export interface SessionListResponse {
  total: number;
  page: number;
  page_size: number;
  sessions: Session[];
}

export interface ApiMessage {
  id: number;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  execution_steps?: ExecutionStep[];
  display_name?: string;
  is_reasoning?: boolean;
  thought?: string;
  // 2026-10-01 小欧 解 [1] E4/E2-1: 后端 MessageResponse 新增该字段(配对任务ID)。
  //   此前消息只带 execution_steps 而无归属, 消费方无法判断步骤属于哪个任务 ——
  //   这是前端"跨任务降级把别的任务步骤当本任务显示"(RightViewer C3)的契约层根因。
  task_id?: string | null;
}

export interface GetSessionMessagesResponse {
  session_id: string;
  title: string;
  title_locked: boolean;
  title_source: 'user' | 'auto';
  title_updated_at: string | null;
  version?: number;
  sessionModel?: SessionModelOverride | null;
  link_enabled: boolean; // 会话 link 开关真源, 随会话加载主路径下发(唯一读取点)
  messages: ApiMessage[];
}

export interface UpdateSessionRequest {
  title: string;
  version: number;
  updated_by?: string;
}

export interface UpdateSessionResponse {
  success: boolean;
  title: string;
  version?: number;
  title_locked?: boolean;
  title_updated_at?: string;
  sessionModel?: SessionModelOverride | null;
}

export interface BatchTitleResponse {
  sessions: Array<{
    session_id: string;
    title: string;
    title_locked: boolean;
    title_updated_at: string | null;
    version?: number;
  }>;
}

export const sessionApi = {
  createSession: async (
    title?: string
  ): Promise<{
    session_id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
  }> => {
    const response = await api.post<{
      session_id: string;
      title: string;
      created_at: string;
      updated_at: string;
      message_count: number;
    }>('/sessions', { title, is_valid: true });
    return response.data;
  },

  listSessions: async (
    page: number = 1,
    pageSize: number = 20,
    keyword?: string,
    isValid?: boolean
  ): Promise<SessionListResponse> => {
    const params: Record<string, unknown> = { page, page_size: pageSize };
    if (keyword) params.keyword = keyword;
    if (isValid === true || isValid === false) params.is_valid = isValid;
    const response = await api.get<SessionListResponse>('/sessions', {
      params,
    });
    return {
      ...response.data,
      sessions: (response.data.sessions ?? []).map((s) => ({
        ...s,
        title_locked: s.title_locked ?? false,
        title_source: s.title_source ?? 'auto',
        title_updated_at: s.title_updated_at ?? null,
        version: s.version ?? 1,
      })),
    };
  },

  getSessionMessages: async (
    sessionId: string
  ): Promise<GetSessionMessagesResponse> => {
    const response = await api.get<GetSessionMessagesResponse>(
      `/sessions/${sessionId}/messages`
    );
    return {
      ...response.data,
      title_locked: response.data.title_locked ?? false,
      title_source: response.data.title_source ?? 'auto',
      title_updated_at: response.data.title_updated_at ?? null,
      version: response.data.version ?? 1,
      link_enabled: response.data.link_enabled ?? false, // 缺省 false(fail-closed)
      messages: (response.data.messages ?? []).map((m) => ({
        ...m,
        thought:
          m.thought ??
          (typeof m.is_reasoning === 'string' ? m.is_reasoning : undefined),
        is_reasoning: m.is_reasoning ?? (m.thought != null && m.thought !== ''),
      })),
    };
  },

  saveMessage: async (
    sessionId: string,
    message: {
      role: string;
      content: string;
      execution_steps?: unknown[];
      is_error?: boolean;
      error_type?: string;
      code?: string;
      message?: string;
      details?: string;
      stack?: string;
      retryable?: boolean;
      retry_after?: number;
      timestamp?: string;
      model?: string;
      provider?: string;
      display_name?: string;
      client_os?: string;
      browser?: string;
      device?: string;
      network?: string;
    }
  ): Promise<{
    success: boolean;
    message_id?: number;
    message_count?: number;
  }> => {
    const response = await api.post<{
      success: boolean;
      message_id?: number;
      message_count?: number;
    }>(`/sessions/${sessionId}/messages`, message);
    return response.data;
  },

  // 2026-10-01 小欧 解 [1] E8: 原 saveExecutionSteps 删除 ——
  //   全仓零调用, 且后端端点已下线(其实现自 2026-08-27 起不写任何步骤, 只分配 ai_message_id)。
  //   留着会 POST 到已不存在的端点。步骤数据一律由 SSE 实时 + 运行期逐步落库产生。

  deleteSession: async (sessionId: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(
      `/sessions/${sessionId}`
    );
    return response.data;
  },

  updateSession: async (
    sessionId: string,
    title: string,
    version: number,
    sessionModel?: SessionModelOverride | null
  ): Promise<UpdateSessionResponse> => {
    const body: Record<string, unknown> = {
      title,
      version,
      updated_by: 'user',
    };
    if (sessionModel !== undefined) {
      body.sessionModel = sessionModel;
    }
    const response = await api.put<UpdateSessionResponse>(
      `/sessions/${sessionId}`,
      body
    );
    return response.data;
  },

  getSession: async (sessionId: string): Promise<Session> => {
    const r = await api.get<Session>(`/sessions/${sessionId}`);
    const d = r.data;
    return {
      ...d,
      title_locked: d.title_locked ?? false,
      title_source: d.title_source ?? 'auto',
      title_updated_at: d.title_updated_at ?? null,
      version: d.version ?? 1,
    };
  },

  getSessionTitlesBatch: async (
    sessionIds: string[]
  ): Promise<BatchTitleResponse> => {
    if (!sessionIds || sessionIds.length === 0) {
      throw new Error('会话ID列表不能为空');
    }
    if (sessionIds.length > 50) {
      throw new Error('批量获取标题最多支持50个会话ID');
    }
    const validIds = sessionIds.filter((id) => id && id.trim());
    if (validIds.length === 0) {
      throw new Error('没有有效的会话ID');
    }
    const url = `/sessions/titles/batch?session_ids=${validIds.map(encodeURIComponent).join(',')}`;
    if (url.length > 2000) {
      throw new Error('请求URL过长，请减少会话数量');
    }
    const response = await api.get<BatchTitleResponse>(url);
    return response.data;
  },
};
