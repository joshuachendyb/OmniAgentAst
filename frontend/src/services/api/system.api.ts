// 编辑历史: 2026-11-16 小欧 - 新建: 服务优雅停机 API(前端「关闭服务」按钮) — 小欧-2026-11-16
import api from './client';

export interface ShutdownResponse {
  status: string;
}

export const systemApi = {
  /**
   * 请求后端优雅停机 — 小欧 2026-11-16
   * 成功后服务随即退出(先返回响应再置 should_exit), 调用方据此提示用户;
   * 非编程式启动(无 uvicorn Server 引用)时后端返回 503。
   */
  shutdown: async (): Promise<ShutdownResponse> => {
    const response = await api.post<ShutdownResponse>('/shutdown');
    return response.data;
  },
};
