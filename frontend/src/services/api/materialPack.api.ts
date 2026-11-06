// 编辑历史: 2026-11-06 小欧 - 新建: 素材包 API(列表/建/改/删) — 小欧-2026-11-06
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
  items: Array<{ path: string; label?: string }>;
}

export interface MaterialPackPatch {
  name?: string;
  note?: string;
  group_name?: string;
  /** 传数组 = 整包覆盖；传 undefined = 不动清单 */
  items?: Array<{ path: string; label?: string }>;
}

export const materialPackApi = {
  list: async (): Promise<MaterialPack[]> => {
    const res = await api.get<MaterialPack[]>('/material-packs');
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
