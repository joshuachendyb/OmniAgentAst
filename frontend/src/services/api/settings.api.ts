// 编辑历史: 2026-09-20 小强 - 新建：设置页 API（getSchema/getAll/getGroup/updateSettings，与 config.api.ts 同模式）
// 2026-09-21 小欧 - [59]B-10 同步：SettingSource 增加 'default'（后端缺省键 source='default'，与显式落盘 yaml 区分）
// 2026-09-23 小欧 - type 联合加 'url'：cors_origins 单行宽框类型（SettingRow case 'url' 走 baseUrlWidth，与 base_url 同款）- 小欧-2026-09-23
// 2026-09-26 小欧 - [72]第九章: 新增 authApi（访问口令设置，唯一权威写通道；settings 通用通道拒绝写 secret 项）— 小欧-2026-09-26
// 2026-09-27 小欧 - [75]5.3：① getTokenStatus 返回类型同步后端（删 masked/config_key/env_name，补两个
//   按来源的结论）；② getTokenStatus 增可选 config 参数，入口查询传 { _skipAuth: true } 不带旧口令
//   （旧口令作废时会把引导查询打成 401/403），验真查询不传、默认带当前口令，两种调法均保留 _skip401；
//   ③ 修两处与实现不符的注释（模块头"未配置口令时放行"、方法注释"只回 configured"）；
//   ④ setToken 内 setAccessToken 包 try/catch —— 5.5 让写失败抛错，而此刻服务端已保存成功，
//   文案须区分"已保存到服务端、浏览器没记住"，否则调用方误以为没保存而反复重试。
import api from './client';
import type { ApiRequestConfig } from './client';
// 2026-09-26 小欧 - 修 C04: 改口令成功后需同步内存 token，否则下一请求带旧口令被 401 踢出 — 小欧-2026-09-26
import { setAccessToken } from './client';

/** 2026-09-26 - 小沈(三遍复核): auth 通道的 401 是"口令不对"这一正常分支，一律不触发全局跳登录页 */
const AUTH_REQ: ApiRequestConfig = { _skip401: true };

/**
 * 访问口令（token）设置 — [72]第九章(9.5.3 第1步/第4步)
 *
 * 为何独立于 settingsApi：`security.access_token` 是 registry 的 secret 项，settings 通用通道
 * **显式拒绝**写 secret（[72]第六章方案 B），故口令有且仅有这条专用写路径
 * （与 provider 通道 modelApi.updateProvider 同构：单一权威写入口，避免同一 key 两个写入口分叉）。
 * 豁免全在 deps（[75]5.1）：GET status 不带口令即放行（带口令照常验真，兼作登录页探针）；
 * POST /auth/token 本机即放行 —— 否则"没口令就永远设不了"死锁。
 */
export const authApi = {
  /**
   * 查状态（**永不回明文**）。返回 3 个字段：
   *   access_token_configured     全局：服务端设过口令没 → 分流"登录"与"首次设置"
   *   can_set_access_token         针对你：能不能设口令 → 分流"填了即设置"与"去服务端本机设"
   *   current_client_requires_auth 针对你：要不要口令 → 手动打开 /login 时不误显示登录框
   *
   * 2026-09-27 小欧 - [75]第5章 5.3：删 masked/config_key/env_name（后端已删，前端类型同步，
   *   否则声明着实际不存在的字段）。另两个字段是 [75] 第4章设计的新增。
   */
  getTokenStatus: async (
    config?: ApiRequestConfig
  ): Promise<{
    access_token_configured: boolean;
    can_set_access_token: boolean;
    current_client_requires_auth: boolean;
  }> => {
    // 2026-09-27 小欧 - [75]第5章 5.3：本端点两种调法（4.2.3 两次查询的分工）：
    //   ① 入口查询 —— 调用方传 { _skipAuth: true } 不带旧口令，后端 5.1 的"不带口令即放行"
    //      豁免必中 → 200，拿结论分流（带旧口令会把引导查询打成 401/403，正是错 8 要修的）。
    //   ② 验真查询 —— 调用方不传 config，默认带上当前口令：200 = 口令有效 / 401 = 口令无效。
    //   两种调法都保留 _skip401，防 401 触发拦截器 location.href='/login' 造成无限重载。
    const response = await api.get('/auth/status', { ...AUTH_REQ, ...config });
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
    try {
      setAccessToken(token); // 同步内存 token：否则下一请求带旧口令 → 401 → 被踢回登录页
    } catch (e) {
      // 2026-09-27 小欧 - [75]5.3/5.5 连锁：5.5 让 setAccessToken 写失败抛错。
      //   服务端此时已保存成功、只是浏览器没记住 —— 文案必须分开说，
      //   否则调用方误以为"没保存"而反复重试（后端状态其实已生效）。
      throw new Error(
        `口令已保存到服务端，但浏览器记住失败：${e instanceof Error ? e.message : String(e)}`
      );
    }
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
