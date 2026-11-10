// 编辑历史: 2026-11-06 小欧 - 新建: 素材包 API(列表/建/改/删) — 小欧-2026-11-06
// 编辑历史: 2026-11-07 小欧 - 条目保留引用身份(kind/attachment_id),
//   附件条目投喂时按 id 恢复附件语义(原只存 path/label, 附件降格为普通文件引用) — 小欧-2026-11-07
// 编辑历史: 2026-11-10 小欧 - 新增 limits(): 限额(包总数/单包条目)由后端单一出口下发,
//   前端据此预校验, 不再本地硬编码 — 小欧-2026-11-10
// 编辑历史: 2026-11-10 小欧 注释清理: 去除修复序号等过期标识, 注释语义不变 — 小欧-2026-11-10
/**
 * 素材包（⑤）API 封装。
 *
 * 契约真源 = backend/app/api/v1/material_packs.py + app/material_packs/material_pack_service.py
 * - 只存清单：items 里是「引用同口径」路径（项目根内相对 / 盘符绝对），不动磁盘
 * - update 的 PATCH 语义：字段为 undefined = 不改，items 为 [] = 清空清单
 * - 错误码：PACK_NAME_CONFLICT(409) / INVALID_PARAM(400)，由全局处理器提示，本层不解析中文
 */
import api from './client';

export interface MaterialPackItem {
  seq: number;
  /** 与引用同口径：项目根内相对 posix / 盘符绝对 */
  path: string;
  label: string;
  /** 引用身份: attachment 时投喂按 attachment_id 恢复附件语义 */
  kind?: string | null;
  attachment_id?: string | null;
}

export interface MaterialPack {
  id: string;
  name: string;
  note: string;
  /** 空串 = 未分组；分组只是标签，不建表 */
  group_name: string;
  created_at: string;
  updated_at: string;
  items: MaterialPackItem[];
}

export interface MaterialPackInput {
  name: string;
  note?: string;
  group_name?: string;
  items: Array<{ path: string; label?: string; kind?: string; attachment_id?: string }>;
}

export interface MaterialPackPatch {
  name?: string;
  note?: string;
  group_name?: string;
  /** 传数组 = 整包覆盖；传 undefined = 不动清单 */
  items?: Array<{ path: string; label?: string; kind?: string; attachment_id?: string }>;
}

export interface MaterialPackLimits {
  max_packs: number;
  max_items: number;
  max_name: number;
  max_label: number;
}

export const materialPackApi = {
  list: async (): Promise<MaterialPack[]> => {
    const res = await api.get<MaterialPack[]>('/material-packs');
    return res.data;
  },

  limits: async (): Promise<MaterialPackLimits> => {
    const res = await api.get<MaterialPackLimits>('/material-packs/limits');
    return res.data;
  },

  create: async (body: MaterialPackInput): Promise<MaterialPack> => {
    const res = await api.post<MaterialPack>('/material-packs', body);
    return res.data;
  },

  update: async (
    id: string,
    patch: MaterialPackPatch
  ): Promise<MaterialPack> => {
    const res = await api.patch<MaterialPack>(`/material-packs/${id}`, patch);
    return res.data;
  },

  remove: async (id: string): Promise<{ ok: boolean }> => {
    const res = await api.delete<{ ok: boolean }>(`/material-packs/${id}`);
    return res.data;
  },
};
