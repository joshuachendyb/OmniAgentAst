// 编辑历史: 2026-09-21 小强 - 关于页功能：新增 readVersionFile（GET /config/version-file 返回 version.txt 全文）
// 2026-09-21 小欧 - 删除无意义白/黑名单类型（whitelistEnabled/commandWhitelist/blacklistEnabled/commandBlacklist）：后端 SecurityConfig 已删，无消费方（北京老陈裁定）
// 编辑历史: 2026-09-21 小强 - 关于页功能：新增 readVersionFile（GET /config/version-file 返回 version.txt 全文）
// 2026-09-21 小欧 - 删除无意义白/黑名单类型（whitelistEnabled/commandWhitelist/blacklistEnabled/commandBlacklist）：后端 SecurityConfig 已删，无消费方（北京老陈裁定）
// 2026-09-21 小强 - DRY收口：新增 configApi.switchCurrentModel 切全局模型唯一写链（Layout.handleModelChange 与 CurrentModelRefCard.onOk 共用，消除重复 updateConfig+ai_model_ref 装配）
// 2026-09-24 19:38:01 小欧 - 禁止backward死代码清理: 删 /config/provider/* 6个死方法及专属类型 ProviderUpdate/ModelAddRequest/ProviderAddRequest（设置2版已走 modelApi /models /providers）— 小欧-2026-09-24
// 2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}：masked 由后端唯一权威
//   mask_secret_value 一次生成（/config/full 已是该形状），前端纯回显。
//   与 model.api.ts ProviderEntry.api_key 同一契约。
// 2026-09-26 小欧 - [72]第十一章(11.5 第1步): 删 ConfigUpdate 接口与 updateConfig 方法（均零调用），
//   其中 provider_api_keys 字段是第三章认定的"第二个能擦除密钥的入口"，删除后前后端一致收敛；
//   切全局模型由 switchCurrentModel 走收敛后的 PUT /config（只写 ai_model_ref）— 小欧-2026-09-26
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
  confirmDangerousOps: boolean;
}

// 2026-09-26 小欧 - [72]第十一章(11.5 第1步): 删 ConfigUpdate 接口 —— 随 updateConfig 方法一并删除
//   （该方法全项目零调用，仅 config.api.ts 内自引用）。其中的 provider_api_keys 字段是
//   [72]第三章认定的"第二个能擦除密钥的入口"，前端亦无任何调用方，删除后前后端一致收敛。
//   切全局模型改由 configApi.switchCurrentModel 走收敛后的 PUT /config（只写 ai_model_ref）。

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
  // 2026-09-27 小欧 - /config/full 的 api_key 由唯一权威 mask_secret_value 生成，
  //   形状为 {configured, masked}（masked 是最终可显示串）。与 model.api.ts 同一契约。
  api_key: { configured: boolean; masked: string };
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

export const configApi = {
  getConfig: async (): Promise<Config> => {
    const response = await api.get<Config>('/config');
    return response.data;
  },

  // 2026-09-21 小强 - 切全局模型共用(DRY收口): Layout.handleModelChange与CurrentModelRefCard.onOk
  //   原先各自重复 updateConfig+ai_model_ref装配, 现统一唯一写链入口, 两调用方只传provider/model
  // 2026-09-26 小欧 - [72]第十一章: 后端 PUT /config 收敛为**只写 ai_model_ref**（六个旧 handler 已删，
  //   provider_api_keys 漏洞字段已移除），本方法语义随之收敛，与后端契约一致。
  switchCurrentModel: async (
    provider: string,
    model: string
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.put<{ success: boolean; message: string }>(
      '/config',
      { ai_model_ref: { provider, model } }
    );
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

  readConfigFile: async (): Promise<{
    config_content: string;
    path: string;
    size: number;
    lines: number;
    mtime: number;
  }> => {
    const response = await api.get<{
      config_content: string;
      path: string;
      size: number;
      lines: number;
      mtime: number;
    }>('/config/read');
    return response.data;
  },

  // 2026-09-21 小强 - 关于页"查看 version 文件全文"：后端 GET /config/version-file
  readVersionFile: async (): Promise<{
    version_content: string;
    path: string;
    size: number;
    lines: number;
    mtime: number;
  }> => {
    const response = await api.get<{
      version_content: string;
      path: string;
      size: number;
      lines: number;
      mtime: number;
    }>('/config/version-file');
    return response.data;
  },
};
