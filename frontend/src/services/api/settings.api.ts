// 编辑历史: 2026-09-20 小强 - 新建：设置页 API（getSchema/getAll/getGroup/updateSettings，与 config.api.ts 同模式）
// 2026-09-21 小欧 - [59]B-10 同步：SettingSource 增加 'default'（后端缺省键 source='default'，与显式落盘 yaml 区分）
// 2026-09-23 小欧 - type 联合加 'url'：cors_origins 单行宽框类型（SettingRow case 'url' 走 baseUrlWidth，与 base_url 同款）- 小欧-2026-09-23
// 2026-09-26 小欧 - [72]第九章: 新增 authApi（访问口令设置，唯一权威写通道；settings 通用通道拒绝写 secret 项）— 小欧-2026-09-26
import api from './client';
import type { ApiRequestConfig } from './client';
// 2026-09-26 小欧 - 修 C04: 改口令成功后需同步内存 token，否则下一请求带旧口令被 401 踢出 — 小欧-2026-09-26
import { setAccessToken } from './client';

/** 2026-09-26 - 小沈(三遍复核): auth 通道的 401 是"口令不对"这一正常分支，一律不触发全局跳登录页 */
const AUTH_REQ: ApiRequestConfig = { _skip401: true };

/**
 * 访问口令（token）设置 — [72]第九章(9.5.3 第1步/第4步)
 *
 * 为何独立于 settingsApi：`security.api_token` 是 registry 的 secret 项，settings 通用通道
 * **显式拒绝**写 secret（[72]第六章方案 B），故口令有且仅有这条专用写路径
 * （与 provider 通道 modelApi.updateProvider 同构：单一权威写入口，避免同一 key 两个写入口分叉）。
 * 首次设置豁免由后端处理（未配置口令时该端点放行，否则"没口令就永远设不了"死锁）。
 */
export const authApi = {
  /**
   * 查是否已配置（**永不回明文**）。返回 4 个字段：
   *   configured  是否已配置口令（前端实际只用这一个）
   *   masked      掩码 {configured, masked}，与 provider api_key 同一形状
   *               （mask_secret_value 产物；前端目前零消费）
   *   config_key  落盘的配置键名（security.api_token），供设置页定位
   *   env_name    对应环境变量名（OMNIAGENT_API_TOKEN），供提示"也可改环境变量"
   */
  getTokenStatus: async (): Promise<{
    configured: boolean;
    masked: { configured: boolean; masked: string };
    config_key: string;
    env_name: string;
  }> => {
    // 登录页本身靠这两个端点工作，若放任 401 触发拦截器的 location.href='/login'，就会
    // 进登录页 → getTokenStatus 401 → 跳登录页 → 重载 → 再 401 无限重载。故 auth 通道一律 _skip401。
    const response = await api.get('/auth/status', AUTH_REQ);
    return response.data;
  },
  /**
   * 设置/更换口令（至少 8 位；立即生效，旧口令作废）
   *
   * 落盘成功后必须把新口令写回内存 token 源（真相源仍是 client.ts，此处只同步）：鉴权头每次请求
   * 都现取 getAccessToken()，不同步的话用户改完口令后所有请求仍带刚作废的旧口令 → 首个请求 401
   * → 被踢回登录页，即"改完还得重输一遍"，与后端"立即生效"矛盾。本机豁免故只有非本机访问才复现。
   */
  setToken: async (
    token: string
  ): Promise<{ ok: boolean; message: string }> => {
    const response = await api.post('/auth/token', { token }, AUTH_REQ);
    setAccessToken(token); // 同步内存 token：否则下一请求带旧口令 → 401 → 被踢回登录页
    return response.data;
  },
};

export type SettingSource = 'yaml' | 'env' | 'ro' | 'default';

export interface SettingSchemaItem {
  key: string;
  type:
    | 'text'
    | 'secret'
    | 'textarea'
    | 'tags'
    | 'int'
    | 'float'
    | 'range'
    | 'bool'
    | 'select'
    | 'model_ref'
    | 'url'
    | 'readonly';
  label: string;
  default: unknown;
  options?: Array<string | number>;
  range?: [number, number];
  step?: number;
  storage: string;
  restart: boolean;
  secret: boolean;
  readonly: boolean;
  notice?: string;
}

export interface SettingsSchema {
  groups: Record<string, { label: string; items: SettingSchemaItem[] }>;
}

export interface SettingsAll {
  groups: Record<
    string,
    { data: Record<string, unknown>; sources: Record<string, SettingSource> }
  >;
  version: string;
  mtime: number;
}

export interface SettingsUpdateResult {
  ok: boolean;
  updated: Array<{ key: string; source: string }>;
  need_restart: string[];
  warnings: string[];
  errors: string[];
  mtime: number;
}

export const settingsApi = {
  getSchema: async (): Promise<SettingsSchema> => {
    const response = await api.get<SettingsSchema>('/settings/schema');
    return response.data;
  },

  getMtime: async (): Promise<number> => {
    const response = await api.get<{ mtime: number }>('/settings/mtime');
    return response.data.mtime;
  },

  getAll: async (): Promise<SettingsAll> => {
    const response = await api.get<SettingsAll>('/settings');
    return response.data;
  },

  getGroup: async (
    group: string
  ): Promise<{
    data: Record<string, unknown>;
    sources: Record<string, SettingSource>;
    mtime: number;
  }> => {
    const response = await api.get('/settings', { params: { group } });
    return response.data;
  },

  updateSettings: async (
    patch: Record<string, unknown>
  ): Promise<SettingsUpdateResult> => {
    const response = await api.put<SettingsUpdateResult>('/settings', {
      patch,
    });
    return response.data;
  },
};
