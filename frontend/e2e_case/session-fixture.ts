/**
 * e2e_case/session-fixture.ts — 会话夹具: 现场发现数据, 不硬编码会话 ID — 小欧 2026-11-18
 *
 * 数据隔离铁律: 用例只认"当前这套库真实存在的数据" —— 会话 ID 与消息条数一律由后端列表接口
 * 现场发现/现场取真值。把某台开发机的会话 ID、条数写死, 换库即红, 更会把"跑过"伪装成"验证过"。
 *
 * 只读: 本文件只发 GET, 不造数据、不改库。
 */
import type { APIRequestContext } from '@playwright/test';

/** 候选会话 + 列表口径消息数(仅用于筛选, 不当断言真值) */
export interface MessageSessionProbe {
  sessionId: string;
  /** 会话列表 message_count: 与 /messages 的 total 不同口径, 只作"有没有消息"的粗筛 */
  messageCount: number;
}

/** /sessions/{id}/messages 的响应子集(用例只关心这几项) */
export interface MessagesBody {
  total?: number;
  has_more?: boolean;
  messages?: Array<{
    execution_steps?: unknown[];
    thought?: string | null;
    role?: string;
  }>;
}

/** 从真实后端列出"有消息"的会话(最多 page_size 个), 按接口默认顺序 */
export async function listMessageSessions(
  request: APIRequestContext,
  pageSize = 100
): Promise<MessageSessionProbe[]> {
  const resp = await request.get(`/api/v1/sessions?page_size=${pageSize}`);
  if (!resp.ok()) return [];
  const body = (await resp.json()) as {
    sessions?: Array<{ session_id: string; message_count?: number }>;
  };
  return (body.sessions ?? [])
    .filter((s) => (s.message_count ?? 0) > 0 && !!s.session_id)
    .map((s) => ({
      sessionId: s.session_id,
      messageCount: s.message_count ?? 0,
    }));
}

/** 读某会话一页消息(query 形如 'limit=10&offset=0&include_steps=true', 省略=后端缺省全量) */
export async function fetchMessages(
  request: APIRequestContext,
  sessionId: string,
  query = ''
): Promise<MessagesBody> {
  const url = `/api/v1/sessions/${sessionId}/messages${query ? `?${query}` : ''}`;
  const resp = await request.get(url);
  if (!resp.ok()) return {};
  return (await resp.json()) as MessagesBody;
}

/** 读某会话的任务列表(取 tasks 长度即该会话任务数) */
export async function countTasks(
  request: APIRequestContext,
  sessionId: string
): Promise<number> {
  const resp = await request.get(`/api/v1/sessions/${sessionId}/tasks`);
  if (!resp.ok()) return 0;
  const body = (await resp.json()) as { tasks?: unknown[] };
  return (body.tasks ?? []).length;
}
