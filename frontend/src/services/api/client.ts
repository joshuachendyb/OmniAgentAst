/**
 * 编辑历史:
 * 2026-09-26 小欧 - 新增 setAccessToken()，与 getAccessToken() 读写结构严格对称
 *   （同一存储键 omniagent_auth，认 zustand persist 的 {state:{accessToken}} 与裸 {accessToken}）。
 *   写入合并而非整体覆盖，免冲掉用户态其余持久化数据。连带 401 跳登录页。
 * 2026-09-27 小欧 - 提 AUTH_STORAGE_KEY（键名原散落 7 处，改键必漏）；setAccessToken
 *   收敛为"读包络 → 合并 → 单次 setItem"三步且写失败抛错（原静默吞掉，调用方无从得知）；
 *   请求拦截器新增 _skipAuth（入口查询不带已作废旧口令）；响应拦截器新增 403 分支
 *   （不跳登录页、不清口令，detail 原话交调用方呈现）。
 * 2026-10-11 小欧 - 修复打包版全站 404：北京老陈驱动。API_BASE_URL 原为
 *   `import.meta.env.VITE_API_BASE_URL || '/api/v1'` —— 默认值含 /api/v1 前缀，但被 env 覆盖时
 *   是裸源地址，同一变量被当「含前缀」与「裸源地址」两种语义使用：axios baseURL 走后者
 *   （`${getApiBaseUrl()}/api/v1`），而 network.ts / main.tsx / ChatPage.tsx 走前者
 *   （`${API_BASE_URL}/health`、`${cfg.baseURL}/chat/stream`）。故显式设 VITE_API_BASE_URL 打生产包时，
 *   /health 与 /chat/stream 全部少一段前缀而 404，前端报"网络连接异常"。
 *   改法：API_BASE_URL 统一为 `${getApiBaseUrl()}/api/v1`（复用既有 getApiBaseUrl，与 axios baseURL
 *   完全同源），并删掉重复定义的一份 VITE_ENV。dev 未设 env 时仍得 '/api/v1'，走 Vite proxy，
 *   调试行为零变化。
 * 2026-10-30 小欧 - 请求计时与诊断、超时探活文案、_silent 静默与幂等 GET 单次重试；
 *   新增 HEAVY_READ_TIMEOUT_MS 供重读接口放宽到 120s。
 */
import axios from 'axios';
import type {
  AxiosInstance,
  AxiosRequestConfig,
  AxiosResponse,
  InternalAxiosRequestConfig,
} from 'axios';
import { handleApiError } from '../error/handler';
import type { RequestDiagnostics } from '../error/handler'; // 2026-10-30 小欧 - 诊断上下文类型
// 2026-10-30 小欧 - 超时探活复用既有 /health 检查(3s 超时), 不另写探测
import { checkNetworkConnection } from '../../utils/network';

/** Vite 注入的环境变量（测试环境无 import.meta.env 时的类型兜底）。 */
const VITE_ENV =
  (import.meta as unknown as { env: Record<string, string> }).env ?? {};

/**
 * 后端 API 基础地址（**含 `/api/v1` 前缀**）。
 *
 * 2026-10-11 小欧 - 修复打包版全站 404：本常量原默认值 `/api/v1`、被 env 覆盖时却是裸源地址，
 *   同一变量被当"含前缀"与"裸源地址"两种语义使用（axios baseURL 走后者，network/ChatPage 走前者），
 *   于是显式设 VITE_API_BASE_URL 打生产包时，/health 与 /chat/stream 全部少一段前缀而 404。
 *   现统一为"含前缀"单一口径，与 axios baseURL（同为 `${getApiBaseUrl()}/api/v1`）完全同源。
 *   dev 环境未设 env 时仍得 `/api/v1`，走 Vite proxy，**调试行为零变化**。
 */
export const API_BASE_URL = `${getApiBaseUrl()}/api/v1`;

/** 访问口令的 localStorage 键名（原字面量散落 7 处，改键必漏一处）。 */
export const AUTH_STORAGE_KEY = 'omniagent_auth';

