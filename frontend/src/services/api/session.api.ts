// 编辑历史: 2026-10-01 小欧 - ApiMessage 增可选 task_id(后端 MessageResponse 配对任务ID): 此前消息只带
//   execution_steps 无归属, 消费方无法判断步骤属于哪个任务(跨任务混显的契约层根因); 同时删 saveExecutionSteps
// 编辑历史: 2026-10-03 小欧 - GetSessionMessagesResponse 补 link_enabled(会话 link 开关真源, 随会话加载下发);
//   getSessionMessages 映射处补值(缺省 false); 不新增 setSessionLink(值随消息落库, 按 YAGNI 不引入) — 小欧-2026-10-03
// 编辑历史: 2026-10-08 小欧 - saveMessage 入参加 allow_interject(开关随消息携带)
// 编辑历史: 2026-10-10 小欧 - 新增 getWorkspaces(读会话目录, 含 project_root/allowed_dirs 只读字段)
//   + patchWorkspaces(全量覆盖写, [] = 清空)
// 编辑历史: 2026-10-24 小欧 - SRP拆分: updateSession拆为updateSessionTitle(只改标题)+updateSessionModel(只改模型), 消除"改标题"与"切模型"耦合(长标题触发422根因) - 小欧-2026-10-24

// 编辑历史: 2026-10-30 小欧 - 全链路重构: patchWorkspaces 入参改对象数组
//   ({path, workspace_property, memo}[]), 不再收 string[]; GET 响应含四字段。 — 小欧-2026-10-30

// 编辑历史: 2026-11-02 小欧 - getWorkspaces 增可选 prune(默认纯读): 仅面板打开时清不可用行,
//   浏览类调用(历史页/文件页)零副作用 — 小欧-2026-11-02
// 编辑历史: 2026-11-03 小欧 - 新增 listRunningTasks(跨会话在跑任务) + getTaskStatus(单任务轻量读),
//   为历史页角标/顶栏浮层/退订后 60s 复核提供后端权威来源 — 小欧-2026-11-03
// 编辑历史: 2026-11-16 小欧 - [23]阶段D: Session 增 routingMode; 新增 updateSessionRoutingMode(会话级路由模式唯一写口) — 小欧-2026-11-16

// 编辑历史: 2026-11-16 小欧 - 修正: getSession 现已取后端真实 version(不再恒兜底 1); routingMode 复用 RoutingMode

// 编辑历史: 2026-11-13 商量 - ApiMessage 补 msg_kind(后端 MessageResponse 新增可选字段, user/system_notice):
//   后台续跑通知消息的种类在 wire 上保真, 前端按它渲染系统通知样式, 不再与用户发言混同

// 编辑历史: 2026-11-16 小欧 bug猎修: createSession 响应补 version(此前类型未声明且调用侧写死 1),
//   与其余会话响应统一归一 version ?? 1, 消除版本号双真源
// 编辑历史: 2026-11-18 小欧 - [46] P0 首屏提速: getSessionMessages 增可选 opts{limit,offset}, 响应补
//   total/has_more(pairs 口径); 缺省不带参数仍走后端全量, 兼容 RightViewer 等直接调用方 — 小欧-2026-11-18
// 编辑历史: 2026-11-18 小欧 - [46] P1 首屏裁剪: opts 增 include_steps(默认 false 不下发 execution_steps);
//   RightViewer 的 messages 兜底显式传 true 拉步骤, 右栏详情不受裁剪影响 — 小欧-2026-11-18
// 编辑历史: 2026-11-18 小欧 - 历史页批量清理: 新增 preview/execute 会话清理接口与类型
//   (mode=invalid|older, days 默认30) — 小欧-2026-11-18
// 编辑历史: 2026-11-18 小欧 - [46/46b] 会审整改: ①getSessionMessages 三个开关统一按"是否显式给出"
//   判空(原 include_steps 取真值 → 首屏 false 被丢掉, 后端缺省 true, 裁剪形同虚设); ②total 兜底
//   ?? 0(不再用本页条数冒充总条数, 否则 has_more 算错); ③SessionCleanupPreview.session_ids 注明
//   预览恒为 [] — 小欧-2026-11-18
// 编辑历史: 2026-11-18 小欧 - getSession/getSessionMessages 改走 dedupeGet: 首屏布局/历史/右栏多处并发
//   取同一会话与同一页消息(实测 /sessions/{id} 4 次、/messages 2 次); key 含全部入参以免串数据 — 小欧-2026-11-18

