import api from './client';

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
