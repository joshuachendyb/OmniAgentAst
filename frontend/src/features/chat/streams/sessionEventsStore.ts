/**
 * sessionEventsStore — 全局生命周期事件流（SSE，全局仅 1 条连接）— 商量 2026-11-24
 *
 * 职责：订阅后端 GET /chat/events，接收"变更信封"（任务起停 / 状态变更 / HITL 待处理），
 *   驱动前端即时接流，替代 ChatPage 每 3 秒查 SQLite 轮询发现"续跑新任务"。
 *
 * 与 chatStreamTransport 的分工（不可合并）：
 *   本文件        = 变更通知：无 seq、不落库、**允许丢**、不承载 AI 正文；
 *   chatStream*   = 任务内容：seq + Journal + after_seq 续传，不许丢。
 *   可靠性模型 = 信封可丢 + 重连对账（onReconnected 回调里拉权威快照比对锚点）。
 *
 * 无 seq 依赖的原因：信封只是"变了"的信号，真相永远在 DB/内容流里；
 *   故断线最多导致"晚一点知道"，不会导致数据缺失。
 *
 * 编辑历史: 2026-11-24 商量 - 新建: 全局生命周期事件流 store, 订阅 SSE 信封 + 即时对账兜底
 */
import { API_BASE_URL, getAccessToken } from '@/services/api/client';

/** 信封类型 —— 与后端 event_bus.py 的事件常量一一对应，改名须同步两端 */
export type LifecycleEventType =
  | 'ready'
  | 'ping'
  | 'task_started'
  | 'task_ended'
  | 'task_status_changed'
  | 'hitl_pending'
  | 'hitl_settled';

export interface LifecycleEvent {
  event_id: number;
  type: LifecycleEventType;
  session_id: string | null;
  data: Record<string, unknown>;
}

type Handler = (ev: LifecycleEvent) => void;

/** 后端心跳 20s；前端 45s 未收到任何帧即判"假死"（TCP 活着但不给数据）主动重连 */
const HEARTBEAT_TIMEOUT_MS = 45_000;
const WATCHDOG_TICK_MS = 5_000;
const RETRY_BASE_MS = 1_000;
const RETRY_MAX_MS = 15_000;
/** 建连后多久拿不到响应头视为失败（与 chatStreamTransport.HEADER_TIMEOUT 同量级但更短：
 *  事件流首帧应立刻到，不必等 AI 生成） */
const HEADER_TIMEOUT_MS = 15_000;

const handlers = new Set<Handler>();
/** 重连成功后的对账回调集合（接入方注册：拉权威快照比对锚点）。
 *  用集合而非单例：会话页与壳层可能各自需要不同粒度的对账，互不覆盖。 */
const reconcileHandlers = new Set<() => void>();

let controller: AbortController | null = null;
let running = false;
let attempt = 0;
/** 已处理的最大 event_id（重连补发起点）；0 = 从 ring 最旧开始 */
let lastEventId = 0;
/** 总线纪元：后端进程重启后变化，变化即丢弃 lastEventId（旧 id 对新总线无意义） */
let epoch: number | null = null;
let lastRecvAt = 0;
let watchdogTimer: number | null = null;
let retryTimer: number | null = null;
let headerTimer: number | null = null;

function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function clearTimers(): void {
  if (watchdogTimer !== null) {
    window.clearInterval(watchdogTimer);
    watchdogTimer = null;
  }
  if (retryTimer !== null) {
    window.clearTimeout(retryTimer);
    retryTimer = null;
  }
  if (headerTimer !== null) {
    window.clearTimeout(headerTimer);
    headerTimer = null;
  }
}

function emit(ev: LifecycleEvent): void {
  handlers.forEach((h) => {
    try {
      h(ev);
    } catch (e) {
      // 单个消费者异常不得影响其他消费者与连接本身
      console.warn('[sessionEvents] handler 异常:', e);
    }
  });
}

function handleFrame(ev: LifecycleEvent): void {
  lastRecvAt = Date.now();
  if (ev.type === 'ready') {
    const be = Number((ev.data as { epoch?: unknown }).epoch ?? 0);
    if (epoch !== null && be !== epoch) {
      // 后端进程重启 → 旧 event_id 对新总线无意义，从头收；对账会补齐断线期间事实
      lastEventId = 0;
    }
    epoch = be;
    return; // ready 不下发业务消费者
  }
  if (ev.type === 'ping') return; // 纯传输层保活
  if (ev.event_id > lastEventId) lastEventId = ev.event_id;
  emit(ev);
}

/** 读流：按行拆 data: 帧（与 chatStreamTransport 的 processSSEData 同风格，但独立解析器：
 *  本流的 type 在 JSON 内而非 event: 行，故不复用其解析） */
