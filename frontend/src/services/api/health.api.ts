// 编辑历史: 2026-11-02 小欧 - HealthStatus 补 host/db_status, 探活超时收口5s常量(后端僵死不再空等全局60s) — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 探活口径单一来源: 超时/慢判阈值/判据 probeAlive 全收敛于此, 删除 utils/network.ts 的 fetch+3s 重复实现(同名"网络检查"实为后端健康检查, 语义漂移) — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - checkHealth 改 _silent: 探活是"看一眼", 失败不许弹全局toast, 也不许触发拦截器的超时归因二次探测(原最多白等8s才报红) — 小欧-2026-11-02
import api from './client';
import type { ApiRequestConfig } from './client';

/**
 * 探活唯一超时 — 2026-11-02 小欧
 * 三个消费者(发送前预检 / 超时归因文案 / 顶栏服务胶囊)共用同一个值:
 *   原 utils/network.ts 用 fetch+3000、胶囊用 5000, 3~5s 窗口内"预检判死、胶囊仍绿"互相打脸。
 * 禁止在别处再写字面量; 改这里即三处同时生效。
 */
export const PROBE_TIMEOUT_MS = 5000;

/**
 * 慢判阈值(顶栏黄态) — 2026-11-02 小欧
 * 本机探活正常在 10ms 级, 超 1.5s 说明事件循环已被占死(判定手法见 AGENTS.md《Shell 卡死取证》)。
 * 属展示判据, 但与探活超时同处定义, 避免阈值散落。
 */
export const SLOW_RESPONSE_MS = 1500;

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
  /** 进程已存活秒数(重启归零, 与 pid 变化互相印证) — 2026-11-02 小欧 */
  uptime_s?: number;
  /** 事件循环调度延迟点采样(毫秒), 区分网络慢与循环被占死 — 2026-11-02 小欧 */
  loop_lag_ms?: number;
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
    // 2026-11-02 小欧 - _silent: 探活由调用方决定呈现(胶囊变红/预检早退/归因选文案), 不弹全局 toast;
    //   同时跳过拦截器的超时归因分支(那里会再探一次 /health), 失败路径不再 5s+3s 白等 — 小欧-2026-11-02
    const cfg: ApiRequestConfig = { timeout: PROBE_TIMEOUT_MS, _silent: true };
    const response = await api.get<HealthStatus>('/health', cfg);
    return response.data;
  },

  echo: async (message: string): Promise<EchoResponse> => {
    const response = await api.post<EchoResponse>('/echo', message);
    return response.data;
  },
};

/**
 * 后端此刻是否应答(boolean 语义) — 2026-11-02 小欧
 * 发送前预检与超时归因专用: 失败即 false, 绝不吃缓存 —— 缓存会把"刚死"误判成"活着",
 * 正是 2026-10-30 那批要治的病。观测(胶囊)另有 healthStatus 承担, 两者不共享结果。
 */
export const probeAlive = async (): Promise<boolean> => {
  try {
    await healthApi.checkHealth();
    return true;
  } catch {
    return false;
  }
};
