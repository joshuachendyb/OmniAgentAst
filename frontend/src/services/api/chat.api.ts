// 编辑历史: 2026-11-02 小欧 - ValidateResponse补status/errors/warnings(后端三级分级真供给, status原声明恒缺), 供ConfigStatusPill Tooltip明细列出 - 小欧-2026-11-02
import api from './client';

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
  valid: boolean;
  model_ref?: {
    provider: string;
    model: string;
    api_base?: string;
    display_name?: string;
  } | null;
  message: string;
  // 2026-11-02 小欧 - 可用性三级分级实装(status 原声明无后端供给, 本次后端补齐): 明细两组供 Tooltip 逐项展示
  status?: 'success' | 'failed' | 'warning';
  errors?: string[];
  warnings?: string[];
}

export const chatApi = {
  validateService: async (): Promise<ValidateResponse> => {
    const response = await api.get<ValidateResponse>('/chat/validate', {
      timeout: 30000,
    });
    return response.data;
  },
};
