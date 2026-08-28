import api from './client';
import type { SessionModelOverride } from '@/types/chat';

export interface Config {
  ai_model_ref?: SessionModelOverride;
  api_key_configured: boolean;
  theme: 'light' | 'dark';
  language: string;
  security?: SecurityConfig;
}

export interface SecurityConfig {
  contentFilterEnabled: boolean;
  contentFilterLevel: 'low' | 'medium' | 'high';
  whitelistEnabled: boolean;
  commandWhitelist: string;
  blacklistEnabled: boolean;
  commandBlacklist: string;
  confirmDangerousOps: boolean;
  maxFileSize: number;
}

export interface ConfigUpdate {
  ai_model_ref?: SessionModelOverride;
  provider_api_keys?: Record<string, string>;
  theme?: 'light' | 'dark';
  language?: string;
  security?: SecurityConfig;
}

export interface ConfigValidateRequest {
  provider: string;
  api_key: string;
}

export interface ConfigValidateResponse {
  valid: boolean;
  message: string;
  model?: string;
}

export interface ProviderInfo {
  name: string;
  api_base: string;
  api_key: string;
  model: string;
  models: string[];
  timeout: number;
  max_retries: number;
  display_name?: string;
}

export interface FullConfigResponse {
  providers: Record<string, ProviderInfo>;
  current_model_ref: SessionModelOverride;
}

export interface ProviderUpdate {
  api_base?: string;
  api_key?: string;
  model?: string;
  timeout?: number;
  max_retries?: number;
}

export interface ModelAddRequest {
  model: string;
}

export interface FullConfigValidationResponse {
  success: boolean;
  provider: string;
  model: string;
  message: string;
  errors: string[];
  warnings: string[];
}

export interface ConfigFixResponse {
  success: boolean;
  fixed_issues: string[];
  warnings: string[];
  backup_path: string;
}

export interface ConfigPathResponse {
  config_path: string;
  config_dir: string;
  exists: boolean;
}

export interface ProviderAddRequest {
  name: string;
  api_base: string;
  api_key: string;
  model: string;
  models: string[];
  timeout: number;
  max_retries: number;
}

export const configApi = {
  getConfig: async (): Promise<Config> => {
    const response = await api.get<Config>('/config');
    return response.data;
  },

  updateConfig: async (
    config: ConfigUpdate
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.put('/config', config);
    return response.data;
  },

  validateConfig: async (
    data: ConfigValidateRequest
  ): Promise<ConfigValidateResponse> => {
    const response = await api.put<ConfigValidateResponse>(
      '/config/validate',
      data
    );
    return response.data;
  },

  getModelList: async (): Promise<{
    models: {
      id: number;
      provider: string;
      model: string;
      display_name: string;
      current_model: boolean;
    }[];
    default_provider: string;
  }> => {
    const response = await api.get<{
      models: {
        id: number;
        provider: string;
        model: string;
        display_name: string;
        current_model: boolean;
      }[];
      default_provider: string;
    }>('/config/models');
    return response.data;
  },

  getFullConfig: async (): Promise<FullConfigResponse> => {
    const response = await api.get<FullConfigResponse>('/config/full');
    return response.data;
  },

  deleteProvider: async (
    providerName: string
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/config/provider/${providerName}`);
    return response.data;
  },

  updateModel: async (
    providerName: string,
    oldModelName: string,
    newModelName: string
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.put(
      `/config/provider/${providerName}/model/${oldModelName}`,
      { model: newModelName }
    );
    return response.data;
  },

  deleteModel: async (
    providerName: string,
    modelName: string,
    options?: { signal?: AbortSignal }
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(
      `/config/provider/${providerName}/model/${modelName}`,
      options?.signal ? { signal: options.signal } : {}
    );
    return response.data;
  },

  updateProvider: async (
    providerName: string,
    data: ProviderUpdate
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.put(`/config/provider/${providerName}`, data);
    return response.data;
  },

  addModel: async (
    providerName: string,
    data: ModelAddRequest
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.post(
      `/config/provider/${providerName}/model`,
      data
    );
    return response.data;
  },

  addProvider: async (
    data: ProviderAddRequest
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.post('/config/provider', data);
    return response.data;
  },

  fixConfig: async (): Promise<ConfigFixResponse> => {
    const response = await api.post<ConfigFixResponse>('/config/fix');
    return response.data;
  },

  getConfigPath: async (): Promise<ConfigPathResponse> => {
    const response = await api.get<ConfigPathResponse>('/config/path');
    return response.data;
  },

  openConfigFolder: async (): Promise<{ success: boolean; path: string }> => {
    const response = await api.post<{ success: boolean; path: string }>(
      '/config/open-folder'
    );
    return response.data;
  },

  readConfigFile: async (): Promise<{ config_content: string }> => {
    const response = await api.get<{ config_content: string }>('/config/read');
    return response.data;
  },
};
