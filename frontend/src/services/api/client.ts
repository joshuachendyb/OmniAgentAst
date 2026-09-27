/**
 * 编辑历史:
 * 2026-09-26 小欧 - [72]第九章：新增 setAccessToken()，与 getAccessToken() 读写结构严格对称
 *   （同一存储键 omniagent_auth，认 zustand persist 的 {state:{accessToken}} 与裸 {accessToken}）。
 *   写入合并而非整体覆盖，免冲掉用户态其余持久化数据。连带 9.6-4：401 跳登录页。
 * 2026-09-27 小欧 - [75]5.5：提 AUTH_STORAGE_KEY（键名原散落 7 处，改键必漏）；setAccessToken
 *   收敛为"读包络 → 合并 → 单次 setItem"三步且写失败抛错（原静默吞掉，调用方无从得知）；
 *   请求拦截器新增 _skipAuth（入口查询不带已作废旧口令）；响应拦截器新增 403 分支
 *   （不跳登录页、不清口令，detail 原话交调用方呈现）。
 */
import axios from 'axios';
import type {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { handleApiError } from '../error/handler';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1';

/** 访问口令的 localStorage 键名（[75]5.5：原字面量散落 7 处，改键必漏一处）。 */
export const AUTH_STORAGE_KEY = 'omniagent_auth';

/**
 * 请求级开关。`_skip401` 提升为有类型字段（[72]A03）：改前只有"读"没有类型载体，
 * 调用方需 `as never` 硬转义，编译器全程失明。
 */
export interface ApiRequestConfig extends AxiosRequestConfig {
  /** true = 本请求 401 不执行全局「清 token + 跳 /login」（登录/鉴权通道自身用） */
  _skip401?: boolean;
  /**
   * true = 本请求不附带 Authorization 头（即使 localStorage 存有口令）。
   * 登录页入口查询 GET /auth/status 专用：默认附带的旧口令已作废时会把引导查询打成 401/403。
   * 验真查询不带此标记、照常附带（[75]4.2.3 两次查询的分工）。
   */
  _skipAuth?: boolean;
}

/** Vite 注入的环境变量（测试环境无 import.meta.env 时的类型兜底）。 */
const VITE_ENV =
  (import.meta as unknown as { env: Record<string, string> }).env ?? {};

/**
 * 后端 API 基础地址（不含 /api/v1），返回空串即"走同源相对路径"。
 *
 * 优先级：VITE_API_BASE_URL 显式地址 > 空串（同源）。
 * 空串时浏览器按当前源解析 /api/*，由 Vite proxy（开发）或 Nginx 反代（生产）转发到后端，
 * 与 API_BASE_URL 的默认值同源，两者不再分叉。
 * 仅当前后端与前端不同源且无反代时才需设 VITE_API_BASE_URL（如 http://192.168.1.10:8000）。
 *
 * 端口联动：后端改端口 → 同步 Vite proxy 的 target 与 VITE_API_PORT。
 *
 * 编辑历史:
 *   2026-09-22 小欧 硬编码 :8000 → 读 VITE_API_PORT
 *   2026-09-27 小欧 [75]BUG-6：默认由"拼 hostname:port 绝对地址"改为"空串（同源）"——
 *     原默认值使 REST（axios，绝对地址）与 SSE（fetch，'/api/v1' 相对）分属两条通道，
 *     生产同源反代部署时 REST 打到未对外的 :8000 而失败。
 */
export function getApiBaseUrl(): string {
  return VITE_ENV.VITE_API_BASE_URL || '';
}

/** 取访问口令。认 zustand persist 的 {state:{accessToken}} 与裸 {accessToken} 两种形态。 */
export function getAccessToken(): string | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.state?.accessToken ?? parsed?.accessToken ?? null;
  } catch {
    return null;
  }
}

