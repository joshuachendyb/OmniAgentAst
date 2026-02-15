import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

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

// Chat API interfaces
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

  validateService: async (): Promise<ValidateResponse> => {
    const response = await api.get<ValidateResponse>('/chat/validate');
    return response.data;
  },

  switchProvider: async (provider: 'zhipuai' | 'opencode'): Promise<ValidateResponse> => {
    const response = await api.post<ValidateResponse>(`/chat/switch/${provider}`);
    return response.data;
  },
};

export default api;