async function pump(body: ReadableStream<Uint8Array>): Promise<void> {
  const reader = body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buf = '';
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      buf += decoder.decode();
      if (buf.trim()) {
        for (const line of buf.split('\n')) feedLine(line);
      }
      return;
    }
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop() ?? '';
    for (const line of lines) feedLine(line);
  }
}

function feedLine(line: string): void {
  if (!line.startsWith('data:')) return;
  const raw = line.slice(5).trim();
  if (!raw) return;
  try {
    handleFrame(JSON.parse(raw) as LifecycleEvent);
  } catch {
    // 半帧/损坏帧丢弃即可（下一帧或对账会自愈）
  }
}

function scheduleReconnect(): void {
  if (!running) return;
  if (retryTimer !== null) return;
  attempt += 1;
  const delay = Math.min(RETRY_BASE_MS * 2 ** (attempt - 1), RETRY_MAX_MS);
  console.info(`[sessionEvents] ${delay}ms 后重连(第 ${attempt} 次)`);
  retryTimer = window.setTimeout(() => {
    retryTimer = null;
    void connect();
  }, delay);
}

async function connect(): Promise<void> {
  if (!running || controller) return;
  const ctl = new AbortController();
  controller = ctl;
  lastRecvAt = Date.now();

  const q = new URLSearchParams({ last_event_id: String(lastEventId) });
  if (epoch !== null) q.set('epoch', String(epoch));

  headerTimer = window.setTimeout(() => {
    console.warn('[sessionEvents] 响应头超时，重连');
    ctl.abort();
  }, HEADER_TIMEOUT_MS);

  try {
    const res = await fetch(`${API_BASE_URL}/chat/events?${q.toString()}`, {
      signal: ctl.signal,
      headers: authHeaders(),
    });
    if (headerTimer !== null) {
      window.clearTimeout(headerTimer);
      headerTimer = null;
    }
    if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

    // 建连成功：重置退避计数并触发一次对账（补齐断线期间的事实，这是可靠性的真正来源）
    if (attempt > 0) {
      attempt = 0;
      reconcileHandlers.forEach((fn) => {
        try {
          fn();
        } catch (e) {
          console.warn('[sessionEvents] 对账回调异常:', e);
        }
      });
    }
    await pump(res.body);
    // 正常 EOF（后端重启/网关 FIN）：不是"假死"，也要重连
    if (running) {
      console.info('[sessionEvents] 流结束，准备重连');
      controller = null;
      scheduleReconnect();
    }
  } catch (e) {
    if (headerTimer !== null) {
      window.clearTimeout(headerTimer);
      headerTimer = null;
    }
    if (!running) return;
    console.warn('[sessionEvents] 连接失败/中断:', e);
    controller = null;
    scheduleReconnect();
  }
}

/** 看门狗：超过 HEARTBEAT_TIMEOUT_MS 无任何帧即判假死，主动断开重连 */
function armWatchdog(): void {
  if (watchdogTimer !== null) return;
  watchdogTimer = window.setInterval(() => {
    if (!running) return;
    if (Date.now() - lastRecvAt > HEARTBEAT_TIMEOUT_MS) {
      console.warn('[sessionEvents] 心跳超时(假死)，主动重连');
      lastRecvAt = Date.now(); // 防止重连前重复触发
      controller?.abort();
      controller = null;
      scheduleReconnect();
    }
  }, WATCHDOG_TICK_MS);
}

/** 订阅信封；返回取消函数。首个订阅者启动连接，最后一个离开时关闭（引用计数） */
export function subscribeLifecycle(handler: Handler): () => void {
  handlers.add(handler);
  if (!running) {
    running = true;
    attempt = 0;
    armWatchdog();
    void connect();
  }
  return () => {
    handlers.delete(handler);
    if (handlers.size === 0) stopLifecycle();
  };
}

/** 注册重连对账回调（接入方：拉权威快照比对锚点，不一致则重新锚定）；返回注销函数 */
export function addReconcileHandler(fn: () => void): () => void {
  reconcileHandlers.add(fn);
  return () => {
    reconcileHandlers.delete(fn);
  };
}

/** 页面从后台切回可见时调用：浏览器会节流后台定时器，切回后立即复核连接健康 */
export function pokeLifecycle(): void {
  if (!running) return;
  if (controller === null) {
    void connect();
    return;
  }
  if (Date.now() - lastRecvAt > HEARTBEAT_TIMEOUT_MS) {
    controller.abort();
    controller = null;
    scheduleReconnect();
  }
}

export function stopLifecycle(): void {
  running = false;
  attempt = 0;
  clearTimers();
  if (controller) {
    controller.abort();
    controller = null;
  }
}
