// 编辑历史: 2026-11-02 小欧 - HealthStatus 补 host/db_status, 探活超时收口5s常量(后端僵死不再空等全局60s) — 小欧-2026-11-02
import api from './client';

// 2026-11-02 小欧 - 探活专用短超时: 后端僵死时快速报红, 不吃全局60s — 小欧-2026-11-02
const PROBE_TIMEOUT_MS = 5000;

export interface HealthStatus {
  status: string;
  timestamp: string;
  version: string;
  db_status?: string;
  /** 后端视角访问地址(Host头), 开发/打包均真实 — 2026-11-02 小欧 */
  host?: string;
  /** 本机局域网IP(他人可访问), 2026-11-02 小欧 */
  server_ip?: string;
  /** 后端进程号, 卡死时对应 py-spy dump --pid 2026-11-02 小欧 */
  pid?: number;
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
    const response = await api.get<HealthStatus>('/health', {
      timeout: PROBE_TIMEOUT_MS,
    });
    return response.data;
  },

  echo: async (message: string): Promise<EchoResponse> => {
    const response = await api.post<EchoResponse>('/echo', { message });
    return response.data;
  },
};
