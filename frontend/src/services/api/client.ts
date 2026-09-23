import axios from 'axios';
import type {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { handleApiError } from '../error/handler';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/**
 * 获取后端 API 基础地址（不含 /api/v1 后缀）。
 *
 * ═══════════════════════════════════════════════════════════════
 * 前端→后端端口关系（两个独立进程，各跑各的端口）：
 *
 *   前端 (Vite dev server, :5173)  ──请求──→  后端 (uvicorn, :8000)
 *
 *   这是两个不同的程序，端口互相独立。
 *   前端必须知道后端在哪个端口，才能连上。
 *
 * 连接方式（二选一）：
 *   方式1 — Vite proxy（vite.config.ts:43-47）：
 *     前端请求 /api/* 由 Vite 内置 http-proxy 转发到 localhost:8000。
 *     同源（都是 :5173），无 CORS 问题。此函数返回 ''（空串）。
 *   方式2 — 直连（本函数）：
 *     前端直连后端，跨域，走 CORS。端口优先级：
 *       ① VITE_API_BASE_URL 环境变量（完整地址，如 http://localhost:9000）→ 直接用
 *       ② VITE_API_PORT 环境变量（仅端口号，如 9000）→ 拼 hostname:port
 *       ③ 都不设 → 默认 :8000（后端 uvicorn 标准端口）
 *
 * 改端口必须前后端对齐：
 *   后端改端口（如 8000→9000）→ 前端必须同步改 VITE_API_PORT=9000，否则连不上。
 *   前端改端口（如 5173→3000）→ 后端必须同步改 CORS 白名单（constants.py 或 network.cors_origins）。
 *
 * 后端端口配置方式：
 *   - uvicorn 启动参数：python -m uvicorn app.main:app --port 9000
 *   - 或修改 main.py 读取环境变量 PORT
 *
 * 编辑历史:
 *   2026-09-22 小欧 硬编码 :8000 → 读 VITE_API_PORT 环境变量（默认 8000），消除后端改端口时改代码
 */
export function getApiBaseUrl(): string {
  // 优先级1：完整地址覆盖（如 http://localhost:9000/api/v1）
  const envBase = (import.meta as unknown as { env: Record<string, string> })
    .env?.VITE_API_BASE_URL;
  if (envBase) return envBase;
  // 优先级2/3：按 hostname + 端口拼接（直连后端场景）
  if (typeof window !== 'undefined') {
    const loc = window.location;
    // VITE_API_PORT：仅端口号（如 9000），缺省 8000（后端 uvicorn 标准端口）
    const port = (import.meta as unknown as { env: Record<string, string> })
      .env?.VITE_API_PORT || '8000';
    return `${loc.protocol}//${loc.hostname}:${port}`;
  }
  // SSR/测试兜底
  return 'http://127.0.0.1:8000';
}

export function getAccessToken(): string | null {
  try {
    const raw = localStorage.getItem('omniagent_auth');
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state?.accessToken ?? parsed?.accessToken ?? null;
  } catch {
    return null;
  }
}

const api: AxiosInstance = axios.create({
  baseURL: `${getApiBaseUrl()}/api/v1`,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error) => {
    const skip401 = (error.config as unknown as { _skip401?: boolean })
      ?._skip401;
    if (error.response?.status === 401 && !skip401) {
      try {
        localStorage.removeItem('omniagent_auth');
        window.location.href = '/login';
      } catch {
        /* ignore */
      }
    }
    handleApiError(error);
    return Promise.reject(error);
  }
);

export default api;
