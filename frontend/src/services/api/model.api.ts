// 编辑历史: 2026-09-20 小强 - 新建：模型管理 API（与 config.api.ts 同模式；current_model_ref 复用 SessionModelOverride）
// 编辑历史: 2026-09-21 小强 - deleteProvider 返回类型补齐 mtime(ModelMutationResult, 与 deleteModel 同构、后端同样返回 mtime)，消除表单 union 后 res.mtime 的 TS 报错 — 小强-2026-09-21
// 2026-09-21 小欧 - P0-9：addProvider 参数扩 api_key（[58] P0-9）
import api from './client';
import type { SessionModelOverride } from '@/types/chat';

export interface ModelEntry {
  name: string;
  label: string;
  default_params: Record<string, unknown>;
  range: Record<string, { min: number; max: number }>;
  capabilities: string[];
}

export interface ProviderEntry {
  name: string;
  label: string;
  api_base: string;
  api_key: { configured: boolean; suffix: string };
  env: boolean; // v4.19：该 provider 的 api_key 是否被 {NAME}_API_KEY 环境变量接管（config.py _apply_env_overrides 同源判定）
  timeout: number;
  models: ModelEntry[];
}

export interface ModelsResponse {
  providers: ProviderEntry[];
  current_model_ref: SessionModelOverride;
  ok?: boolean;
  switched_to?: string | null;
  mtime?: number;
}

export interface ModelMutationResult {
  ok: boolean;
  model?: string;
  provider?: string;
  switched_to?: string | null;
  mtime: number;
}

export interface ProviderConfigPatch {
  api_key?: string;
  base_url?: string;
  timeout?: number;
  retry_times?: number;
  clear?: boolean;
}

const enc = (s: string): string => encodeURIComponent(s);

export const modelApi = {
  getModels: async (): Promise<ModelsResponse> => {
    const response = await api.get<ModelsResponse>('/models');
    return response.data;
  },

  addModel: async (data: {
    provider: string;
    model: string;
    label?: string;
    default_params?: Record<string, unknown>;
    range?: Record<string, { min: number; max: number }>;
    capabilities?: string[];
  }): Promise<ModelsResponse> => {
    const response = await api.post<ModelsResponse>('/models', data);
    return response.data;
  },

  updateModel: async (
    provider: string,
    model: string,
    data: Partial<
      Pick<ModelEntry, 'label' | 'default_params' | 'range' | 'capabilities'>
    >
  ): Promise<ModelMutationResult> => {
    const response = await api.put(
      `/models/${enc(provider)}/${enc(model)}`,
      data
    );
    return response.data;
  },

  deleteModel: async (
    provider: string,
    model: string
  ): Promise<ModelMutationResult> => {
    const response = await api.delete(`/models/${enc(provider)}/${enc(model)}`);
    return response.data;
  },

  getProviders: async (): Promise<ProviderEntry[]> => {
    const response = await api.get<ProviderEntry[]>('/providers');
    return response.data;
  },

  addProvider: async (data: {
    name: string;
    label?: string;
    api_base?: string;
    api_key?: string;
  }): Promise<ModelMutationResult> => {
    const response = await api.post('/providers', data);
    return response.data;
  },

  updateProvider: async (
    name: string,
    data: ProviderConfigPatch
  ): Promise<ModelMutationResult> => {
    const response = await api.put(`/providers/${enc(name)}`, data);
    return response.data;
  },

  // 2026-09-21 小强 - 修复类型瑕疵：deleteProvider 补齐 mtime（与 deleteModel 同构、后端同样返回 mtime，缺此字段表单 union 后 res.mtime 报错）
  deleteProvider: async (name: string): Promise<ModelMutationResult> => {
    const response = await api.delete(`/providers/${enc(name)}`);
    return response.data;
  },
};
