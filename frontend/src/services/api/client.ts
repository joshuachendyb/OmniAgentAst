/**
 * 编辑历史:
 * 2026-09-26 - 小欧 - [72]第九章(9.5.3 第4步/9.6-2) 新增 setAccessToken()：登录页输入的访问口令
 *   经此写入 localStorage，与既有 getAccessToken() 的读取结构严格对称（同一存储键 omniagent_auth，
 *   同时认 zustand persist 的 {state:{accessToken}} 与裸 {accessToken} 两种形态）。
 *   为何不新造第二个存储键：读端已存在且真实生效（request 拦截器确实附带 Authorization: Bearer），
 *   另起一键会造出"读 A 写 B"的静默失效——那才是真 bug（写进去读不到，登录态看似成功实则无效）。
 *   写入时保留既有其它字段（合并而非整体覆盖），免冲掉用户态里其余持久化数据。
 *   连带 9.6-4: 401 时跳登录页，闭环"输错口令进不来 → 改口令 → 旧口令立即作废"。— 小欧 2026-09-26
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

/**
 * 2026-09-26 - 小沈(三遍复核) - 把 `_skip401` 提升为**有类型的请求配置字段**（A03 配套）。
 *   改前该标记只有"读"（响应拦截器 `error.config as unknown as {_skip401?}`）而**无类型载体**，
 *   调用方要传就得写 `as never` 硬转义 —— 编译器全程失明，写错键名/写错类型一律不报。
 *   现导出本接口，调用方 `api.get(url, { _skip401: true } satisfies ApiRequestConfig)` 即可，
 *   拦截器侧也改读本类型，双向受检。语义不变：仅"本次请求的 401 不触发清 token + 跳登录页"。
 */
export interface ApiRequestConfig extends AxiosRequestConfig {
  /** true = 本请求收到 401 时不执行全局「清 token + 跳 /login」（登录/鉴权通道自身用） */
  _skip401?: boolean;
}

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
    const port =
      (import.meta as unknown as { env: Record<string, string> }).env
        ?.VITE_API_PORT || '8000';
    return `${loc.protocol}//${loc.hostname}:${port}`;
  }
  // SSR/测试兜底
  return 'http://127.0.0.1:8000';
}

/**
 * 取访问口令（token）— [72]第九章(9.6-2) 核实结论：此逻辑**已存在且真实生效**
 *   （request 拦截器确实会附带 `Authorization: Bearer <token>`），本次实施只补 setAccessToken。
 */
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

/**
 * 写访问口令 — [72]第九章(9.5.3) 新建：登录页输入后写入，与 getAccessToken 的读取结构对称
 *   （兼容 zustand persist 的 {state:{accessToken}} 与裸 {accessToken} 两种形态）。
 */
export function setAccessToken(token: string | null): void {
  try {
    if (!token) {
      localStorage.removeItem('omniagent_auth');
      return;
    }
    // 2026-09-26 - 小欧 - [72]三堂会审后修正（修包络破坏）:
    //   原写法把 zustand persist 包络 `{"state":{...},"version":1}` 展平回写为顶层对象，
    //   `state` 包裹与 `version` 双双丢失。读端靠 `??` 侥幸兼容，但包络已坏：
    //   zustand 下次持久化会与残留顶层字段互相覆盖，且 corrupt 非对象 JSON 时
    //   `parsed.accessToken = token` 在严格模式抛异常 → catch 吞掉 → 口令**没存上**（静默失败）。
    //   现按原包络回写：有 state 写回 state 内（包络其余字段原样保留），裸对象则合并顶层，
    //   非对象/解析失败则全新写入。getAccessToken 的双形态读取与此严格对称。
    const raw = localStorage.getItem('omniagent_auth');
    if (raw) {
      try {
        const p: unknown = JSON.parse(raw);
        if (p && typeof p === 'object' && !Array.isArray(p)) {
          const obj = p as Record<string, unknown>;
          if (obj.state && typeof obj.state === 'object') {
            localStorage.setItem(
              'omniagent_auth',
              JSON.stringify({
                ...obj,
                state: {
                  ...(obj.state as Record<string, unknown>),
                  accessToken: token,
                },
              })
            );
            return;
          }
          localStorage.setItem(
            'omniagent_auth',
            JSON.stringify({ ...obj, accessToken: token })
          );
          return;
        }
      } catch {
        /* 解析失败则走全新写入 */
      }
    }
    localStorage.setItem(
      'omniagent_auth',
      JSON.stringify({ accessToken: token })
    );
  } catch {
    /* ignore */
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
    const skip401 = (error.config as ApiRequestConfig | undefined)?._skip401;
    if (error.response?.status === 401 && !skip401) {
      // 2026-09-26 - 小欧 - 修 C07「401 拦截器无差别清 token，误杀刚设的新口令」（三遍核实确认成立）：
      //   原实现对任何 401 无条件 `removeItem('omniagent_auth') + location='/login'`。
      //   危险时序（用户可在设置页改口令，与本文件 A04/C04 修复后的常规流量并存）：
      //     t0 请求 R 发出，带的是**旧口令**（长耗时，如 SSE/测试连接/大模型列表）；
      //     t1 用户改口令成功 → setAccessToken(新口令) 已写入 localStorage；
      //     t2 R 返回 401 —— 它证明的是**旧口令无效**，而旧口令本就已被作废，
      //        此时内存里的新口令是完全有效的；拦截器却把它一起清掉并跳登录页。
      //   后果：口令改成功了，用户却被踢回登录页、必须重新输新口令（且若他此时正在输入新口令，
      //   输入内容随页面跳转一并丢失）——「保存成功」与「被登出」同时发生，自相矛盾。
      //   修法：只清"这次失败所凭据的那个 token"——比对失败请求实际带的 Authorization 与当前
      //   内存 token，两者不同即说明用户已换过口令、旧口令的失败是过期信息，**不动当前状态**。
      //   同值才清（真·当前凭据被拒）。这是标准的"凭据版本比对"，不引入任何新状态。
      //   —— 编辑：小欧 2026-09-26
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
          localStorage.removeItem('omniagent_auth');
          window.location.href = '/login';
        } catch {
          /* ignore */
        }
      }
    }
    // 2026-09-26 - 小欧 - 修 C08「_skip401 只挡跳转、仍弹全局 toast」（三遍核实确认成立）：
    //   `_skip401` 的语义本就是"这次 401 是预期内的、由调用方自己处理"，但原实现只跳过了
    //   清除+跳转，**紧接着仍无条件调 handleApiError(error)**（默认 showError=true）⇒
    //   auth 通道的 401 照样弹全局错误 toast。真实后果：用户在登录页输错口令，
    //   页面自己有内联提示，同时又弹一个全局 toast（"服务器内部错误/网络错误"之类），
    //   两个提示内容不一致甚至矛盾；改口令时被后端 409/400 拒绝同理。
    //   修法：_skip401 时以 showError:false 调用 —— 调用方（LoginPage / SettingRow）本就持有
    //   该请求的上下文与自有提示，此处不再叠加全局 toast。errorType/deleteMessage 等
    //   handleApiError 的其它返回值不受影响。
    //   —— 编辑：小欧 2026-09-26
    handleApiError(error, skip401 ? { showError: false } : undefined);
    return Promise.reject(error);
  }
);

export default api;
