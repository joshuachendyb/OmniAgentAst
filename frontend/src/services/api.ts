// 编辑历史: 2026-08-26 小欧 - 修复A1: 新增sessionApi.getSession返回Session(created_at/updated_at)供顶栏时间悬浮(7.1⑤)
// 编辑历史: 2026-08-27 小欧 - SessionTaskItem 新增 response 字段（optional），支撑左列任务列表显示任务结果全文
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: Config.ai_model_ref改可选(无前端读取点); api.Message重命名ApiMessage避免与types/chat.Message冲突
// 编辑历史: 2026-08-27 小欧 - 修复BUG1: getSession兜底version/title_locked/title_source/title_updated_at, 杜绝ChatHeader 409恢复读version恒undefined致保存死循环
// 编辑历史: 2026-08-27 小欧 - 修复BUG2: listSessions逐条兜底Session缺失字段
// 编辑历史: 2026-08-27 小欧 - 修复BUG3: getSessionTitlesBatch对session_ids逐条encodeURIComponent, 避免空格/+/&扭曲
// 编辑历史: 2026-08-27 小欧 - 修复BUG4: getSessionMessages兼容后端thought→is_reasoning并暴露thought字段
/**
 * API服务层 - api.ts
 *
 * 功能：封装所有后端API调用，统一错误处理和类型定义
 *
 * 错误处理说明：
 * - 所有API错误统一使用 errorHandler.handleApiError() 处理
 * - 禁止直接调用 message.error/warning/success/info
 * - 错误去重、提示样式、重试逻辑由 errorHandler 统一管理
 *
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-17
 * @update 添加配置管理、会话管理接口 - by 小新
 * @update 2026-08-22 小欧 - sessionModel 结构化(L2 会话级模型覆盖): GetSessionMessagesResponse/UpdateSessionResponse 字段 model_override→sessionModel(SessionModelOverride 类型); updateSession 签名加 sessionModel 参数并发送
 * @update 2026-08-22 小欧 - model结构化归一报告v1.25/v1.26 6.6 方案B(前端随后端修改): Config.ai_provider/ai_model→ai_model_ref、ConfigUpdate 同、FullConfigResponse.current_provider/current_model→current_model_ref(均 SessionModelOverride=后端 ModelRef 镜像, 补 api_base?); ValidateResponse.provider/model→model_ref?; types/chat.ts SessionModelOverride 补 api_base?
 * @update 2026-08-26 小欧 - 8.2.1 任务清单(B1)/任务详情(C1)/执行步骤(C2)/信任(D1/D2) API 命名空间+类型+adaptTaskDetail 纯函数落地
 */

import axios from 'axios';
import type { ExecutionStep } from '../types/execution';
import type { SessionModelOverride } from '../types/chat';
import { handleApiError } from '../utils/errorHandler';

// 【小新修复 2026-03-14】统一API地址配置，支持环境变量
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/**
 * Axios实例配置
 *
 * 包含统一错误处理和日志记录
 */
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 120000, // 2分钟超时（免费模型响应慢）
});

/**
 * 请求拦截器 - 添加日志
 */
