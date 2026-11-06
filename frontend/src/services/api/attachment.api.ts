// 编辑历史: 2026-11-06 小欧 - 新建: 附件 API(上传/列表/详情/文本/删除/collect/localCapability/importLocal)
//   前端附件功能 — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧 - F-09: AttachmentRecord 补 source_task_id(方案B溯源, 与后端 _COLS 对齐);
//   B-03: get/remove/text 增 sessionId 必填(后端会话归属校验, 越会话视同不存在) — 小欧-2026-11-07
/**
 * 附件 API 封装（同 file.api / session.api 范式）
 *
 * 契约真源 = backend/app/api/v1/attachments.py + app/attachments/attachment_service.py
 * - 上传用 multipart/form-data（session_id + file），由 axios 自动带 boundary，**不手写 Content-Type**
 * - 记录里的 path 是「项目根相对 posix 路径」，直接用于 refs 上行
 * - 错误取 error.code（全局 http_exception_handler 包装后的形状），不匹配中文文案
 */
import api, { HEAVY_READ_TIMEOUT_MS } from './client'; // api 只有默认导出（同 file.api）

export interface AttachmentRecord {
  id: string;
  session_id: string;
  original_name: string;
  stored_path: string;
  /** 项目根相对 posix 路径（上行 refs 用） */
  path: string;
  mime: string;
  size: number;
  sha256: string;
  kind: 'text' | 'image' | 'video' | 'richdoc' | 'binary';
  extract_status: 'none' | 'ok' | 'failed';
  extract_chars: number;
  source_path: string | null;
  /** 产物「存为附件」来源任务(方案B溯源; 上传/直接引用恒 null) */
  source_task_id: string | null;
  created_at: string;
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

  list: async (sessionId: string): Promise<AttachmentRecord[]> => {
    const res = await api.get<AttachmentRecord[]>('/attachments', {
      params: { session_id: sessionId },
    });
    return res.data;
  },

  /** 存在性校验（发送前预检唯一数据源，不走 /files/stat）。
   *  sessionId 必填: 后端会话归属校验(B-03), 越会话访问视同附件不存在。 */
  get: async (id: string, sessionId: string): Promise<AttachmentRecord> => {
    const res = await api.get<AttachmentRecord>(`/attachments/id/${id}`, {
      params: { session_id: sessionId },
    });
    return res.data;
  },

  /** 预览注入文本（排障/素材包预览用；**不**用于入队 —— ChatRef.content 已删除）。
   *  sessionId 必填: 后端会话归属校验(B-03)。 */
  text: async (id: string, sessionId: string): Promise<{ id: string; text: string }> => {
    const res = await api.get<{ id: string; text: string }>(
      `/attachments/id/${id}/text`,
      { params: { session_id: sessionId }, timeout: HEAVY_READ_TIMEOUT_MS }
    );
    return res.data;
  },

  /** 删除附件记录（限本会话, B-03）; 默认不删磁盘文件。 */
  remove: async (
    id: string,
    sessionId: string,
    purge = false
  ): Promise<{ ok: boolean }> => {
    const res = await api.delete<{ ok: boolean }>(`/attachments/id/${id}`, {
      params: { session_id: sessionId, purge },
    });
    return res.data;
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
};

/** ③ 存为附件双形态（与 backend/app/attachments/collect.py 返回同构） */
export type CollectResult =
  | { mode: 'referenced'; path: string; label: string; size: number }
  | { mode: 'copied'; attachment: AttachmentRecord };