/**
 * 请求级开关。`_skip401` 提升为有类型字段：改前只有"读"没有类型载体，
 * 调用方需 `as never` 硬转义，编译器全程失明。
 */
export interface ApiRequestConfig extends AxiosRequestConfig {
  /** true = 本请求 401 不执行全局「清 token + 跳 /login」（登录/鉴权通道自身用） */
  _skip401?: boolean;
  /**
   * true = 本请求不附带 Authorization 头（即使 localStorage 存有口令）。
   * 登录页入口查询 GET /auth/status 专用：默认附带的旧口令已作废时会把引导查询打成 401/403。
   * 验真查询不带此标记、照常附带（两次查询的分工）。
   */
  _skipAuth?: boolean;
  /** 2026-10-30 小欧 - true = 调用方已自行提示, 本请求失败不弹全局 toast */
  _silent?: boolean;
  /** 2026-10-30 小欧 - true = 已做过一次静默重试, 防无限重试 */
  _retried?: boolean;
  /** 2026-10-30 小欧 - 请求发出时刻(performance.now), 响应侧据此算真实耗时 */
  _startedAt?: number;
}

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
 *   2026-09-22 小欧 硬编码 :8000 → 读 VITE_API_PORT
 *   2026-09-27 小欧 默认由"拼 hostname:port 绝对地址"改为"空串（同源）"——
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
 * 收敛为"读包络 → 合并 → 单次 setItem"三步；写失败抛错（原静默吞掉，调用方无从得知）。
 */
export function setAccessToken(token: string | null): void {
  try {
    if (!token) {
      localStorage.removeItem(AUTH_STORAGE_KEY);
      return;
    }
    // 保留 zustand persist 包络（{"state":{...},"version":N}）的其余字段原样回写：
    // 展平会丢 state 包裹与 version，且会与 zustand 下次持久化互相覆盖。
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
    // 否则用户以为改成功了，下个请求带旧口令被 401 踢回登录页。
    throw new Error(
      `访问口令存取失败：${e instanceof Error ? e.message : String(e)}`
    );
  }
}

/** 慢请求留痕阈值 — 小欧 2026-10-30: 原实现只有失败才打日志, "慢但没超时"完全不可见 */
const SLOW_LOG_THRESHOLD_MS = 5000;

/** 取一个响应头的字符串值 — 小欧 2026-10-30
 *  AxiosHeaders 的键名取决于服务端原始大小写(未命中已有键时按原名存),
 *  下标直取只在浏览器把小写名回传时才成立 → 优先用 .get()(大小写无关), 再退回下标。 */
const headerValue = (h: unknown, name: string): string | undefined => {
  const get = (h as { get?: (k: string) => unknown })?.get;
  const v =
    typeof get === 'function'
      ? get.call(h, name)
      : (h as Record<string, string> | undefined)?.[name];
  return typeof v === 'string' && v ? v : undefined;
};

/** 取本请求的可诊断上下文(URL/耗时/请求ID), 只进 console — 小欧 2026-10-30
 *  入参可以是 AxiosResponse(成功) 或 axios error(失败): 两者都带 config, 请求ID 分别在
 *  顶层 headers 与 response.headers。
 *  注意: 超时失败没有 response, requestId 为 undefined —— 此时与后端对账只能靠
 *  URL + 耗时 + 时间窗, 本函数照实返回空值, 不猜。 */
const describeRequest = (src: unknown): RequestDiagnostics => {
  const s = src as {
    config?: ApiRequestConfig;
    headers?: unknown;
    response?: { headers?: unknown };
  };
  const cfg = s?.config;
  return {
    url: `${cfg?.method?.toUpperCase() ?? 'GET'} ${cfg?.url ?? '-'}`,
    elapsedMs:
      cfg?._startedAt !== undefined
        ? Math.round(performance.now() - cfg._startedAt)
        : undefined,
    requestId:
      headerValue(s?.response?.headers, 'x-request-id') ??
      headerValue(s?.headers, 'x-request-id'),
  };
};