api.interceptors.request.use(
  (config) => {
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

/**
 * 响应拦截器 - 统一错误处理
 * 【小强修复 2026-04-11】使用统一错误处理中心
 */
api.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.config.url} - ${response.status}`);
    return response;
  },
  (error) => {
    console.error('[API Response Error]', error);

    // 使用统一错误处理中心
    handleApiError(error, {
      showError: true,
    });

    return Promise.reject(error);
  }
);

// ============================================
// 健康检查接口
// ============================================
export interface HealthStatus {
  status: string;
  timestamp: string;
  version: string;
}

export interface EchoRequest {
  message: string;
}

export interface EchoResponse {
  received: string;
  timestamp: string;
}

export const healthApi = {
  checkHealth: async (): Promise<HealthStatus> => {
    const response = await api.get<HealthStatus>('/health');
    return response.data;
  },

  echo: async (message: string): Promise<EchoResponse> => {
    const response = await api.post<EchoResponse>('/echo', { message });
    return response.data;
  },
};

// ============================================
// 对话接口
// ============================================
export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
}

export interface ValidateResponse {
  valid: boolean; // 2026-08-27 小欧 修复#31: 后端/chat/validate返回valid, 非success(字段名不匹配导致校验成功误判为失效)
  // 归一(小欧 2026-08-22 报告v1.25 6.6 方案B): 后端 /chat/validate 响应 provider/model 键归一 model_ref 结构, 前端随之后端
  model_ref?: {
    provider: string;
    model: string;
    api_base?: string;
    display_name?: string;
  } | null;
  message: string;
  status?: 'success' | 'failed' | 'warning';
}

export const chatApi = {
  /**
   * 【已废弃 2026-03-26】非流式聊天 - 未被使用
   * 流式聊天使用 sse.ts 的 sendMessage
   * 保留代码供参考，已移至 backup/api废弃代码.ts
   */
  // sendMessage: async (
  //   messages: ChatMessage[],
  //   temperature: number = 0.7
  // ): Promise<ChatResponse> => {
  //   const response = await api.post<ChatResponse>("/chat", {
  //     messages,
  //     stream: false,
  //     temperature,
  //   });
  //   return response.data;
  // },

  /**
   * 验证AI服务配置 - 已存在API
   * @author 小新
   */
  validateService: async (): Promise<ValidateResponse> => {
    const response = await api.get<ValidateResponse>('/chat/validate', {
      timeout: 30000,
    });
    return response.data;
  },
};

// ============================================
// 配置管理接口
// @author 小新
// @update 2026-02-18 已对接真实API
// ============================================
export interface Config {
  // 归一(小欧 2026-08-22 报告v1.25 6.6 方案B): ai_provider/ai_model → ai_model_ref 结构(SessionModelOverride=后端ModelRef镜像)
  // 2026-08-27 小欧 三堂会审: 后端可能未返回该字段, 故改为可选, 前端无直接读取点无需空守卫
  ai_model_ref?: SessionModelOverride;
  api_key_configured: boolean;
  theme: 'light' | 'dark';
  language: string;
  // 安全配置
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
  // 归一(小欧 2026-08-22 报告v1.25 6.6 方案B): provider+model 成对语义由 SessionModelOverride 单结构承载(原子切换),
  // 后端 _update_model_ref 单 handler 原子写入, 不再拆两字段依赖处理顺序
  ai_model_ref?: SessionModelOverride;

  // ⭐ 修复：使用统一的 provider_api_keys，不硬编码 provider 名称
  provider_api_keys?: Record<string, string>; // {provider_name: api_key}
  theme?: 'light' | 'dark';
  language?: string; // ⭐ 新增：language 字段
  // 安全配置
  security?: SecurityConfig;
}

export interface ConfigValidateRequest {
  // ⭐ 修复：使用字符串，不硬编码 provider 名称
  provider: string;
  api_key: string;
}

export interface ConfigValidateResponse {
  valid: boolean;
  message: string;
  model?: string;
}

// Provider和Model管理的接口
export interface ProviderInfo {
  name: string;
  api_base: string;
  api_key: string;
  model: string;
  models: string[];
  timeout: number;
  max_retries: number;
  display_name?: string; // 可选的显示名称
}

export interface FullConfigResponse {
  providers: Record<string, ProviderInfo>;
  // 归一(小欧 2026-08-22 报告v1.25 6.6 方案B): current_provider/current_model → current_model_ref 结构
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

// 完整配置验证响应（小新新增）
export interface FullConfigValidationResponse {
  success: boolean;
  provider: string;
  model: string;
  message: string;
  errors: string[];
  warnings: string[];
}

// 配置修复响应（小沈新接口）
export interface ConfigFixResponse {
  success: boolean;
  fixed_issues: string[];
  warnings: string[];
  backup_path: string;
}

// 配置文件路径响应
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

/**
 * 配置管理API
 *
 * @author 小新
 * @update 2026-02-18 对接小沈后端API
 */
export const configApi = {
  /**
   * 获取当前配置
   * @author 小新
   */
  getConfig: async (): Promise<Config> => {
    const response = await api.get<Config>('/config');
    return response.data;
  },

  /**
   * 更新配置
   * @author 小新
   */
  updateConfig: async (
    config: ConfigUpdate
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.put('/config', config);
    return response.data;
  },

  /**
   * 验证配置
   * @author 小新
   */
  validateConfig: async (
    data: ConfigValidateRequest
  ): Promise<ConfigValidateResponse> => {
    const response = await api.put<ConfigValidateResponse>(
      '/config/validate',
      data
    );
    return response.data;
  },

  /**
   * 验证完整配置（validate-full接口）
   * 用于启动时全面检查所有Provider和Model配置
   * @author 小欧
   * @update 2026-02-23 新增
   * @deprecated 后端已删除 GET /config/validate-full，使用 validateConfig 替代
   */
  // validateFullConfig 已删除

  /**
   * 获取可用模型列表
   * @author 小新
   * @update 2026-02-24 修改类型以匹配后端返回（id, provider, model, display_name, current_model）
   */
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

  /**
   * 获取完整配置（包含所有provider和model）
   * @author 小欧
   */
  getFullConfig: async (): Promise<FullConfigResponse> => {
    const response = await api.get<FullConfigResponse>('/config/full');
    return response.data;
  },

  /**
   * 删除Provider
   * @author 小欧
   */
  deleteProvider: async (
    providerName: string
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.delete(`/config/provider/${providerName}`);
    return response.data;
  },

  /**
   * 更新模型名称
   * @author 小欧
   */
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

  /**
   * 删除 Provider 下的模型
   * @author 小欧
   * @param signal AbortController.signal 用于取消请求
   */
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

  /**
   * 更新Provider配置
   * @author 小欧
   */
  updateProvider: async (
    providerName: string,
    data: ProviderUpdate
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.put(`/config/provider/${providerName}`, data);
    return response.data;
  },

  /**
   * 添加模型到Provider
   * @author 小欧
   */
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

  /**
   * 添加新Provider
   * @author 小欧
   */
  addProvider: async (
    data: ProviderAddRequest
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.post('/config/provider', data);
    return response.data;
  },

  /**
   * 修复配置文件常见问题
   * 自动删除provider下废弃的model字段
   * @author 小新
   * @update 2026-02-26 对接小沈新接口
   */
  fixConfig: async (): Promise<ConfigFixResponse> => {
    const response = await api.post<ConfigFixResponse>('/config/fix');
    return response.data;
  },

  /**
   * 获取配置文件路径
   * @author 小新
   * @update 2026-03-03 新增
   */
  getConfigPath: async (): Promise<ConfigPathResponse> => {
    const response = await api.get<ConfigPathResponse>('/config/path');
    return response.data;
  },

  /**
   * 打开配置文件所在目录
   * 调用系统资源管理器打开文件夹
   * @author 小新
   * @update 2026-03-04 新增
   */
  openConfigFolder: async (): Promise<{ success: boolean; path: string }> => {
    const response = await api.post<{ success: boolean; path: string }>(
      '/config/open-folder'
    );
    return response.data;
  },

  /**
   * 读取配置文件原文内容
   */
  readConfigFile: async (): Promise<{ config_content: string }> => {
    const response = await api.get<{ config_content: string }>('/config/read');
    return response.data;
  },
};

// ============================================
// 会话管理接口
// @author 小新
// @update 2026-02-18 已对接真实API
// @update 2026-02-25 新增title_locked, title_source, title_updated_at, version字段
// ============================================
export interface Session {
  session_id: string;
  title: string;
  title_locked: boolean; // ⭐ 新增：标题是否被用户锁定
  title_source: 'user' | 'auto'; // ⭐ 新增：标题来源（用户手动/自动生成）
  title_updated_at: string | null; // ⭐ 新增：标题最后更新时间
  version?: number; // ⭐ 新增：乐观锁版本号
  created_at: string;
  updated_at: string;
  message_count: number;
  is_valid: boolean; // ⭐ 新增：是否为有效会话（用户创建=true，测试创建=false）
}

export interface SessionListResponse {
  total: number;
  page: number;
  page_size: number;
  sessions: Session[];
}

export interface ApiMessage {
  id: number;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  execution_steps?: ExecutionStep[];
  display_name?: string; // 前端小新代修改：模型显示名称
  is_reasoning?: boolean; // 【小查修复】是否为思考过程（统一使用 snake_case）
  thought?: string; // 2026-08-27 小欧 修复BUG4: 后端返回thought(思考文本), 兼容映射is_reasoning并暴露原文
}

// ⭐ 新增：获取会话消息响应（包含新字段）
export interface GetSessionMessagesResponse {
  session_id: string;
  title: string;
  title_locked: boolean;
  title_source: 'user' | 'auto';
  title_updated_at: string | null;
  version?: number;
  sessionModel?: SessionModelOverride | null;
  messages: ApiMessage[];
}

// ⭐ 新增：更新会话标题请求（包含version参数）
export interface UpdateSessionRequest {
  title: string;
  version: number; // ⭐ 新增：版本号（乐观锁，必须）
  updated_by?: string; // ⭐ 新增：修改者（可选）
}

// ⭐ 新增：更新会话标题响应
export interface UpdateSessionResponse {
  success: boolean;
  title: string;
  version?: number;
  title_locked?: boolean;
  title_updated_at?: string;
  sessionModel?: SessionModelOverride | null;
}

// ⭐ 新增：批量获取会话标题响应
export interface BatchTitleResponse {
  sessions: Array<{
    session_id: string;
    title: string;
    title_locked: boolean;
    title_updated_at: string | null;
    version?: number;
  }>;
}

/**
 * 会话管理API
 *
 * @author 小新
 * @update 2026-02-18 已对接真实API
 */
export const sessionApi = {
  /**
   * 创建新会话
   * @author 小新
   * @update 2026-02-18 已对接真实API
   * @update 2026-03-03 添加is_valid=True，标识为有效会话
   */
  createSession: async (
    title?: string
  ): Promise<{
    session_id: string;
    title: string;
    created_at: string;
    updated_at: string;
    message_count: number;
  }> => {
    const response = await api.post<{
      session_id: string;
      title: string;
      created_at: string;
      updated_at: string;
      message_count: number;
    }>('/sessions', { title, is_valid: true });
    return response.data;
  },

  /**
   * 获取会话列表
   * @author 小新
   * @update 2026-03-03 新增 isValid 参数，支持过滤有效/无效会话
   */
  listSessions: async (
    page: number = 1,
    pageSize: number = 20,
    keyword?: string,
    isValid?: boolean // ⭐ 新增参数：true=有效会话，false=无效会话，undefined=全部
  ): Promise<SessionListResponse> => {
    const params: Record<string, unknown> = { page, page_size: pageSize };
    if (keyword) params.keyword = keyword;
    // 只有明确传入 true 或 false 时才添加 is_valid 参数
    if (isValid === true || isValid === false) params.is_valid = isValid;
    const response = await api.get<SessionListResponse>('/sessions', {
      params,
    });
    // 2026-08-27 小欧 修复BUG2: 后端SessionResponse不含title_locked/title_source/title_updated_at/version, 兜底默认
    return {
      ...response.data,
      sessions: (response.data.sessions ?? []).map((s) => ({
        ...s,
        title_locked: s.title_locked ?? false,
        title_source: s.title_source ?? 'auto',
        title_updated_at: s.title_updated_at ?? null,
        version: s.version ?? 1,
      })),
    };
  },

  /**
   * 获取会话消息
   * @author 小新
   * @update 2026-02-25 新增title_locked, title_source, title_updated_at, version字段
   */
  getSessionMessages: async (
    sessionId: string
  ): Promise<GetSessionMessagesResponse> => {
    const response = await api.get<GetSessionMessagesResponse>(
      `/sessions/${sessionId}/messages`
    );
    // ⭐ 兼容性处理：确保新增字段有默认值
    return {
      ...response.data,
      title_locked: response.data.title_locked ?? false,
      title_source: response.data.title_source ?? 'auto',
      title_updated_at: response.data.title_updated_at ?? null,
      version: response.data.version ?? 1,
      // 2026-08-27 小欧 修复BUG4: 后端返回thought(思考文本), 映射到is_reasoning并暴露thought原文
      messages: (response.data.messages ?? []).map((m) => ({
        ...m,
        thought: m.thought ?? (typeof m.is_reasoning === 'string' ? m.is_reasoning : undefined),
        is_reasoning: m.is_reasoning ?? (m.thought != null && m.thought !== ''),
      })),
    };
  },

  /**
   * 保存消息到会话
   * @author 小新
   * @update 2026-03-16: 添加 display_name 字段
   * @update 2026-03-24: 添加 client_os 等客户端信息（小沈）
   */
  saveMessage: async (
    sessionId: string,
    message: {
      role: string;
      content: string;
      execution_steps?: unknown[];
      // 错误相关字段（API文档字段名）
      is_error?: boolean;
      error_type?: string;
      code?: string;
      message?: string;
      details?: string;
      stack?: string;
      retryable?: boolean;
      retry_after?: number;
      timestamp?: string;
      model?: string;
      provider?: string;
      display_name?: string; // 【小新修改 2026-03-16】添加display_name字段
      // 客户端信息（小沈 2026-03-24）
      client_os?: string;
      browser?: string;
      device?: string;
      network?: string;
    }
  ): Promise<{
    success: boolean;
    message_id?: number;
    message_count?: number;
  }> => {
    const response = await api.post<{
      success: boolean;
      message_id?: number;
      message_count?: number;
    }>(`/sessions/${sessionId}/messages`, message);
    return response.data;
  },

  /**
   * 保存执行步骤到会话
   * @author 小新
   * @update 2026-03-06 新增：用于保存AI思考过程的执行步骤
   * @update 2026-03-16 修正：增加content参数，支持在visibilitychange时同时保存content
   * @update 2026-03-16 修正：增加reply_to_message_id参数，用于校验AI消息ID
   * 修正原因：SSE数据保存方案-综合版第18章要求，visibilitychange时需要同时保存
   *          execution_steps和content，后端API需要支持content参数
   */
  saveExecutionSteps: async (
    sessionId: string,
    executionSteps: unknown[],
    content?: string,
    replyUserMessageId?: number // 新增：回复的用户消息ID
  ): Promise<{
    success: boolean;
    message_id?: number;
    is_new_message?: boolean;
  }> => {
    // ⭐ 【调试】记录前端保存
    console.log(
      `💾 [前端保存] sessionId=${sessionId}, stepsCount=${executionSteps.length}, contentLen=${content?.length || 0}, replyUserMessageId=${replyUserMessageId}`
    );

    const response = await api.post<{
      success: boolean;
      message_id?: number;
      is_new_message?: boolean;
    }>(`/sessions/${sessionId}/execution_steps`, {
      execution_steps: executionSteps,
      ...(content !== undefined && { content }),
      ...(replyUserMessageId !== undefined && {
        reply_to_message_id: replyUserMessageId,
      }),
    });
    return response.data;
  },

  /**
   * 删除会话
   * @author 小新
   */
  deleteSession: async (sessionId: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(
      `/sessions/${sessionId}`
    );
    return response.data;
  },

  /**
   * 更新会话标题
   * @author 小新
   * @update 2026-02-25 新增version和updated_by参数
   */
  updateSession: async (
    sessionId: string,
    title: string,
    version: number, // ⭐ 必须参数：版本号
    sessionModel?: SessionModelOverride | null // 北京老陈 2026-08-22: L2 会话级模型覆盖(结构化)
  ): Promise<UpdateSessionResponse> => {
    const body: Record<string, unknown> = {
      title,
      version, // ⭐ 必须传递
      updated_by: 'user', // ⭐ 可选：标记用户修改
    };
    if (sessionModel !== undefined) {
      body.sessionModel = sessionModel; // 显式传 null=清空跟随全局
    }
    const response = await api.put<UpdateSessionResponse>(
      `/sessions/${sessionId}`,
      body
    );
    return response.data;
  },

    /** A1：会话级创建/更新时间（7.1⑤ 顶栏悬浮数据源） */
  getSession: async (sessionId: string): Promise<Session> => {
    const r = await api.get<Session>(`/sessions/${sessionId}`);
    const d = r.data;
    // 2026-08-27 小欧 修复BUG1: 后端SessionResponse不返回version/title_*字段, 兜底默认,
    // 避免ChatHeader 409恢复分支读sessionData.version恒undefined导致保存死循环
    return {
      ...d,
      title_locked: d.title_locked ?? false,
      title_source: d.title_source ?? 'auto',
      title_updated_at: d.title_updated_at ?? null,
      version: d.version ?? 1,
    };
  },

  /**
   * 批量获取会话标题状态
   * @author 小新
   * @update 2026-02-25 新增批量接口
   * @update 2026-02-25 添加输入验证（Q001）
   */
  getSessionTitlesBatch: async (
    sessionIds: string[]
  ): Promise<BatchTitleResponse> => {
    // 验证1：检查数组是否为空
    if (!sessionIds || sessionIds.length === 0) {
      throw new Error('会话ID列表不能为空');
    }

    // 验证2：检查数组长度（最多50个）
    if (sessionIds.length > 50) {
      throw new Error('批量获取标题最多支持50个会话ID');
    }

    // 验证3：检查每个ID的有效性并过滤
    const validIds = sessionIds.filter((id) => id && id.trim());
    if (validIds.length === 0) {
      throw new Error('没有有效的会话ID');
    }

    // 验证4：检查URL长度
    // 2026-08-27 小欧 修复BUG3: 逐条encodeURIComponent, 避免含空格/+/&/=的id扭曲(对比tokenUsageApi已正确编码)
    const url = `/sessions/titles/batch?session_ids=${validIds.map(encodeURIComponent).join(',')}`;
    if (url.length > 2000) {
      throw new Error('请求URL过长，请减少会话数量');
    }

    const response = await api.get<BatchTitleResponse>(url);
    return response.data;
  },
};

// ============================================================
// 【小新重构2026-03-09】ReAct任务控制API
// 根据设计文档第10.10-10.12节添加
// ============================================================

/**
 * 任务控制响应类型
 */
interface TaskControlResponse {
  success: boolean;
  message: string;
}

/**
 * 用户确认请求类型
 */
interface ConfirmRequest {
  confirm_id: string;
  confirmed: boolean;
  trust_session?: boolean;
}

/**
 * 任务控制API - 用于流式任务执行过程中的控制
 */
export const taskControlApi = {
  /**
   * 取消任务
   * POST /api/v1/chat/stream/cancel/{task_id}
   *
   * @param taskId 任务ID
   * @param sessionId 会话ID（可选）
   * @returns 取消结果
   */
  cancel: async (
    taskId: string,
    sessionId?: string
  ): Promise<TaskControlResponse> => {
    const url = sessionId
      ? `/chat/stream/cancel/${taskId}?session_id=${sessionId}`
      : `/chat/stream/cancel/${taskId}`;
    const response = await api.post<TaskControlResponse>(url);
    return response.data;
  },

  /**
   * 暂停任务
   * POST /api/v1/chat/stream/pause/{task_id}
   *
   * @param taskId 任务ID
   * @param sessionId 会话ID（可选）
   * @returns 暂停结果
   */
  pause: async (
    taskId: string,
    sessionId?: string
  ): Promise<TaskControlResponse> => {
    const url = sessionId
      ? `/chat/stream/pause/${taskId}?session_id=${sessionId}`
      : `/chat/stream/pause/${taskId}`;
    const response = await api.post<TaskControlResponse>(url);
    return response.data;
  },

  /**
   * 恢复任务
   * POST /api/v1/chat/stream/resume/{task_id}
   *
   * @param taskId 任务ID
   * @param sessionId 会话ID（可选）
   * @returns 恢复结果
   */
  resume: async (
    taskId: string,
    sessionId?: string
  ): Promise<TaskControlResponse> => {
    const url = sessionId
      ? `/chat/stream/resume/${taskId}?session_id=${sessionId}`
      : `/chat/stream/resume/${taskId}`;
    const response = await api.post<TaskControlResponse>(url);
    return response.data;
  },

  /**
   * 用户确认操作
   * POST /api/v1/chat/stream/confirm
   *
   * @param confirmId 确认ID
   * @param confirmed 用户选择：true=确认执行，false=拒绝执行
   * @param trustSession 可选，是否信任本次会话
   * @returns 确认结果
   */
  confirm: async (
    confirmId: string,
    confirmed: boolean,
    trustSession?: boolean
  ): Promise<TaskControlResponse> => {
    const body: ConfirmRequest = {
      confirm_id: confirmId,
      confirmed: confirmed,
    };

    if (trustSession !== undefined) {
      body.trust_session = trustSession;
    }

    const response = await api.post<TaskControlResponse>(
      '/chat/stream/confirm',
      body
    );
    return response.data;
  },
};

// ============================================================
// 【小欧 2026-08-26 8.2/8.5/8.7/8.C】任务清单(B1)/任务详情(C1)/执行步骤(C2)/信任(D1/D2)
// 全部对齐后端实测路由与响应形状（2026-08-26 实读 sessions.py/task_execution.py/
// storage.py 核验，见 8.C 对照表）；不再使用拟定形状。
// 【R1 二轮 A6 补全】本节此前仅有类型 SessionTaskItem，三个 API 命名空间与
// adaptTaskDetail 有名无体——现补齐全部真实定义。
// ============================================================

/**
 * 任务清单行（GET /sessions/{session_id}/tasks 实测字段，storage.list_session_tasks）
 * ⚠ 8.C-①：context_link_mode 后端补列（D-1 已实现）后为必填；
 *   补列部署前左列类型徽标守卫不渲染（不阻塞其余字段）。
 */
export interface SessionTaskItem {
  task_id: string;
  user_input: string;
  response?: string; // 任务结果正文（final步骤response，全文显示）
  status: string; // 实测枚举：executing(初始,storage.py:467) → completed/failed/cancelled/paused(:128)；未知值前端兜底灰色
  duration: number | null;
  model: string | null; // sessionModel JSON 派生键（后端已派生）
  provider: string | null;
  total_steps: number;
  llm_call_count: number;
  created_at: string;
  updated_at: string;
  /** ⚠ 8.C-①/D-1：B1 SELECT 已补列；后端未部署该版本前字段缺失，前端守卫不渲染 */
  context_link_mode?: 'linked' | 'independent';
}

/** B1 响应（task_queries/sessions.py list_tasks 包装：{tasks,total}） */
export interface SessionTasksResponse {
  tasks: SessionTaskItem[];
  total: number;
}

/** 产出物条目（chat_tasks.artifacts 元素 / final_stats.artifacts 同构） */
export interface TaskArtifact {
  name: string;
  path: string;
  type: string;
}

/**
 * 任务详情视图模型（C1 GET /chat/execution/task/{task_id} 经 adaptTaskDetail 适配后）
 * 【8.C-③】实测原始形状为嵌套 {task(chat_tasks 全列), tool_stats(数组!), user_message}，
 * 且 task.accumulated_usage 为 JSON 文本（SELECT * 未解析）——统一在本适配层归一。
 */
export interface TaskDetail {
  task_id: string;
  session_id: string;
  status: string;
  duration: number | null;
  total_steps: number;
  llm_call_count: number;
  retry_count: number;
  error_type: string | null;
  error_message: string | null;
  accumulated_usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  } | null;
  artifacts: TaskArtifact[] | null;
  tool_stats: Record<string, number>; // 数组→dict 归一后
}

/**
 * C1 响应适配纯函数（8.C-③）：JSON 兜底解析 accumulated_usage + tool_stats 数组转 dict。
 * 纯函数无副作用，供 StaticStatsBlock 前统一调用；解析失败静默回退空对象/null。
 */
export function adaptTaskDetail(raw: {
  task: Record<string, unknown>;
  tool_stats: Array<{ tool_name: string; call_count: number }>;
}): TaskDetail {
  const t = raw.task ?? {};
  let usage: TaskDetail['accumulated_usage'] = null;
  if (typeof t.accumulated_usage === 'string' && t.accumulated_usage) {
    try {
      usage = JSON.parse(t.accumulated_usage);
    } catch {
      usage = null; // JSON 文本损坏时兜底
    }
  } else if (t.accumulated_usage && typeof t.accumulated_usage === 'object') {
    usage = t.accumulated_usage as TaskDetail['accumulated_usage'];
  }
  const toolStats: Record<string, number> = {};
  for (const it of raw.tool_stats ?? []) {
    toolStats[it.tool_name] = it.call_count;
  }
  return {
    task_id: String(t.task_id ?? ''),
    session_id: String(t.session_id ?? ''),
    status: String(t.status ?? ''),
    duration: (t.duration as number | null) ?? null,
    total_steps: Number(t.total_steps ?? 0),
    llm_call_count: Number(t.llm_call_count ?? 0),
    retry_count: Number(t.retry_count ?? 0),
    error_type: (t.error_type as string | null) ?? null,
    error_message: (t.error_message as string | null) ?? null,
    accumulated_usage: usage,
    artifacts: (t.artifacts as TaskArtifact[] | null) ?? null,
    tool_stats: toolStats,
  };
}

/** B1 会话任务清单（sessions.py:80 → storage.list_session_tasks） */
export const sessionTaskApi = {
  listTasks: (sessionId: string): Promise<SessionTasksResponse> =>
    api.get(`/sessions/${sessionId}/tasks`).then((r) => r.data),
};

/** C1/C2 任务详情与步骤回放（chat/task_execution.py:16/:32） */
export const executionApi = {
  getTaskDetail: async (taskId: string): Promise<TaskDetail> => {
    const r = await api.get(`/chat/execution/task/${taskId}`);
    return adaptTaskDetail(r.data); // 入口即适配，消费方拿到的永远是归一形状
  },
  getTaskSteps: (
    taskId: string
  ): Promise<{ task_id: string; steps: unknown[]; count: number }> =>
    api.get(`/chat/execution/task/${taskId}/steps`).then((r) => r.data),
};

/** D1/D2 信任清单（sessions.py:88/:96；实测 {session_id,total,trusted_tools:[{tool_name,created_at}]}） */
export const trustApi = {
  getTrust: async (sessionId: string): Promise<string[]> => {
    const r = await api.get(`/sessions/${sessionId}/trust`);
    return ((r.data?.trusted_tools ?? []) as Array<{ tool_name: string }>).map(
      (x) => x.tool_name
    );
  },
  revokeTrust: (sessionId: string, toolName: string): Promise<void> =>
    api
      .delete(`/sessions/${sessionId}/trust/${encodeURIComponent(toolName)}`)
      .then(() => undefined),
};

/**
 * token 消费（A6）：GET /token-usage（根级路由，token_usage.py:42）
 * chain 口径必须传 task_id：后端按该任务 context_root_task_id 全链(含当前)求和；
 * 不传 task_id 时 chain_accumulated_tokens=null，退化为 session 全量 SUM。
 */
export interface ChainTokenLayer {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}
export interface ChainTokenResponse {
  success: boolean;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  task_accumulated_tokens: ChainTokenLayer | null;
  session_accumulated_tokens: ChainTokenLayer | null;
  chain_accumulated_tokens: ChainTokenLayer | null;
}
export const tokenUsageApi = {
  getChainTokens: async (params: {
    sessionId: string;
    taskId?: string;
  }): Promise<ChainTokenResponse> => {
    const q: string[] = [`session_id=${encodeURIComponent(params.sessionId)}`];
    if (params.taskId) q.push(`task_id=${encodeURIComponent(params.taskId)}`);
    const response = await api.get<ChainTokenResponse>(
      `/token-usage?${q.join('&')}`
    );
    return response.data;
  },
};

export default api;
