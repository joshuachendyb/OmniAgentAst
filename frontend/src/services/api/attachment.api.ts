// 编辑历史: 2026-11-06 小欧 - 新建: 附件 API(上传/列表/详情/文本/删除/collect/localCapability/importLocal)
//   前端附件功能 — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧: AttachmentRecord 补 source_task_id(溯源, 与后端 _COLS 对齐); get/remove/text
//   增 sessionId 必填(后端会话归属校验, 越会话视同不存在) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: 资产台账 —— 记录补 scope/last_used_at/use_count/available/favorited/global_id;
//   list 改作用域选项(session/recent/global/ai + 分页), 增 promote/rename/clearRecent/loadRawBlob(带 token blob) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: remove 改 _silent(409 由抽屉二次确认, 其余错误调用方就地提示) — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧: loadRawBlob 补 signal 与显式 30s 超时(裸 fetch 挂死时预览抽屉永转 loading);
//   text/raw 注明纯预览严格读口径 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 注释清理: 去除文档号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
// 编辑历史: 2026-11-07 小欧 - scope 注释术语对准: ai 栏 UI 定名「任务产物」 — 小欧-2026-11-07
// 编辑历史: 2026-11-11 小欧 - kind 七类对齐(audio/unknown) + AttachmentCapabilities 类型与 capabilities() 接口 — 小欧-2026-11-11
// 编辑历史: 2026-11-11 小欧 - P5 指标: AttachmentMetrics 类型 + metrics() 只读聚合接口 — 小欧-2026-11-11
/**
 * 附件 API 封装（同 file.api / session.api 范式）
 *
 * 契约真源 = backend/app/api/v1/attachments.py + app/attachments/attachment_service.py
 * - 上传用 multipart/form-data（session_id + file），由 axios 自动带 boundary，**不手写 Content-Type**
 * - 记录里的 path 是「项目根相对 posix 路径」，直接用于 refs 上行
 * - 错误取 error.code（全局 http_exception_handler 包装后的形状），不匹配中文文案
 */
import api, {
  API_BASE_URL,
  getAccessToken,
  HEAVY_READ_TIMEOUT_MS,
} from './client'; // api 只有默认导出（同 file.api）
import type { ApiRequestConfig } from './client';

/** 列表作用域: 本会话 / 最近用过 / 已收藏 / 任务产物(scope=ai) */
export type AttachmentScope = 'session' | 'recent' | 'global' | 'ai';

export interface AttachmentRecord {
  id: string;
  /** 来源会话；全局资产为 null（不再作为访问判定字段） */
  session_id: string | null;
  original_name: string;
  stored_path: string;
  /** 项目根相对 posix 路径（上行 refs 用） */
  path: string;
  mime: string;
  size: number;
  sha256: string;
  // 与后端 extract.classify 七类对齐(audio P3 接入, unknown 为 URL/无后缀兜底) — 小欧-2026-11-11
  kind: 'text' | 'image' | 'video' | 'audio' | 'richdoc' | 'binary' | 'unknown';
  extract_status: 'none' | 'ok' | 'failed';
  extract_chars: number;
  source_path: string | null;
  /** 产物「存为附件」来源任务(溯源; 上传/直接引用恒 null) */
  source_task_id: string | null;
  created_at: string;
  /** session=会话级（仅本会话可读） / global=跨会话全局资产 */
  scope: 'session' | 'global';
  /** 最近注入时间（发送即记） */
  last_used_at: string | null;
  /** 注入次数（「最近用过」判据） */
  use_count: number;
  /** 磁盘文件是否还在（失效行仍可删，但不可加入本轮） */
  available: boolean;
  /** 同 sha 是否已有全局行（= 已收藏） */
  favorited: boolean;
  /** 已收藏时对应全局行 id（取消收藏用） */
  global_id: string | null;
}

export interface ListOptions {
  scope?: AttachmentScope;
  q?: string;
  limit?: number;
  offset?: number;
}

