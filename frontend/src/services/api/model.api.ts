// 编辑历史: 2026-09-20 小强 - 新建：模型管理 API（与 config.api.ts 同模式；current_model_ref 复用 SessionModelOverride）
// 编辑历史: 2026-09-21 小强 - deleteProvider 返回类型补齐 mtime(ModelMutationResult, 与 deleteModel 同构、后端同样返回 mtime)，消除表单 union 后 res.mtime 的 TS 报错 — 小强-2026-09-21
// 2026-09-21 小欧 - P0-9：addProvider 参数扩 api_key（[58] P0-9）
// 2026-09-21 小欧 - ProviderEntry 补 max_retries 字段（对齐后端 GET /models 返回 max_retries）
// 2026-09-22 小欧 - [62]P3 ModelEntry 补 param_options?: Record<string,string[]>（对齐后端 GET /models
//   返回的三层解析 param_options，前端读链第一站；缺此字段 useSettings 四通道无数据来源）
// 2026-09-22 小欧 - [62]P5：①addModel 入参补 param_options?: Record<string,string[]>（3.3(2)-b，
//   添加口模板区勾选项透传到 POST /models 落盘）；②updateModel Pick 补 'param_options'（3.2(7)，
//   ModelEntry 加该字段后 Pick 缺它 TS 拒收 param_options——后端已校验+落盘，前端类型须同步放开）
// 2026-09-22 小欧 - [62]P6 4.3(4)(5)：ProviderConfigPatch 补 max_retries/label、addProvider 入参补
//   timeout/max_retries（对齐后端 ProviderConfigUpdate/ProviderAddRequest DTO——前端实际发送的字段
//   须在 TS 类型有声明，否则类型保护失效；创建 Provider 弹窗可自定义超时/重试）
// 2026-09-22 小欧 - [62]P8 4.3(9)-2-b：ProviderEntry 补 param_types 元数据（动态字段 schema 源）
// 2026-09-24 小欧 - updateModel data 扩 remove_params?: string[]（②参数行 × 删除键级通道，
//   PUT /models body 白名单字段，后端 update_model 先删后 merge）- 小欧-2026-09-24
// 2026-09-24 小欧 - [68] 模型库：类型补 RemoteModelItem/RemoteModelsResponse/ReplaceModelsResult，
//   方法补 fetchRemoteModels（GET remote-models）/replaceModels（PUT models 替换写入）- 小欧-2026-09-24
// 2026-09-26 小欧 - [72]第七章(7.3) + 第十二章(12.5) + 第十章(10.3) 落地:
//   ①ProviderEntry.api_key 改三键恒定 {configured, prefix, suffix} —— 原类型 {configured, suffix} 撒谎
//     （后端未配置时只返 {configured:false}，无 suffix 键）；第七与十二两章改同一处，按设计合并一次实施
//   ②RemoteModelsResponse 补 status_code?/category? 两字段（第十章错误分类，前端据此分两套文案）
//   ③新增 testConnection(provider, probeKey?) —— POST test-connection，body 传待测 key；
//     刻意不用 GET query（query 会进浏览器历史与服务器 access log，明文 key 留痕）— 小欧-2026-09-26
import api from './client';
import type { SessionModelOverride } from '@/types/chat';

export interface ModelEntry {
  name: string;
  label: string;
  default_params: Record<string, unknown>;
  param_options?: Record<string, string[]>;
  range: Record<string, { min: number; max: number }>;
  capabilities: string[];
}

