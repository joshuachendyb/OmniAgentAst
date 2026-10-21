// 编辑历史: 2026-10-21 小杨 - 文档[28] 4.4.1 新建：文件浏览 API（6 端点 + 图片 blob），同 session.api 范式 — 小杨-2026-10-21
//   2026-10-21 小杨 - 文档[28] v5.11 对账：recent-files 实码返回包装对象 {session_id, files[]}，
//     此处按真源解包 .files（照裸数组写会 "items.filter is not a function"） — 小杨-2026-10-21
/**
 * 文件浏览 API（只读浏览项目根目录）
 *
 * 契约真源 = 后端 `backend/app/file_browse/`（文档[28] 第五章）：
 * - 路径参数一律"相对项目根"的 posix 路径（后端只接受相对路径，绝对路径/UNC/`..` 一律 400）
 * - 错误信封取 `error.code`（全局 http_exception_handler 包装后的形状，非 detail.code）
 */
import api, { getAccessToken, API_BASE_URL } from './client'; // api 只有默认导出（session.api.ts 同款），具名解构必红

export interface FileNode {
  key: string;
  name: string;
  type: 'dir' | 'file';
  size: number | null;
  mtime: string;
  preview: 'text' | 'image' | 'none';
  children?: FileNode[] | null;
  incomplete_child?: boolean;
}

export interface TreeResponse {
  path: string;
  project_root: string;
  nodes: FileNode[];
  truncated: boolean; // 节点数触顶
  incomplete_depth: boolean; // 深度到顶（前端据此补拉）
  skipped: number; // 本次扫描跳过的坏条目数
}

export interface ReadResponse {
  path: string;
  name: string;
  content: string;
  encoding: string;
  size: number;
  total_lines: number;
  /** O1：文件最近修改时间（与 tree 的 mtime 同口径字符串），I9 单请求刷新用 */
  mtime: string;
}

export interface SearchHit {
  path: string;
  name: string;
  type: string;
  preview: string;
  dir: string;
}

export interface SearchResponse {
  keyword: string;
  results: SearchHit[];
  scanned: number;
  hit_limit: boolean;
  scanned_cap: boolean;
}

export interface RecentFile {
  path: string;
  name: string;
  preview: string;
  last_seen_at: string;
  /** FT1：该文件在最近窗口内被哪些工具动过（后端注册名，字母序） */
  ops: string[];
}

/** 后端 recent-files 的真实返回是包装对象（file_routes.py:77-82），不是裸数组 */
export interface RecentFilesResponse {
  session_id: string;
  files: RecentFile[];
}

export interface RootResponse {
  project_root: string;
  allowed_dirs: string[];
  code_root_blocked: boolean;
}

/** 图片未变化（304）：调用方据此保留旧 objectURL，不视为失败 */
export class ImageUnchanged extends Error {
  constructor() {
    super('image unchanged');
  }
}

const need = (v: string, what: string) => {
  if (!v || !v.trim()) throw new Error(`${what}不能为空`);
};

export const fileApi = {
  fetchRoot: async (): Promise<RootResponse> =>
    (await api.get<RootResponse>('/files/root')).data,

  fetchTree: async (
    path = '',
    maxDepth = 5,
    maxNodes = 5000
  ): Promise<TreeResponse> =>
    (
      await api.get<TreeResponse>('/files/tree', {
        params: { path, max_depth: maxDepth, max_nodes: maxNodes },
      })
    ).data,

  readFile: async (
    path: string,
    cfg?: { signal?: AbortSignal }
  ): Promise<ReadResponse> => {
    need(path, '文件路径');
    return (
      await api.get<ReadResponse>('/files/read', {
        params: { path },
        ...cfg, // I7 竞态防护：调用方传 AbortSignal
      })
    ).data;
  },

  /**
   * 输入框 `@` 补全数据源（文档[28] 4.2.1 途径 3）。
   * 候选过滤（只留可读文本）在调用方做 —— 与后端 `_preview_of()` 的 `text` 判定对齐，
   * 前端不自立规则（M18）。
   */
  searchFiles: async (q: string, limit = 20): Promise<SearchResponse> =>
    (await api.get<SearchResponse>('/files/search', { params: { q, limit } }))
      .data,

  fetchRecentFiles: async (sessionId: string): Promise<RecentFile[]> => {
    need(sessionId, '会话ID');
    // 后端返回 {session_id, files[]} —— 必须解包 .files
    const res = await api.get<RecentFilesResponse>('/files/recent-files', {
      params: { session_id: sessionId },
    });
    return res.data.files ?? [];
  },

  loadImageBlob: async (path: string): Promise<Blob> => {
    need(path, '文件路径');
    // 不能裸 `<img src=API_URL>`：带不了 header 必 401。故 fetch + blob + objectURL。
    const token = getAccessToken(); // 与 authHeaders 同源；无口令即不带头（勿拼出 "Bearer null" 发出去）
    const res = await fetch(
      `${API_BASE_URL}/files/raw?path=${encodeURIComponent(path)}`,
      token ? { headers: { Authorization: `Bearer ${token}` } } : {}
    );
    if (res.status === 304) throw new ImageUnchanged(); // res.ok 对 304 为 false，漏判=误报失败
    if (!res.ok) throw new Error(`图片加载失败 (${res.status})`);
    return res.blob();
  },
};