/** 慢请求留痕: >= SLOW_LOG_THRESHOLD_MS 才打, 避免刷屏 — 小欧 2026-10-30 */
const logIfSlow = (diag: RequestDiagnostics): void => {
  if (diag.elapsedMs !== undefined && diag.elapsedMs >= SLOW_LOG_THRESHOLD_MS) {
    console.warn(
      `[SlowReq] ${diag.url} ${diag.elapsedMs}ms req=${diag.requestId ?? '-'}`
    );
  }
};

/**
 * 重读接口（目录树/文件正文/外部树）独立超时 — 小欧 2026-10-30
 * 为什么: 本机实测 depth=3 树 0.55s, 但项目根指到网络盘/大仓时可达数十秒;
 *   原全局 60s 对这类"天生慢"的只读接口过紧, 会把正常慢读报成"后端响应超时"。
 * 为什么只放宽不放窄: 收窄快接口超时会凭空增加误报, 无收益(YAGNI)。
 */
export const HEAVY_READ_TIMEOUT_MS = 120_000;

const api: AxiosInstance = axios.create({
  baseURL: `${getApiBaseUrl()}/api/v1`,
  timeout: 60_000,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // 2026-10-30 小欧 - 记发出时刻(含排队), 响应侧算真实耗时;
    //   重试请求沿用首次尝试的起点(否则 [SlowReq] 只记重试那一段, 低估用户实际等待)
    if ((config as ApiRequestConfig)._startedAt === undefined) {
      (config as ApiRequestConfig)._startedAt = performance.now();
    }
    // _skipAuth 的请求不附带 Authorization。专供登录页"入口查询"：
    //   默认附带的旧口令已作废时会把引导查询打成 401/403；验真查询不带此标记、照常附带口令。
    if ((config as ApiRequestConfig)._skipAuth) return config;
    const token = getAccessToken();
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

/** 超时提示: 后端活着(排队/慢) — 小欧 2026-10-30
 *  措辞不承诺"原请求在处理": /health 通只证明进程活着, 不证明该请求在被处理 */
const TIMEOUT_HINT_BUSY = '后端仍在处理，请稍候重试';
/** 超时提示: 后端未响应 — 小欧 2026-10-30
 *  探测 false 有三种成因(进程不在/重启中/本页连接被占满), 文案列全、不下断言 */
const TIMEOUT_HINT_DOWN =
  '后端未响应：可能服务未运行或连接被占满，请稍后重试或检查服务';

/** 是否超时(axios 超时=ECONNABORTED; 部分环境只有 message 含 timeout) — 小欧 2026-10-30
 *  加 `!response` 守卫 —— 超时的定义就是**后端没答**,
 *  有 response 的失败必须保留后端原文(如 detail 含 "timeout" 的业务报错), 不能被探活文案覆盖。 */
const isTimeoutError = (error: unknown): boolean => {
  const e = error as {
    code?: string;
    message?: string;
    response?: unknown;
  };
  if (e?.response) return false;
  return e?.code === 'ECONNABORTED' || /timeout/i.test(e?.message ?? '');
};

/** 幂等 GET 抖动单次重试的等待时间 — 小欧 2026-10-30 */
const RETRY_ONCE_DELAY_MS = 1000;

/** 连接层失败码: 请求没到达后端(链路/端口/DNS 抖动), 重试可能落到健康的后端 — 小欧 2026-10-30
 *  与超时严格区分: 超时说明后端**收到了**但没在期限内答完, 重试是给已饱和的后端再加一份压力。 */
const RETRYABLE_NET_CODES = [
  'ERR_NETWORK',
  'ECONNRESET',
  'ECONNREFUSED',
  'ENOTFOUND',
  'EAI_AGAIN',
];

/** 幂等 GET 且「连接层失败」→ 允许静默重试一次 — 小欧 2026-10-30
 *
 *  为什么不重试超时(按系统全局最优的取舍):
 *    ① 超时通常是后端被占满(慢查询/大库写放大), 再打一次等于把 60s 等待变成 121s,
 *       同时给已经饱和的后端再压一份负载 —— 重试放大, 是雪崩的加速器;
 *    ② 用户视角更差: 原本 60s 就有明确文案, 重试后要干等两倍时间才知道结果;
 *    ③ 真正能靠重试自愈的是「请求根本没到后端」的链路抖动, 那类失败**立即**返回, 重试成本极低。
 *  故本函数只认连接层失败, 超时一律交给探活 + 文案分支。 */
const canRetryOnce = (error: unknown, cfg?: ApiRequestConfig): boolean => {
  if (!cfg || cfg._retried) return false;
  if ((cfg.method ?? 'get').toLowerCase() !== 'get') return false;
  if (cfg.signal?.aborted) return false;
  // 有 response = 后端已明确答复(4xx/5xx), 重试只会把同一个错误再打一遍
  if ((error as { response?: unknown })?.response) return false;
  // 超时不在重试范围(理由见上)
  if (isTimeoutError(error)) return false;
  const e = error as { code?: string; message?: string };
  if (e?.code && RETRYABLE_NET_CODES.includes(e.code)) return true;
  return /network|fetch|econnreset/i.test(e?.message ?? '');
};

api.interceptors.response.use(
  (response: AxiosResponse) => {
    // 2026-10-30 小欧 - 成功的慢请求也要留痕(原实现只有失败才打日志)
    logIfSlow(describeRequest(response));
    return response;
  },
  // 2026-10-30 小欧 - 错误回调改 async —— 超时分支要 await /health 探测
  async (error) => {
    const cfg = error.config as ApiRequestConfig | undefined;
    const skip401 = cfg?._skip401;
    // 403 独立处理，不跳登录页、不清口令，原话透传。
    //   403 语义是"你不能做这事"（如非本机要设口令），不是"口令错了"。原实现只认 401，
    //   403 一律落到 handleApiError 的泛化文案，后端返回的「只能在服务端本机进行」被丢弃。
    if (error.response?.status === 403) {
      return Promise.reject(error); // 交给调用方按后端 detail 呈现（LoginPage / SettingRow）
    }
    if (error.response?.status === 401 && !skip401) {
      // 凭据版本比对：改口令前发出的长耗时请求返回 401 时，它证明的是**旧口令**
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
    // 2026-10-30 小欧 - 诊断上下文(URL/耗时/请求ID), 不改变控制流
    const diag = describeRequest(error);
    logIfSlow(diag);

    // 2026-10-30 小欧 - 幂等 GET「连接层失败」单次静默重试(重试成功则用户无感)
    //   放在 _silent 判定**之前**: 静默请求同样值得自愈(如 @ 搜索), 重试仍失败会继续落到下面
    //   的 _silent 分支(不弹 toast), 语义不变。超时/写请求/有响应/已取消 一律不重试(见 canRetryOnce)
    if (canRetryOnce(error, cfg)) {
      await new Promise((resolve) => setTimeout(resolve, RETRY_ONCE_DELAY_MS));
      return api.request({ ...cfg, _retried: true } as ApiRequestConfig);
    }

    // 2026-10-30 小欧 - 调用方已自行提示(_silent) 或 预期内 401(_skip401) → 不弹全局 toast
    if (skip401 || cfg?._silent) {
      handleApiError(error, { showError: false, diag });
      return Promise.reject(error);
    }

    // 2026-10-30 小欧 - 超时探一次 /health, 结果只用来选文案(不下"服务已停止"的断言)
    //   传 API_BASE_URL(含 /api/v1): network.ts 内部拼 `${base}/health`, 与 useChatSend.ts:146 同款传参
    if (isTimeoutError(error)) {
      const alive = await checkNetworkConnection(API_BASE_URL);
      handleApiError(error, {
        message: alive ? TIMEOUT_HINT_BUSY : TIMEOUT_HINT_DOWN,
        diag,
      });
      return Promise.reject(error);
    }

    handleApiError(error, { diag });
    return Promise.reject(error);
  }
);

export default api;
