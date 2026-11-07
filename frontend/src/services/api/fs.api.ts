// 编辑历史: 2026-11-07 小欧 - 新建: 同机文件系统 API(磁盘/常用位置/授权目录 增删查),
//   供「附件」抽屉「我的电脑」自研浏览器; 契约真源 backend/app/api/v1/fs_routes.py
//   — 小欧-2026-11-07
/**
 * 同机文件系统 API 封装。
 *
 * 全部端点**仅同机可用**：跨机返回 403 LOCAL_IMPORT_DISABLED（后端判定，前端不参与）。
 * 授权台账落 SQLite（local_auth_dirs），撤销不影响已导入的附件（附件已复制进工作区）。
 */
import api from './client';
import type { ApiRequestConfig } from './client';

export interface FsDrive {
  /** 盘符根，如 `D:\` */
  path: string;
  /** 卷标（Windows 磁盘名称），可能为空 */
  label: string;
  /** 总字节数；不可读的盘为 0 */
  total: number;
  /** 剩余字节数 */
  free: number;
  ready: boolean;
}

/** 常用位置（桌面/下载/文档）：后端只下发真实存在的目录 */
export interface QuickPath {
  label: string;
  path: string;
}

export interface AuthDir {
  path: string;
  /** 授权时间（ISO，秒精度） */
  created_at: string;
}

export interface DrivesResponse {
  /** 本机主机名，抽屉标题「我的电脑 · {host}」用 */
  host_label: string | null;
  drives: FsDrive[];
  quick: QuickPath[];
}

// 三个端点都由抽屉自渲染状态（列表空/失败都有局部提示），失败不弹全局 toast
const silent: ApiRequestConfig = { _silent: true };

export const fsApi = {
  drives: async (): Promise<DrivesResponse> =>
    (await api.get<DrivesResponse>('/fs/drives', silent)).data,

  listAuthorized: async (): Promise<AuthDir[]> =>
    (await api.get<{ dirs: AuthDir[] }>('/fs/authorize', silent)).data.dirs ??
    [],

  /** 授权一个目录（幂等）；受保护目录（凭据/系统配置/浏览器配置）返回 400 */
  authorize: async (path: string): Promise<AuthDir[]> =>
    (await api.post<{ dirs: AuthDir[] }>('/fs/authorize', { path })).data
      .dirs ?? [],

  /** 撤销授权（不影响已导入的附件） */
  revoke: async (path: string): Promise<AuthDir[]> =>
    (
      await api.delete<{ dirs: AuthDir[] }>('/fs/authorize', {
        params: { path },
      })
    ).data.dirs ?? [],
};
