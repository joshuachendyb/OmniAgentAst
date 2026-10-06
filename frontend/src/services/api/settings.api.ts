// 编辑历史: 2026-09-20 小强 - 新建：设置页 API（getSchema/getAll/getGroup/updateSettings）
// 2026-09-21 小欧 - SettingSource 增加 'default'（后端缺省键与显式落盘区分）
// 2026-09-23 小欧 - type 联合加 'url'（SettingRow 走 baseUrlWidth）
// 2026-09-26 小欧 - 新增 authApi（口令唯一权威写通道，settings 通道拒写 secret）
// 2026-09-27 小欧 - getTokenStatus 返回类型同步后端（删 3 个死字段、补 2 个按来源结论）、
//   增 config 参数区分入口查询（_skipAuth）与验真查询、_skip401 恒真（config 在前 AUTH_REQ 在后）、
//   setToken 包 try/catch 区分"服务端已保存、浏览器没记住"
import api from './client';
import type { ApiRequestConfig } from './client';
// 2026-09-26 小欧 - 修 C04: 改口令成功后需同步内存 token，否则下一请求带旧口令被 401 踢出 — 小欧-2026-09-26
import { setAccessToken } from './client';

/** 2026-09-26 - 小沈(三遍复核): auth 通道的 401 是"口令不对"这一正常分支，一律不触发全局跳登录页 */
const AUTH_REQ: ApiRequestConfig = { _skip401: true };

/**
 * 访问口令（token）读写 —— 唯一权威写入口。
 * security.access_token 是 registry 的 secret 项，settings 通用通道显式拒绝写 secret，
 * 故独立于 settingsApi（与 provider 通道同构，避免同 key 两个写入口）。
 * 豁免判定全在 deps：GET status 不带口令即放行、带口令照常验真；POST /auth/token 本机即放行。
 */
export const authApi = {
  /**
   * 查状态（永不回明文），返回四个字段：
   *   access_token_configured      全局：是否已设口令 → 分流"登录"与"首次设置"
   *   can_set_access_token         本来源：能否设口令 → 分流"填了即设置"与"去本机设"
   *   set_token_blocked_reason     被拒原因：'not_local' | 'proxy_untrusted' | null
   *   current_client_requires_auth 本来源：是否需要口令 → 免口令来源不误显示登录框
   * masked/config_key/env_name 已随后端删除（无人消费），两个按来源的结论为新增。
   */
  getTokenStatus: async (
    config?: ApiRequestConfig
  ): Promise<{
    access_token_configured: boolean;
    can_set_access_token: boolean;
    set_token_blocked_reason: 'not_local' | 'proxy_untrusted' | null;
    current_client_requires_auth: boolean;
  }> => {
    // 两种调法：
    //   ① 入口查询 config={_skipAuth:true} 不带旧口令 → 后端豁免必中 → 200 拿结论分流
    //      （带旧口令会把引导查询打成 401/403）
    //   ② 验真查询 不传 config → 默认带当前口令 → 200 有效 / 401 无效
    // 展开顺序 config 在前、AUTH_REQ 在后：保证 _skip401 恒为 true，
    // 否则调用方误传 _skip401:false 会触发拦截器跳登录 → 无限重载
    const response = await api.get('/auth/status', { ...config, ...AUTH_REQ });
    return response.data;
  },
  /**
   * 设置/更换口令（至少 8 位，立即生效、旧口令作废）。
   *
   * 落盘成功后须把新口令写回内存 token 源（真相源在 client.ts，此处只同步）：鉴权头每次请求现取
   * getAccessToken()，不同步则下一请求带已作废的旧口令 → 401 → 被踢回登录页，与"立即生效"矛盾。
   */
  setToken: async (
    token: string
  ): Promise<{ ok: boolean; message: string }> => {
    const response = await api.post('/auth/token', { token }, AUTH_REQ);
    try {
      setAccessToken(token); // 同步内存 token：否则下一请求带旧口令 → 401 → 被踢回登录页
    } catch (e) {
      // setAccessToken 写失败会抛错，而此刻服务端已保存成功。
      // 错误信息须自述"已存服务端、浏览器没记住"，否则调用方误判未保存而反复重试
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

// 2026-10-06 小欧 - 安全 Tab 说明文案三段(均已由后端插值好真实路径, 前端零字符串逻辑)
export interface SecurityDocsResponse {
  /** 弹框1「安全策略说明」: 5 组 22 条 */
  policy: string;
  /** 弹框2「读写判定流程」: mermaid 流程图 + 八步表 + 白名单清单 */
  flow: string;
  /** 页面内直出分类表: 4 类 5 行 × 4 列 */
  classification: string;
}

export const settingsApi = {
  // 2026-10-06 小欧: 安全说明文案只读, 不并入 getAll —— 那边是可配置项的值, 混一起前端分不清哪个能改
  getSecurityDocs: async (): Promise<SecurityDocsResponse> => {
    const response = await api.get<SecurityDocsResponse>(
      '/settings/security-docs'
    );
    return response.data;
  },

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