export interface ProviderEntry {
  name: string;
  label: string;
  api_base: string;
  // 2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}：masked 是后端 mask_secret_value
  //   一次生成好的最终可显示串（三档：len>8 前4+4星+后4 / 4<len<=8 ****+后4 / len<=4 ****），
  //   前端只回显，不再判断档位或拼星号。旧 {configured,prefix,suffix} 三键契约已作废。
  api_key: { configured: boolean; masked: string };
  env: boolean; // v4.19：该 provider 的 api_key 是否被 {NAME}_API_KEY 环境变量接管（config.py _apply_env_overrides 同源判定）
  timeout: number;
  max_retries: number;
  // 2026-09-22 小欧 - [62]P8 4.3(9)-2-b：param_types 元数据（后端 PROVIDER_PARAM_TYPES 下发，
  //   前端动态字段渲染/收集的 schema 源——只渲染不定义）
  param_types?: Record<
    string,
    { type: string; label: string; min?: number; default?: unknown }
  >;
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

export interface RemoteModelItem {
  id: string;
  owned_by?: string | null;
}

export interface RemoteModelsResponse {
  ok: boolean;
  provider: string;
  models: RemoteModelItem[];
  count: number;
  configured: string[];
  current_model?: string | null;
  message?: string;
  // [72]第十章(10.3) - 小欧 - 2026-09-26: 错误分类与状态码随响应返回，前端据此分流
  // "地址问题"与"key 问题"两套文案（**不得统一显示"失败"**）。
  // **404/405/501 → endpoint_unsupported，刻意不判 key 无效**（部分 provider 无 /models 端点）。
  status_code?: number | null;
  category?: 'ok' | 'key_invalid' | 'endpoint_unsupported' | 'network_error';
}

export interface ReplaceModelsResult {
  ok: boolean;
  mtime: number;
  added: string[];
  removed: string[];
}

// [72]第十二章(12.5) - 小欧 - 2026-09-26: 明文查看接口响应（api_key 为明文，仅内存持有不持久化）
export interface ApiKeyPlainResponse {
  provider: string;
  api_key: string;
  configured: boolean;
}

export interface ProviderConfigPatch {
  api_key?: string;
  base_url?: string;
  label?: string;
  timeout?: number;
  retry_times?: number;
  max_retries?: number;
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
    param_options?: Record<string, string[]>;
  }): Promise<ModelsResponse> => {
    const response = await api.post<ModelsResponse>('/models', data);
    return response.data;
  },

  updateModel: async (
    provider: string,
    model: string,
    data: Partial<
      Pick<
        ModelEntry,
        'label' | 'default_params' | 'range' | 'capabilities' | 'param_options'
      >
    > & {
      // 2026-09-24 小欧 - 键级删除名单（与 default_params merge 叠加，后端先删再 merge）- 小欧-2026-09-24
      remove_params?: string[];
    }
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

  // 2026-09-22 小欧 - [62]P6 4.3(5)：addProvider 入参补 timeout/max_retries（添加弹窗可设，
  //   后端 ProviderAddRequest DTO 已有默认 timeout=60/max_retries=3，缺此声明前端弹窗没数据来源，
  //   创建 Provider 只能走后端默认值）
  addProvider: async (data: {
    name: string;
    label?: string;
    api_base?: string;
    api_key?: string;
    timeout?: number;
    max_retries?: number;
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

  // 2026-09-24 小欧 - [68] 拉取远程模型列表 — 小欧-2026-09-24
  fetchRemoteModels: async (
    provider: string
  ): Promise<RemoteModelsResponse> => {
    const response = await api.get<RemoteModelsResponse>(
      `/providers/${enc(provider)}/remote-models`
    );
    return response.data;
  },

  // [72]第十二章(12.5) - 小欧 - 2026-09-26: 取已保存的 api_key 明文（供"眼睛"切换查看）。
  // 后端会记审计日志（provider + 时间 + 来源 IP），env 接管时返回 400 拒绝（YAML 里不是生效值）。
  getApiKeyPlain: async (provider: string): Promise<ApiKeyPlainResponse> => {
    const response = await api.get<ApiKeyPlainResponse>(
      `/providers/${enc(provider)}/api-key`
    );
    return response.data;
  },

  // [72]第十章(10.3) - 小欧 - 2026-09-26: 测试连接（key 正确性检测）。
  // 用 POST 而非 GET query 传待测 key —— query 会进浏览器历史/服务器 access log，明文 key 会留痕。
  // 探测逻辑在后端复用 fetch_remote_models，此处只做转发（不新造第二套）。
  testConnection: async (
    provider: string,
    probeKey?: string
  ): Promise<RemoteModelsResponse> => {
    const response = await api.post<RemoteModelsResponse>(
      `/providers/${enc(provider)}/test-connection`,
      { api_key: probeKey && probeKey.trim() !== '' ? probeKey.trim() : null }
    );
    return response.data;
  },

  // 2026-09-24 小欧 - [68] 替换式写入 models 列表 — 小欧-2026-09-24
  replaceModels: async (
    provider: string,
    models: string[]
  ): Promise<ReplaceModelsResult> => {
    const response = await api.put<ReplaceModelsResult>(
      `/providers/${enc(provider)}/models`,
      { models }
    );
    return response.data;
  },
};