/**
 * 写访问口令。与 getAccessToken 读写结构对称（认 {state:{accessToken}} 与裸 {accessToken}）。
 * [75]5.5：收敛为"读包络 → 合并 → 单次 setItem"三步；写失败抛错（原静默吞掉，见 [75]4.4.4）。
 */
export function setAccessToken(token: string | null): void {
  try {
    if (!token) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return;
    }
    // 保留 zustand persist 包络（{"state":{...},"version":N}）的其余字段原样回写：
    // 展平会丢 state 包裹与 version，且会与 zustand 下次持久化互相覆盖（[72]三堂会审结论）。
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    let base: Record<string, unknown> = {};
    if (raw) {
      try {
        const parsed: unknown = JSON.parse(raw);
        if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
          base = parsed as Record<string, unknown>;
        }
      } catch {
        // 存量数据损坏（corrupt JSON）→ 当全新写入。此处绝不能往外抛，
        // 否则一次损坏就让口令永远存不上（比静默失败更糟）。
      }
    }
    const wrapped = !!base.state && typeof base.state === 'object';
    localStorage.setItem(
      AUTH_STORAGE_KEY,
      JSON.stringify(
        wrapped
          ? {
              ...base,
              state: {
                ...(base.state as Record<string, unknown>),
                accessToken: token,
              },
            }
          : { ...base, accessToken: token }
      )
    );
  } catch (e) {
    // 只有真正的存储写入失败（配额满/隐私模式禁写等）才走到这 —— 必须让调用方知道，
    // 否则用户以为改成功了，下个请求带旧口令被 401 踢回登录页（见 [75]4.4.4）。
    throw new Error(
      `访问口令存取失败：${e instanceof Error ? e.message : String(e)}`
    );
  }
}

const api: AxiosInstance = axios.create({
  baseURL: `${getApiBaseUrl()}/api/v1`,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // [75]5.5：_skipAuth 的请求不附带 Authorization。专供登录页"入口查询"
    //   （[75]4.2.3 分工①）：默认附带的旧口令已作废时会把引导查询打成 401/403；
    //   验真查询不带此标记、照常附带口令（分工②）。
    if ((config as ApiRequestConfig)._skipAuth) return config;
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
    const skip401 = (error.config as ApiRequestConfig | undefined)?._skip401;
    // [75]5.5：403 独立处理，不跳登录页、不清口令，原话透传。
    //   403 语义是"你不能做这事"（如非本机要设口令），不是"口令错了"。原实现只认 401，
    //   403 一律落到 handleApiError 的泛化文案，后端返回的「只能在服务端本机进行」被丢弃。
    if (error.response?.status === 403) {
      return Promise.reject(error); // 交给调用方按后端 detail 呈现（LoginPage / SettingRow）
    }
    if (error.response?.status === 401 && !skip401) {
      // 凭据版本比对（[72]C07）：改口令前发出的长耗时请求返回 401 时，它证明的是**旧口令**
      // 无效，而内存里的新口令有效。原实现无条件清 token + 跳登录页，会出现"保存成功却被登出"
      // （用户正在输入的新口令随跳转丢失）。故只在失败凭据与当前凭据**同值**时才清。
      const failedAuth = (
        error.config as InternalAxiosRequestConfig | undefined
      )?.headers?.Authorization as string | undefined;
      const currentToken = getAccessToken();
      const isStaleCredential =
        !!currentToken &&
        !!failedAuth &&
        failedAuth !== `Bearer ${currentToken}`;
      if (!isStaleCredential) {
        try {
          localStorage.removeItem(AUTH_STORAGE_KEY);
          window.location.href = '/login';
        } catch {
          /* ignore */
        }
      }
    }
    // _skip401 = 「这次 401 是预期内的、由调用方自己处理」（[72]C08）：
    // 此时不弹全局 toast，否则与调用方的内联提示重复且矛盾。
    // [75]5.5：403 已在上方提前返回，同样不叠加全局 toast。
    handleApiError(error, skip401 ? { showError: false } : undefined);
    return Promise.reject(error);
  }
);

export default api;
