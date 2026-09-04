import axios from 'axios';
import type {
  AxiosInstance,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { handleApiError } from '../error/handler';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

export function getApiBaseUrl(): string {
  const envBase = (import.meta as unknown as { env: Record<string, string> })
    .env?.VITE_API_BASE_URL;
  if (envBase) return envBase;
  if (typeof window !== 'undefined') {
    const loc = window.location;
    return `${loc.protocol}//${loc.hostname}:8000`;
  }
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
