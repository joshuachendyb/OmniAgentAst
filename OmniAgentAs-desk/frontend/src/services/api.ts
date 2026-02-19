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

import axios from 'axios';
import { message } from 'antd';

const API_BASE_URL = 'http://localhost:8000/api/v1';

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
 */
api.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.config.url} - ${response.status}`);
    return response;
  },
  (error) => {
    console.error('[API Response Error]', error);
    
    // 统一错误提示
    if (error.response?.status === 401) {
      message.error('API Key无效，请检查配置');
    } else if (error.response?.status === 429) {
      message.error('请求太频繁，请稍后再试');
    } else if (error.code === 'ECONNABORTED') {
      message.error('请求超时，请检查网络');
    } else {
      message.error('操作失败：' + (error.response?.data?.detail || error.message));
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
  sendMessage: async (messages: ChatMessage[], temperature: number = 0.7): Promise<ChatResponse> => {
    const response = await api.post<ChatResponse>('/chat', {
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
    const response = await api.get<ValidateResponse>('/chat/validate');
    return response.data;
  },

  /**
   * 切换AI提供商 - 已存在API
   * @author 小新
   */
  switchProvider: async (provider: 'zhipuai' | 'opencode'): Promise<ValidateResponse> => {
    const response = await api.post<ValidateResponse>(`/chat/switch/${provider}`);
    return response.data;
  },
};

// ============================================
// 配置管理接口
// @author 小新
// @update 2026-02-18 已对接真实API
// ============================================
export interface Config {
  ai_provider: 'zhipuai' | 'opencode';
  ai_model: string;
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
  ai_provider?: 'zhipuai' | 'opencode';
  zhipu_api_key?: string;
  opencode_api_key?: string;
  theme?: 'light' | 'dark';
  // 安全配置
  security?: SecurityConfig;
}

export interface ConfigValidateRequest {
  provider: 'zhipuai' | 'opencode';
  api_key: string;
}

export interface ConfigValidateResponse {
  valid: boolean;
  message: string;
  model?: string;
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
  updateConfig: async (config: ConfigUpdate): Promise<{ success: boolean; message: string }> => {
    const response = await api.put('/config', config);
    return response.data;
  },

  /**
   * 验证配置
   * @author 小新
   */
  validateConfig: async (data: ConfigValidateRequest): Promise<ConfigValidateResponse> => {
    const response = await api.post<ConfigValidateResponse>('/config/validate', data);
    return response.data;
  },
};

// ============================================
// 会话管理接口
// @author 小新
// @update 2026-02-18 已对接真实API
// ============================================
export interface Session {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
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
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  execution_steps?: ExecutionStep[];
}

export interface ExecutionStep {
  type: 'thought' | 'action' | 'observation' | 'error' | 'final';
  content?: string;
  tool?: string;
  params?: Record<string, any>;
  result?: any;
  timestamp: number;
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
   */
  createSession: async (title?: string): Promise<{ session_id: string; title: string; created_at: string; updated_at: string; message_count: number }> => {
    const response = await api.post<{ session_id: string; title: string; created_at: string; updated_at: string; message_count: number }>('/sessions', { title });
    return response.data;
  },

  /**
   * 获取会话列表
   * @author 小新
   */
  listSessions: async (page: number = 1, pageSize: number = 20, keyword?: string): Promise<SessionListResponse> => {
    const params: any = { page, page_size: pageSize };
    if (keyword) params.keyword = keyword;
    const response = await api.get<SessionListResponse>('/sessions', { params });
    return response.data;
  },

  /**
   * 获取会话消息
   * @author 小新
   */
  getSessionMessages: async (sessionId: string): Promise<{ session_id: string; messages: Message[] }> => {
    const response = await api.get<{ session_id: string; messages: Message[] }>(`/sessions/${sessionId}/messages`);
    return response.data;
  },

  /**
   * 保存消息到会话
   * @author 小新
   */
  saveMessage: async (sessionId: string, message: { role: string; content: string }): Promise<{ success: boolean }> => {
    const response = await api.post<{ success: boolean }>(`/sessions/${sessionId}/messages`, message);
    return response.data;
  },

  /**
   * 删除会话
   * @author 小新
   */
  deleteSession: async (sessionId: string): Promise<{ success: boolean }> => {
    const response = await api.delete<{ success: boolean }>(`/sessions/${sessionId}`);
    return response.data;
  },

  /**
   * 更新会话标题
   * @author 小新
   */
  updateSession: async (sessionId: string, title: string): Promise<{ success: boolean; title: string }> => {
    const response = await api.put<{ success: boolean; title: string }>(`/sessions/${sessionId}`, { title });
    return response.data;
  },
};

// ============================================
// 安全接口
// @author 小新
// @update 2026-02-19 升级到v2.0 API契约（score+message精简版）
// ============================================
import type { SecurityCheckResponse, SecurityCheckRequest, UseSecurityCheckReturn } from '../types/security';
import { getRiskLevel } from '../types/security';

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
    const response = await api.post<SecurityCheckResponse>('/security/check', { command } as SecurityCheckRequest);
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
      throw new Error(response.error || '安全检查失败');
    }

    const { score, message } = response.data;
    const riskLevel = getRiskLevel(score);

    return {
      score,
      message,
      level: riskLevel.level,
      canProceed: riskLevel.canProceed,
      ui: riskLevel.ui
    };
  },
};

export default api;