import api, { dedupeGet } from './client';
import type { ExecutionStep } from '@/types/execution';
import type { SessionModelOverride, WorkspacesResponse, RoutingMode } from '@/types/chat';

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
  sessionModel?: SessionModelOverride | null;
  /** 2026-11-16 小欧 阶段D: 会话级能力路由模式(后端缺省归一 suggest) */
  routingMode?: RoutingMode;
}

export interface SessionListResponse {
  total: number;
  page: number;
  page_size: number;
  sessions: Session[];
}

/** 跨会话在跑任务的一行(后端 chat_tasks 权威口径) — 小欧-2026-11-03
 *  status 是 DB 词表(executing/paused/completed...), 消费前必须经 chatStreamStore.toStreamStatus 归一。 */
export interface RunningTask {
  task_id: string;
  session_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface RunningTasksResponse {
  total: number;
  tasks: RunningTask[];
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
  // 2026-10-01 小欧 - 后端 MessageResponse 新增该字段(配对任务ID): 此前消息只带 execution_steps 无归属,
  //   跨任务降级会把别的任务步骤当本任务显示 — 小欧-2026-10-01
  task_id?: string | null;
  // 2026-11-13 商量 - 消息种类(user/system_notice): 后台续跑通知按它渲染系统通知样式
  msg_kind?: string | null;
}

/** [历史页清理] invalid=无效/空壳会话, older=N 天前未活动的会话 */
export type SessionCleanupMode = 'invalid' | 'older';

/** [历史页清理] 预览结果(只统计不写库) */
export interface SessionCleanupPreview {
  mode: SessionCleanupMode;
  days: number;
  cutoff: string | null;
  count: number;
  skipped_active: number;
  sample_titles: string[];
  /** 预览恒为 []（只预览不删, 不可据此清前端 Store）；执行结果看 SessionCleanupResult */
  session_ids: string[];
  deleted: number;
}

/** [历史页清理] 执行结果 */
export interface SessionCleanupResult {
  mode: SessionCleanupMode;
  days: number;
  count: number;
  deleted: number;
  skipped_active: number;
  session_ids: string[];
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
  allow_interject: boolean; // 2026-10-06 小欧 - 文档[11] 3.4.6: 插话开关真源(同 link_enabled, 唯一读取点)
  /** [46] P0 消息历史分页: 总条数(消息对口径, 不等于渲染气泡数) */
  total?: number;
  /** [46] P0 是否还有更早的可加载(供"加载更早"显隐) */
  has_more?: boolean;
  messages: ApiMessage[];
}

export interface UpdateSessionRequest {
  title: string;
  version: number;
  updated_by?: string;
}

export interface UpdateSessionResponse {
  success: boolean;
  title?: string | null;
  version?: number;
  title_locked?: boolean;
  title_updated_at?: string;
  sessionModel?: SessionModelOverride | null;
  /** 2026-11-16 小欧 阶段D: 会话级路由模式(写回值; 后端仅回 success+version, 其余字段可选) */
  routingMode?: RoutingMode | null;
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

/** 会话任务产出物条目(「本会话产物」行) — 后端 chat_tasks.artifacts 真源 */
export interface SessionArtifactItem {
  task_id: string;
  task_created_at: string;
  name: string;
  path: string;
  /** 项目根相对 posix 路径(根内有值, 可直接作文件引用上行; 根外为 null) */
  rel_path: string | null;
  type: string;
  tool_name: string;
  /** 产物文件是否还在（失效行仍可见，不可加入本轮） */
  exists: boolean;
}

export interface SessionArtifactsResponse {
  session_id: string;
  total: number;
  artifacts: SessionArtifactItem[];
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
    version?: number;
  }> => {
    const response = await api.post<{
      session_id: string;
      title: string;
      created_at: string;
      updated_at: string;
      message_count: number;
      version?: number;
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
    sessionId: string,
    opts?: { limit?: number; offset?: number; include_steps?: boolean }
  ): Promise<GetSessionMessagesResponse> => {
    // [46] P0/P1: 仅首屏路径(loadHistoryMessages)传分页 opts; 右栏详情兜底显式 include_steps=true;
    //   RightViewer/切模型等其它直接调用仍不带参数=后端全量(兼容)
    // 2026-11-18 - 小欧 - 会审整改: 三开关统一按"是否显式给出"判空(原 include_steps 取真值 →
    //   首屏的 false 被丢掉, 后端缺省 True, 首屏裁剪形同虚设) — 小欧-2026-11-18
    const params =
      opts &&
      (opts.limit != null || opts.offset != null || opts.include_steps != null)
        ? {
            ...(opts.limit != null ? { limit: opts.limit } : {}),
            ...(opts.offset != null ? { offset: opts.offset } : {}),
            ...(opts.include_steps != null
              ? { include_steps: opts.include_steps }
              : {}),
          }
        : undefined;
    const data = await dedupeGet(
      `messages:${sessionId}:${params?.limit ?? ''}:${params?.offset ?? ''}:${
        params?.include_steps ?? ''
      }`,
      // 2026-11-18 小欧 - 只取正文: 整份 AxiosResponse 含函数, 合并方深拷贝会抛 DataCloneError — 小欧-2026-11-18
      async () =>
        (
          await api.get<GetSessionMessagesResponse>(
            `/sessions/${sessionId}/messages`,
            { params }
          )
        ).data
    );
    return {
      ...data,
      title_locked: data.title_locked ?? false,
      title_source: data.title_source ?? 'auto',
      title_updated_at: data.title_updated_at ?? null,
      version: data.version ?? 1,
      link_enabled: data.link_enabled ?? false, // 缺省 false(fail-closed)
      allow_interject: data.allow_interject ?? false, // 2026-10-07 小欧 - 文档[11] 3.4.6: 缺省 false(fail-closed)。注意本对象是 GetSessionMessagesResponse(蛇形), 驼峰 AllowInterject 的变换在下游 chatHistory/useChatSession 做, 与 link_enabled 同款。
      // 2026-11-18 小欧 会审整改: 后端恒下发 total; 不用本页条数冒充总量(否则 has_more 算错)
      total: data.total ?? 0,
      has_more: data.has_more ?? false,
      messages: (data.messages ?? []).map((m) => ({
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
      allow_interject?: boolean; // 2026-10-08 小欧 - 文档[11] 3.4.5.2: 开关随消息携带, 不带则 None=沿用会话值
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

  // 2026-10-01 小欧 - 原 saveExecutionSteps 删除: 全仓零调用, 后端端点已下线(实现自 2026-08-27 起
  //   不写任何步骤); 留着会 POST 到不存在的端点, 步骤一律由 SSE 实时 + 运行期逐步落库 — 小欧-2026-10-01

  deleteSession: async (sessionId: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(
      `/sessions/${sessionId}`
    );
    return response.data;
  },

  /** [历史页清理] 预览命中数与样例, 不写库 */
  previewCleanupSessions: async (
    mode: SessionCleanupMode,
    days: number = 30
  ): Promise<SessionCleanupPreview> => {
    const response = await api.post<SessionCleanupPreview>(
      '/sessions/cleanup/preview',
      { mode, days }
    );
    return response.data;
  },

  /** [历史页清理] 执行批量软删除, 返回被删 ID 供前端清 Store */
  cleanupSessions: async (
    mode: SessionCleanupMode,
    days: number = 30
  ): Promise<SessionCleanupResult> => {
    const response = await api.post<SessionCleanupResult>(
      '/sessions/cleanup',
      { mode, days }
    );
    return response.data;
  },

  // 编辑历史: 2026-10-24 小欧 - SRP拆分: 原 updateSession 把"改标题"与"切会话模型"耦合在一个函数,
  //   title 必传致 ModelPicker 被迫传标题, 长标题触发后端 422; 拆为 updateSessionTitle + updateSessionModel
  updateSessionTitle: async (
    sessionId: string,
    title: string,
    version: number
  ): Promise<UpdateSessionResponse> => {
    const body: Record<string, unknown> = {
      title,
      version,
      updated_by: 'user',
    };
    const response = await api.put<UpdateSessionResponse>(
      `/sessions/${sessionId}`,
      body
    );
    return response.data;
  },

  updateSessionModel: async (
    sessionId: string,
    sessionModel: SessionModelOverride | null,
    version: number
  ): Promise<UpdateSessionResponse> => {
    const body: Record<string, unknown> = {
      version,
      updated_by: 'user',
      sessionModel,
    };
    const response = await api.put<UpdateSessionResponse>(
      `/sessions/${sessionId}`,
      body
    );
    return response.data;
  },

  /**
   * 2026-11-16 小欧 [23]阶段D: 会话级路由模式唯一写口(suggest/auto/strict)。
   * 与 updateSessionModel 同端点同乐观锁, 只发 routingMode+version — 小欧-2026-11-16
   */
  updateSessionRoutingMode: async (
    sessionId: string,
    routingMode: 'suggest' | 'auto' | 'strict',
    version: number
  ): Promise<UpdateSessionResponse> => {
    const body: Record<string, unknown> = {
      version,
      updated_by: 'user',
      routingMode,
    };
    const response = await api.put<UpdateSessionResponse>(
      `/sessions/${sessionId}`,
      body
    );
    return response.data;
  },

  getSession: async (sessionId: string): Promise<Session> => {
    // 2026-11-18 小欧 - 并发取同一会话只发一次; 只取正文(整份 AxiosResponse 含函数, 深拷贝会抛) — 小欧-2026-11-18
    const d = await dedupeGet(`session:${sessionId}`, async () =>
      (await api.get<Session>(`/sessions/${sessionId}`)).data
    );
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

  // 2026-11-03 小欧 - 跨会话在跑任务(历史页角标/顶栏浮层的后端权威来源): 只读、一条 SQL。
  //   调用方只在挂载/窗口聚焦/列表重载时各调一次, 不做轮询 — 小欧-2026-11-03
  listRunningTasks: async (): Promise<RunningTasksResponse> => {
    const response = await api.get<RunningTasksResponse>(
      '/sessions/tasks/running'
    );
    return response.data;
  },

  // 2026-11-03 小欧 - 单任务状态轻量读口(前端退订后每 60s 后台复核专用): 只读单行,
  //   替代拉整会话任务正文的 /sessions/{id}/tasks; task 为 null 表示该任务行不存在(=已结束, 常态非异常)
  getTaskStatus: async (taskId: string): Promise<RunningTask | null> => {
    const response = await api.get<{ task: RunningTask | null }>(
      `/sessions/tasks/${encodeURIComponent(taskId)}`
    );
    return response.data.task;
  },

  // 2026-11-13 小欧 - 会话任务产出物清单(「本会话产物」唯一真源): 读 chat_tasks.artifacts,
  //   跨任务按任务时间倒序; 产出物是任务产物, 不是附件台账行(工作区内产物走引用模式不落库)
  listSessionArtifacts: async (
    sessionId: string
  ): Promise<SessionArtifactsResponse> => {
    const response = await api.get<SessionArtifactsResponse>(
      `/sessions/${encodeURIComponent(sessionId)}/artifacts`
    );
    return response.data;
  },

  // 2026-11-02 小欧 - 会话目录读口: prune=true 才清库(面板主动请求), 默认纯读零副作用;
  //   响应含 project_root/allowed_dirs 只读字段, 只展示永不进 PATCH
  getWorkspaces: async (
    sessionId: string,
    prune?: boolean
  ): Promise<WorkspacesResponse> => {
    if (!sessionId || !sessionId.trim()) {
      throw new Error('会话ID不能为空');
    }
    const response = await api.get<WorkspacesResponse>(
      `/sessions/${encodeURIComponent(sessionId)}/workspaces`,
      prune ? { params: { prune: true } } : undefined
    );
    return response.data;
  },

  // 2026-10-30 18:36:36 小欧 - 会话目录写口: body 即全量覆盖写([] = 清空), 命中禁区整单 422
  //   (detail 落 error.workspace_rejected); 超时收窄 20s(后台提交, 未答由 store 对账拉回库真值) — 小欧-2026-10-30
  patchWorkspaces: async (
    sessionId: string,
    sessionWorkspaces: {
      path: string;
      workspace_property?: string;
      memo?: string | null;
    }[]
  ): Promise<{ success: boolean; session_id: string }> => {
    if (!sessionId || !sessionId.trim()) {
      throw new Error('会话ID不能为空');
    }
    if (!Array.isArray(sessionWorkspaces)) {
      throw new Error('目录列表必须是数组');
    }
    const response = await api.patch<{ success: boolean; session_id: string }>(
      `/sessions/${encodeURIComponent(sessionId)}/workspaces`,
      { session_workspaces: sessionWorkspaces },
      { timeout: 20_000 }
    );
    return response.data;
  },
};
