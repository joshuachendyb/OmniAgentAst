/**
 * API服务层 - api.ts
 *
 * 功能：封装所有后端API调用，统一错误处理和类型定义
 *
 * @author 小新
 * @version 2.0.0
 * @since 2026-02-17
 * @update 添加配置管理、会话管理接口 - by 小新
 */

import axios from "axios";
import { message } from "antd";
import type { ExecutionStep } from "../utils/sse";

// 【小新修复 2026-03-14】统一API地址配置，支持环境变量
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

/**
 * Axios实例配置
 *
 * 包含统一错误处理和日志记录
 */
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
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
    console.error("[API Request Error]", error);
    return Promise.reject(error);
  }
);

/**
 * 响应拦截器 - 统一错误处理
 */
api.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.config.url} - ${response.status}`);
    return response;
  },
  (error) => {
    console.error("[API Response Error]", error);

    // 统一错误提示
    if (error.response?.status === 401) {
      message.error("API Key无效，请检查配置");
    } else if (error.response?.status === 429) {
      message.error("请求太频繁，请稍后再试");
    } else if (error.code === "ECONNABORTED") {
      message.error("请求超时，请检查网络");
    } else {
      message.error(
        "操作失败：" + (error.response?.data?.detail || error.message)
      );
    }

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
    const response = await api.get<HealthStatus>("/health");
    return response.data;
  },

  echo: async (message: string): Promise<EchoResponse> => {
    const response = await api.post<EchoResponse>("/echo", { message });
    return response.data;
  },
};

// ============================================
// 对话接口
// ============================================
export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatRequest {
  messages: ChatMessage[];
  stream?: boolean;
  temperature?: number;
}

export interface ChatResponse {
  success: boolean;
  content: string;
  model: string;
  error?: string;
}

export interface ValidateResponse {
  success: boolean;
  provider: string;
  model: string;
  message: string;
}

export const chatApi = {
  sendMessage: async (
    messages: ChatMessage[],
    temperature: number = 0.7
  ): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>("/chat", {
      messages,
      stream: false,
      temperature,
    });
    return response.data;
  },

  /**
   * 验证AI服务配置 - 已存在API
   * @author 小新
   */
  validateService: async (): Promise<ValidateResponse> => {
    const response = await api.get<ValidateResponse>("/chat/validate");
    return response.data;
  },

  /**
   * 切换AI提供商 - 已存在API
   * @author 小新
   */
  switchProvider: async (
    provider: "zhipuai" | "opencode"
  ): Promise<ValidateResponse> => {
    const response = await api.post<ValidateResponse>(
      `/chat/switch/${provider}`
    );
    return response.data;
  },
};

// ============================================
// 配置管理接口
// @author 小新
// @update 2026-02-18 已对接真实API
// ============================================
export interface Config {
  ai_provider: "zhipuai" | "opencode" | "longcat";
  ai_model: string;
  api_key_configured: boolean;
  theme: "light" | "dark";
  language: string;
  // 安全配置
  security?: SecurityConfig;
}

export interface SecurityConfig {
  contentFilterEnabled: boolean;
  contentFilterLevel: "low" | "medium" | "high";
  whitelistEnabled: boolean;
  commandWhitelist: string;
  blacklistEnabled: boolean;
  commandBlacklist: string;
  confirmDangerousOps: boolean;
  maxFileSize: number;
}

export interface ConfigUpdate {
  // ⭐⭐⭐ 重要：provider 和 model 必须成对使用！⭐⭐⭐
  // 切换模型时，必须同时提供 ai_provider 和 ai_model
  // 原因：同一个 model 名称可能属于多个 provider（如 kimi-k2.5-free 可能在多个 provider 下）
  // 只有 provider+model 组合才能唯一确定一个模型
  // 设计原则：发送时两个字段，接收时两个字段，使用时两个字段必须同时使用
  ai_provider?: string;
  ai_model?: string;

  // ⭐ 修复：使用统一的 provider_api_keys，不硬编码 provider 名称
  provider_api_keys?: Record<string, string>; // {provider_name: api_key}
  theme?: "light" | "dark";
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
  current_provider: string;
  current_model: string;
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
    const response = await api.get<Config>("/config");
    return response.data;
  },

  /**
   * 更新配置
   * @author 小新
   */
  updateConfig: async (
    config: ConfigUpdate
  ): Promise<{ success: boolean; message: string }> => {
    const response = await api.put("/config", config);
    return response.data;
  },

  /**
   * 验证配置
   * @author 小新
   */
  validateConfig: async (
    data: ConfigValidateRequest
  ): Promise<ConfigValidateResponse> => {
    const response = await api.post<ConfigValidateResponse>(
      "/config/validate",
      data
    );
    return response.data;
  },

  /**
   * 验证完整配置（validate-full接口）
   * 用于启动时全面检查所有Provider和Model配置
   * @author 小欧
   * @update 2026-02-23 新增
   */
  validateFullConfig: async (): Promise<FullConfigValidationResponse> => {
    const response = await api.get<FullConfigValidationResponse>(
      "/config/validate-full"
    );
    return response.data;
  },

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
    }>("/config/models");
    return response.data;
  },

  /**
   * 获取完整配置（包含所有provider和model）
   * @author 小欧
   */
  getFullConfig: async (): Promise<FullConfigResponse> => {
    const response = await api.get<FullConfigResponse>("/config/full");
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
    const response = await api.post("/config/provider", data);
    return response.data;
  },

  /**
   * 修复配置文件常见问题
   * 自动删除provider下废弃的model字段
   * @author 小新
   * @update 2026-02-26 对接小沈新接口
   */
  fixConfig: async (): Promise<ConfigFixResponse> => {
    const response = await api.post<ConfigFixResponse>("/config/fix");
    return response.data;
  },

  /**
   * 获取配置文件路径
   * @author 小新
   * @update 2026-03-03 新增
   */
  getConfigPath: async (): Promise<ConfigPathResponse> => {
    const response = await api.get<ConfigPathResponse>("/config/path");
    return response.data;
  },

  /**
   * 打开配置文件所在目录
   * 调用系统资源管理器打开文件夹
   * @author 小新
   * @update 2026-03-04 新增
   */
  openConfigFolder: async (): Promise<{ success: boolean; path: string }> => {
    const response = await api.post<{ success: boolean; path: string }>("/config/open-folder");
    return response.data;
  },

  /**
   * 读取配置文件原文内容
   * @author 小新
   * @update 2026-03-04 新增
   */
  readConfigFile: async (): Promise<{ success: boolean; config_path: string; content: string }> => {
    const response = await api.get<{ success: boolean; config_path: string; content: string }>("/config/read");
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
  title_source: "user" | "auto"; // ⭐ 新增：标题来源（用户手动/自动生成）
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

export interface Message {
  id: number;
  session_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  execution_steps?: ExecutionStep[];
  display_name?: string; // 前端小新代修改：模型显示名称
  is_reasoning?: boolean; // 【小查修复】是否为思考过程（统一使用 snake_case）
}

// ⭐ 新增：获取会话消息响应（包含新字段）
export interface GetSessionMessagesResponse {
  session_id: string;
  title: string;
  title_locked: boolean;
  title_source: "user" | "auto";
  title_updated_at: string | null;
  version?: number;
  messages: Message[];
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
    }>("/sessions", { title, is_valid: true });
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
    isValid?: boolean  // ⭐ 新增参数：true=有效会话，false=无效会话，undefined=全部
  ): Promise<SessionListResponse> => {
    const params: any = { page, page_size: pageSize };
    if (keyword) params.keyword = keyword;
    if (isValid !== undefined) params.is_valid = isValid;  // ⭐ 新增
    const response = await api.get<SessionListResponse>("/sessions", {
      params,
    });
    return response.data;
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
      title_source: response.data.title_source ?? "auto",
      title_updated_at: response.data.title_updated_at ?? null,
      version: response.data.version ?? 1,
    };
  },

  /**
   * 保存消息到会话
   * @author 小新
   * @update 2026-03-11: 添加 execution_steps 参数
   * @update 2026-03-14: 添加错误相关字段（使用API文档字段名 - snake_case）
   */
  saveMessage: async (
    sessionId: string,
    message: {
      role: string;
      content: string;
      execution_steps?: any[];
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
    }
  ): Promise<{ success: boolean }> => {
    const response = await api.post<{ success: boolean }>(
      `/sessions/${sessionId}/messages`,
      message
    );
    return response.data;
  },

  /**
   * 保存执行步骤到会话
   * @author 小新
   * @update 2026-03-06 新增：用于保存AI思考过程的执行步骤
   * @update 2026-03-16 修正：增加content参数，支持在visibilitychange时同时保存content
   * 修正原因：SSE数据保存方案-综合版第18章要求，visibilitychange时需要同时保存
   *          execution_steps和content，后端API需要支持content参数
   */
  saveExecutionSteps: async (
    sessionId: string,
    executionSteps: any[],
    content?: string  // 新增：可选的content参数，用于保存AI回复内容
  ): Promise<{ success: boolean }> => {
    const response = await api.post<{ success: boolean }>(
      `/sessions/${sessionId}/execution_steps`,
      { 
        execution_steps: executionSteps,
        ...(content !== undefined && { content })  // 有值才传递
      }
    );
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
    version: number // ⭐ 必须参数：版本号
  ): Promise<UpdateSessionResponse> => {
    const response = await api.put<UpdateSessionResponse>(
      `/sessions/${sessionId}`,
      {
        title,
        version, // ⭐ 必须传递
        updated_by: "user", // ⭐ 可选：标记用户修改
      }
    );
    return response.data;
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
      throw new Error("会话ID列表不能为空");
    }

    // 验证2：检查数组长度（最多50个）
    if (sessionIds.length > 50) {
      throw new Error("批量获取标题最多支持50个会话ID");
    }

    // 验证3：检查每个ID的有效性并过滤
    const validIds = sessionIds.filter((id) => id && id.trim());
    if (validIds.length === 0) {
      throw new Error("没有有效的会话ID");
    }

    // 验证4：检查URL长度
    const url = `/sessions/titles/batch?session_ids=${validIds.join(",")}`;
    if (url.length > 2000) {
      throw new Error("请求URL过长，请减少会话数量");
    }

    const response = await api.get<BatchTitleResponse>(url);
    return response.data;
  },
};

// ============================================
// 安全接口
// @author 小新
// @update 2026-02-19 升级到v2.0 API契约（score+message精简版）
// ============================================
import type {
  SecurityCheckResponse,
  SecurityCheckRequest,
  UseSecurityCheckReturn,
} from "../types/security";
import { getRiskLevel } from "../types/security";

/**
 * 安全API v2.0
 * 基于阶段2.1危险等级设计文档第4章契约接口
 *
 * @author 小新
 * @version 2.0.0
 * @update 2026-02-19 升级到精简版API（score+message）
 */
export const securityApi = {
  /**
   * 检查命令安全性
   * 调用后端 /api/v1/security/check 接口
   *
   * @param command 要检查的命令
   * @returns 安全检测结果（包含score和message）
   * @author 小新
   */
  checkCommand: async (command: string): Promise<SecurityCheckResponse> => {
    const response = await api.post<SecurityCheckResponse>("/security/check", {
      command,
    } as SecurityCheckRequest);
    return response.data;
  },

  /**
   * 检查命令并解析风险等级
   * 封装checkCommand，返回更详细的解析结果
   *
   * @param command 要检查的命令
   * @returns 解析后的风险等级信息
   * @author 小新
   */
  checkWithLevel: async (command: string): Promise<UseSecurityCheckReturn> => {
    const response = await securityApi.checkCommand(command);

    if (!response.success || !response.data) {
      throw new Error(response.error || "安全检查失败");
    }

    const { score, message } = response.data;
    const riskLevel = getRiskLevel(score);

    return {
      score,
      message,
      level: riskLevel.level,
      canProceed: riskLevel.canProceed,
      ui: riskLevel.ui,
    };
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
 * 分页数据响应类型
 */
interface NextPageResponse {
  success: boolean;
  data?: any;
  next_page_token?: string;
  has_more: boolean;
}

/**
 * 用户确认请求类型
 */
interface ConfirmRequest {
  task_id: string;
  confirmed: boolean;
  modified_command?: string;
}

/**
 * 分页数据请求类型
 */
interface NextPageRequest {
  task_id: string;
  tool_name: string;
  next_page_token: string;
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
   * @returns 取消结果
   */
  cancel: async (taskId: string): Promise<TaskControlResponse> => {
    const response = await api.post<TaskControlResponse>(`/chat/stream/cancel/${taskId}`);
    return response.data;
  },

  /**
   * 暂停任务
   * POST /api/v1/chat/stream/pause/{task_id}
   * 
   * @param taskId 任务ID
   * @returns 暂停结果
   */
  pause: async (taskId: string): Promise<TaskControlResponse> => {
    const response = await api.post<TaskControlResponse>(`/chat/stream/pause/${taskId}`);
    return response.data;
  },

  /**
   * 恢复任务
   * POST /api/v1/chat/stream/resume/{task_id}
   * 
   * @param taskId 任务ID
   * @returns 恢复结果
   */
  resume: async (taskId: string): Promise<TaskControlResponse> => {
    const response = await api.post<TaskControlResponse>(`/chat/stream/resume/${taskId}`);
    return response.data;
  },

  /**
   * 用户确认操作
   * POST /api/v1/chat/stream/confirm
   * 
   * @param taskId 任务ID
   * @param confirmed 用户选择：true=确认执行，false=拒绝执行
   * @param modifiedCommand 可选，修改后的命令
   * @returns 确认结果
   */
  confirm: async (
    taskId: string, 
    confirmed: boolean, 
    modifiedCommand?: string
  ): Promise<TaskControlResponse> => {
    const body: ConfirmRequest = {
      task_id: taskId,
      confirmed: confirmed,
    };
    
    if (modifiedCommand) {
      body.modified_command = modifiedCommand;
    }
    
    const response = await api.post<TaskControlResponse>('/chat/stream/confirm', body);
    return response.data;
  },

  /**
   * 请求分页数据
   * POST /api/v1/chat/stream/next-page
   * 
   * @param taskId 任务ID
   * @param toolName 工具名称
   * @param nextPageToken 分页令牌
   * @returns 分页数据结果
   */
  nextPage: async (
    taskId: string, 
    toolName: string, 
    nextPageToken: string
  ): Promise<NextPageResponse> => {
    const body: NextPageRequest = {
      task_id: taskId,
      tool_name: toolName,
      next_page_token: nextPageToken,
    };
    
    const response = await api.post<NextPageResponse>('/chat/stream/next-page', body);
    return response.data;
  },
};

export default api;
