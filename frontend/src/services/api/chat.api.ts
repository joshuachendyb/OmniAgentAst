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
  status?: 'success' | 'failed' | 'warning';
}

export const chatApi = {
  validateService: async (): Promise<ValidateResponse> => {
    const response = await api.get<ValidateResponse>('/chat/validate', {
      timeout: 30000,
    });
    return response.data;
  },
};