/** 上传白名单/上限/类型选项唯一出口(C8); 前端禁止写死后缀/大小/上限 — 小欧-2026-11-11 */
export interface AttachmentCapabilities {
  accept: string;
  limits: { max_refs: number; max_urls: number; max_url_images: number };
  kind_options: Array<{ value: string; label: string }>;
}

/** P5 运行指标(GET /attachments/metrics): 逐事件计数 + 三比率, 可定位到 source/kind */
export interface AttachmentMetrics {
  days: number;
  counts: Record<string, Record<string, number>>;
  rates: {
    degrade: Record<string, number>;
    native_fail: Record<string, number>;
    extract_fail: Record<string, number>;
  };
}

export const attachmentApi = {
  /** 上传单个文件；onProgress 只给 0~100 的百分比（组件侧渲染用） */
  upload: async (
    sessionId: string,
    file: File,
    onProgress?: (percent: number) => void
  ): Promise<AttachmentRecord> => {
    const form = new FormData();
    form.append('session_id', sessionId);
    form.append('file', file);
    const res = await api.post<AttachmentRecord>('/attachments/upload', form, {
      timeout: HEAVY_READ_TIMEOUT_MS,
      onUploadProgress: (e) => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded / e.total) * 100));
        }
      },
    });
    return res.data;
  },

  /**
   * 附件列表（作用域唯一入口）。
   * 2026-11-07 小欧: 原 `list(sessionId)` 扩为选项对象；session 作用域仍按会话取，
   *   recent/global/ai 跨会话共享（后端判定，前端不参与）— 小欧-2026-11-07
   */
  list: async (
    sessionId?: string | null,
    opts?: ListOptions
  ): Promise<AttachmentRecord[]> => {
    const { scope = 'session', q, limit, offset } = opts ?? {};
    const cfg: ApiRequestConfig = {
      params: { session_id: sessionId || undefined, scope, q, limit, offset },
      _silent: true,
    };
    return (await api.get<AttachmentRecord[]>('/attachments', cfg)).data;
  },

  /** 存在性校验（发送前预检唯一数据源，不走 /files/stat）。
   *  sessionId 必填: 后端会话归属校验；跨会话 session 级附件自动升级为全局。 */
  get: async (id: string, sessionId: string): Promise<AttachmentRecord> => {
    const res = await api.get<AttachmentRecord>(`/attachments/id/${id}`, {
      params: { session_id: sessionId },
    });
    return res.data;
  },

  /** 预览注入文本（排障/预览用；**不**用于入队 —— ChatRef.content 已删除）。
   *  纯预览严格读：会话归属校验必填, 跨会话 session 行如实 404（自动升级只属发送/引用链）。 */
  text: async (
    id: string,
    sessionId: string
  ): Promise<{ id: string; text: string }> => {
    const res = await api.get<{ id: string; text: string }>(
      `/attachments/id/${id}/text`,
      { params: { session_id: sessionId }, timeout: HEAVY_READ_TIMEOUT_MS }
    );
    return res.data;
  },

  /** 收藏（幂等 + sha 去重）：返回全局行；已收藏时返回同一行。 */
  promote: async (id: string, sessionId: string): Promise<AttachmentRecord> => {
    const res = await api.post<AttachmentRecord>(
      `/attachments/id/${id}/promote`,
      null,
      { params: { session_id: sessionId } }
    );
    return res.data;
  },

  /** 真抽取手动重跑（text/richdoc），返回回填后的附件记录 — 小欧-2026-11-11 */
  reextract: async (id: string, sessionId: string): Promise<AttachmentRecord> => {
    const res = await api.post<AttachmentRecord>(
      `/attachments/id/${id}/reextract`,
      null,
      { params: { session_id: sessionId }, timeout: HEAVY_READ_TIMEOUT_MS }
    );
    return res.data;
  },

  /** 重命名展示名（磁盘文件名不变）。 */
  rename: async (
    id: string,
    name: string,
    sessionId?: string | null
  ): Promise<AttachmentRecord> => {
    const res = await api.patch<AttachmentRecord>(`/attachments/id/${id}`, {
      session_id: sessionId || null,
      name,
    });
    return res.data;
  },

  /** 删除附件记录；purge=同时删磁盘文件（无其他行共享该路径时），
   *  force=确认删除被合集引用的文件（否则后端 409 ATTACHMENT_IN_USE）。
   *  _silent: 409 由抽屉弹二次确认，其余错误由调用方就地提示。 */
  remove: async (
    id: string,
    sessionId?: string | null,
    opts?: { purge?: boolean; force?: boolean }
  ): Promise<{ ok: boolean }> => {
    const { purge = true, force = false } = opts ?? {};
    const cfg: ApiRequestConfig = {
      params: { session_id: sessionId || undefined, purge, force },
      _silent: true,
    };
    const res = await api.delete<{ ok: boolean }>(`/attachments/id/${id}`, cfg);
    return res.data;
  },

  /** 清空最近使用记录（不删除任何文件）。 */
  clearRecent: async (): Promise<{ cleared: number }> => {
    const res = await api.post<{ cleared: number }>(
      '/attachments/clear-recent'
    );
    return res.data;
  },

  /**
   * 预览二进制（图片/PDF）：带 token fetch 成 blob。
   * 不能裸 `<img src=...>`：带不了 header 必 401。
   * 纯预览严格读(跨会话 session 行 404)：传 signal 供抽屉卸载/超时中止, 消永久 loading。
   */
  loadRawBlob: async (
    id: string,
    sessionId: string,
    signal?: AbortSignal
  ): Promise<Blob> => {
    const token = getAccessToken();
    const res = await fetch(
      `${API_BASE_URL}/attachments/id/${id}/raw?session_id=${encodeURIComponent(sessionId)}`,
      {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        signal,
      }
    );
    if (!res.ok) throw new Error(`预览加载失败 (${res.status})`);
    return res.blob();
  },

  /**
   * ③ 存为附件（S0）：工作区内产物 → referenced（不复制，直接可引用）；
   * 工作区外 → copied（复制进 attachments/ 并返回完整记录）。
   */
  collect: async (
    sessionId: string,
    sourcePath: string
  ): Promise<CollectResult> => {
    const res = await api.post<CollectResult>('/attachments/collect', {
      session_id: sessionId,
      source_path: sourcePath,
    });
    return res.data;
  },

  /**
   * 同机能力探测：后端判定真实客户端 IP 是否本机。
   * 前端只据此显隐「从本机导入」入口，不参与判定（薄前端）。
   */
  localCapability: async (): Promise<{ local_import: boolean }> => {
    const res = await api.get<{ local_import: boolean }>(
      '/attachments/local-capability'
    );
    return res.data;
  },

  /**
   * 同机本地导入：只传「读源路径」，落盘目标由后端计算。
   * 跨机调用返回 403 LOCAL_IMPORT_DISABLED（后端拦，前端不做判定）。
   */
  importLocal: async (
    sessionId: string,
    path: string
  ): Promise<AttachmentRecord> => {
    const res = await api.post<AttachmentRecord>('/attachments/import-local', {
      session_id: sessionId,
      path,
    });
    return res.data;
  },

  /** GET /attachments/capabilities: 单一出口, 不设 /limits 别名 */
  capabilities: async (): Promise<AttachmentCapabilities> => {
    const res = await api.get<AttachmentCapabilities>('/attachments/capabilities');
    return res.data;
  },

  /** GET /attachments/metrics: 只读日志聚合(P5), 不加新表 */
  metrics: async (days = 1): Promise<AttachmentMetrics> => {
    const res = await api.get<AttachmentMetrics>('/attachments/metrics', { params: { days } });
    return res.data;
  },
};

/** ③ 存为附件双形态（与 backend/app/attachments/collect.py 返回同构） */
export type CollectResult =
  | { mode: 'referenced'; path: string; label: string; size: number }
  | { mode: 'copied'; attachment: AttachmentRecord };
