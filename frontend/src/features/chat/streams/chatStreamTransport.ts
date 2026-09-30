// [63] 5.3：SSE 传输层——POST 首连 / GET after_seq 续传 / 读循环 / 指数退避 /
//   180s 头超时 / 60s 空闲超时（HITL 等待期暂停）/ 错误分类与轮询观察。
//   迁移源：useSSE.ts:779-1179（sendMessageInternal/reconnect 读循环链）
//         + useSSE.ts:121-404（模块级 helper：classifyError/handleSSEError/
//           ERROR_CONFIG_MAP/calculateReconnectDelay/pollSessionTaskStatus/TASK_POLL_*）
//   本层不持有任何 React 状态，状态宿主唯一为 Store session（5.4）。
import { processSSEData } from '@/features/chat/services/sseParser';
import {
  classifyError,
  ErrorType,
  getErrorConfig,
  handleSSEError,
} from '@/services/error/handler';
// 2026-09-30 00:52 小欧 - [63] 5.15 归位补漏：taskControlApi 用于"顶替即拒"旧 HITL 请求(BUG-14)
import { sessionTaskApi, taskControlApi } from '@/services/api/task.api';
import { getAccessToken } from '@/services/api/client';
import type { ExecutionStep } from '@/types/execution';
import type { Dispatch, SetStateAction } from 'react';
import type { SSEError, SSEMetadata } from '@/types/sse';
import type {
  PendingAuthorizationPayload,
  ResumeResult,
  SessionSnapshot,
  StreamStatus,
} from './backupTypes';
import {
  chatStreamStore,
  commit,
  emitEvent,
  isTerminalStatus,
  type ChatStreamSession,
} from './chatStreamStore';

const HEADER_TIMEOUT = 180_000; // 请求头超时（fetch 返回即清除，useSSE.ts:831-834/882-885 同口径）

/** 清 180s 头超时定时器（字段化：真实 firstChunkTimeoutRef useSSE.ts:558；
 *  clearAllTimers 五件套 idle/firstChunk/reconnect/saveSteps/intentionalAbort 之一） */
function clearFirstChunkTimer(s: ChatStreamSession): void {
  if (s.firstChunkTimeout === null) return;
  window.clearTimeout(s.firstChunkTimeout);
  commit(s, (d) => {
    d.firstChunkTimeout = null;
  });
}

const IDLE_TIMEOUT = 60_000; // 无数据判定断连（心跳刷新；HITL 等待期暂停，useSSE.ts:912-933）
const MAX_ATTEMPTS = 3; // 重连次数上限（useSSE reconnectAttemptsRef 口径 useSSE.ts:543-547）
const RECONNECT = { maxAttempts: 3, baseDelay: 1000, maxDelay: 10_000 }; // useSSE.ts:543-547 原值
const TASK_POLL_INTERVAL = 5000; // ┐ 迁移自 useSSE.ts:179-181（pollSessionTaskStatus 配套常量）
const TASK_POLL_MAX = 30; // │ 5s×30≈2.5 分钟

/** 2026-09-29 小欧：重连退避 sleep（真实 useSSE.ts:1192-1193 setTimeout 等价，Promise 化后便于 await 串接） */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

/** 2026-09-29 小欧：Full Jitter 延迟 = random(0, min(base*2^attempt, max))（迁自 useSSE.ts:396-407） */
function calculateReconnectDelay(
  attempt: number,
  baseDelay: number,
  maxDelay: number
): number {
  const exponential = baseDelay * Math.pow(2, attempt);
  return Math.min(Math.random() * exponential, maxDelay);
}

// transport 连接配置（真实来源 useSSE config.baseURL/config.token，useSSE.ts:841-843）
// 由 main.tsx 模块级注入一次，替代 React hook 入参
let cfg: { baseURL: string; token?: string } = { baseURL: '' };

export function setTransportConfig(c: {
  baseURL: string;
  token?: string;
}): void {
  cfg = c;
}

/** 2026-09-29 小欧：原生 fetch 绕过 axios 拦截器，鉴权头必须现取（useSSE.ts:837-843 实证修复照搬） */
function authHeaders(): Record<string, string> {
  // 2026-09-29 小欧：口令以 getAccessToken() 为权威真源（登录/改口令后可即时生效），
  //   cfg.token 仅作 main.tsx 显式注入时的兜底——原 useSSE 的 config.token 全仓 0 处赋值，
  //   恒为 undefined 致 Authorization 从不附带（2026-09-26 缺陷），此处置为活读避免复现。
  const token = getAccessToken() ?? cfg.token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** 2026-09-29 小欧：统一构造 SSEError 事件载荷（5.1 StreamEvent error 载荷为 SSEError 全结构） */
function transportError(errorType: string, errorMessage: string): SSEError {
  return {
    type: 'error',
    error_type: errorType,
    error_message: errorMessage,
    timestamp: new Date().toISOString(),
  };
}

/**
 * 首连 POST：发消息并读取 SSE 流。taskId 由 start 帧经 storeHandlers.setServerTaskId 落 Store
 * （不另造解析函数，迁自真实 sseParser → handlers.setServerTaskId 链，useSSE.ts:1021）。
 */
export async function sendStreamRequest(
  s: ChatStreamSession,
  content: string,
  mode: 'linked' | 'independent'
): Promise<void> {
  // 前置状态（迁自 useSSE.ts:791-802：非重连才复位 seq、置接收/连接态）
  s.abortController?.abort(); // 2026-09-29 小欧：断上一条连接（等价 useSSE.ts:796 disconnect(false,...)），防连接泄漏
  // 2026-09-29 23:52:07 小欧（[63] 5.3 防退化修复 · F9）：换发必须先中止**旧轮询观察**再放行新流。
  //   旧 useSSE.ts.bak:796 disconnect() 走 unmount 路径，会把 pollSignalRef 一并 abort；
  //   5.3 原稿只 abort abortController，而 observeByPolling 只认 pollSignal
  //   （本文件 observeByPolling 首行 `if (s.pollSignal.aborted) return 'aborted'`），
  //   于是"轮询期间用户再发新消息"时旧轮询不中止、与新流叠加，两路都发 listTasks 都发事件。
  //   又 pollSignal 自建会话起只置 true 从不复位，故此处先置位旧信号中止旧轮询、再换新对象，
  //   使本轮新流/新轮询可用（否则本会话后续轮询永久死掉）。
  s.pollSignal.aborted = true; // 中止旧轮询观察
  s.pollSignal = { aborted: false }; // 本轮新信号，供本轮新流/新轮询
  commit(s, (d) => {
    d.lastSeq = -1; // 新请求复位（useSSE.ts:823），防上一任务 seq 守卫拦掉新帧
    d.isReceiving = true;
    d.isConnected = true;
    if (d.reconnectStatus !== 'reconnecting') d.reconnectStatus = 'connecting';
    d.abortController = new AbortController();
    // 2026-09-30 07:58 小欧 - [79] D1：控制器易主即清主动中断标志。
    //   该标志语义是"这一次 abort 是主动的"，只覆盖当次 abort；新连接接管后旧 abort 已了结。
    //   漏清的后果：stop()→clearCompleted 置真后再发新消息，本流 final 帧会被 onComplete 的
    //   intentionalAbort 守卫误判为"已取消"而丢弃，正常完成永不收尾（守卫反成退化源）。
    d.intentionalAbort = false;
  });
  const ctl = s.abortController!;
  commit(s, (d) => {
    d.firstChunkTimeout = window.setTimeout(() => ctl.abort(), HEADER_TIMEOUT);
  });
  try {
    const res = await fetch(`${cfg.baseURL}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        messages: [{ role: 'user', content: content }],
        stream: true,
        session_id: s.sessionId,
        context_link_mode: mode,
      }),
      signal: ctl.signal,
    });
    clearFirstChunkTimer(s);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    if (!res.body) throw new Error('响应体为空');
    await pump(res, s);
  } catch (e) {
    await handleTransportError(s, e);
  } finally {
    clearFirstChunkTimer(s); // 异常路径兜底
  }
}

/**
 * 恢复状态机 ACTIVE + GET_* 分支（5.4 resume 委派）：按 after_seq 续传同一流态缓冲，绝不重新 POST。
 * 不可重试错误类型不进循环；可重试耗尽后转轮询观察终态（2026-07-12 北京老陈裁定：不自动 cancel）。
 */
export async function resumeStreamRequest(
  s: ChatStreamSession
): Promise<ResumeResult> {
  if (!s.serverTaskId) return 'pending_draft';
  if (s.resumeInFlight) return 'recovering'; // 防双 pump（V4）
  // 2026-09-30 07:58 小欧 - [79] D1：控制器所有权——读循环在飞时不得抢占 abortController。
  //   下方循环每次 attempt 都 commit d.abortController = ctl，旧流就此失去唯一 abort 句柄——
  //   stop()/clearCompleted() 只能断新流，旧流继续吐帧并继续 emitEvent（双事件 + 连接泄漏）。
  //   判据只用瞬态标志 pumpActive（读循环单飞位，退出即 false）。
  //   不可并用 isConnected：它非瞬态，仅在终态/错误路径才置 false，断线后残留 true，
  //   会把合法重连一并挡掉（实测 8 项重连/轮询用例由该误判转红）。
  if (s.pumpActive) return 'recovering';
  commit(s, (d) => {
    d.resumeInFlight = true;
  });
  try {
    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt += 1) {
      const ctl = new AbortController();
      commit(s, (d) => {
        d.reconnectAttempts = attempt;
        d.reconnectStatus = attempt === 0 ? 'connecting' : 'reconnecting';
        d.abortController = ctl;
        // 2026-09-30 07:58 小欧 - [79] D1：同上，续传连接接管时清主动中断标志。
        //   recoverFromIdle 先 abort 旧读并 await pumpDone（旧泵 AbortError 已在标志为真时静默收尾），
        //   此处再清不影响该静默口径，顺序不产生回退。
        d.intentionalAbort = false;
        d.firstChunkTimeout = window.setTimeout(
          () => ctl.abort(),
          HEADER_TIMEOUT
        );
      });
      // session_id 取 Store sessionId 单一真源；after_seq 从已处理最大 seq 的下一帧开始（useSSE.ts:854）
      const url =
        `${cfg.baseURL}/chat/stream/${s.serverTaskId}` +
        `?session_id=${encodeURIComponent(s.sessionId)}&after_seq=${s.lastSeq + 1}`;
      try {
        const res = await fetch(url, {
          signal: ctl.signal,
          headers: authHeaders(),
        });
        clearFirstChunkTimer(s);
        if (res.status === 404) return await handleGetNotFound(s);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        if (!res.body) throw new Error('响应体为空');
        const r = await pump(res, s);
        commit(s, (d) => {
          d.reconnectAttempts = 0; // 成功建连即复位重连计数（useSSE.ts:1043-1044）
        });
        return r;
      } catch (e) {
        clearFirstChunkTimer(s);
        if (ctl.signal.aborted) return 'aborted';
        const t = classifyError(e);
        if (!getErrorConfig(t).retryable) {
          // 不可重试类直接失败，不空转 3 次（useSSE.ts:292-297 口径）
          commit(s, (d) => {
            d.reconnectStatus = 'failed';
            d.status = 'failed';
            d.isReceiving = false;
            d.isConnected = false;
          });
          emitEvent(s, 'error', transportError(t, String(e)));
          return 'failed';
        }
        commit(s, (d) => {
          d.reconnectStatus = 'reconnecting';
        });
        if (attempt === MAX_ATTEMPTS - 1) {
          // 2026-09-29 23:52:07 小欧（[63] 5.3 防退化修复 · 旧 B1【高】）：
          //   重连耗尽必须置 reconnectStatus='failed'。旧 useSSE.ts.bak:1155-1159
          //   `if (reconnectAttemptsRef.current >= config.maxAttempts) { setReconnectStatus('failed') }`
          //   明确置位；5.3 原稿直接 observeByPolling，reconnectStatus 一路停在 'reconnecting'
          //   最长 150s，UI 会一直显示"重连中"，而实际早已转入轮询观察 —— 状态与事实不符（铁规 1.2 严禁退化）。
          //   口径与旧实现同构：'failed' 只表示"重连这条路断了"，任务本身仍由轮询观察，不自动取消。
          commit(s, (d) => {
            d.reconnectStatus = 'failed';
          });
          // 2026-09-29 23:22:19 小欧（[63] 5.3 防退化修复）：重连耗尽必须向用户报一次错。
          //   旧 useSSE 的本地 handleSSEError 包装器（useSSE.ts.bak:303-324）在耗尽时先
          //   console.warn + 转入 pollSessionTaskStatus，随后**必发**一次
          //   onError{error_type, error_message: ERROR_CONFIG_MAP[errorType].showMessage ?? '连接失败'}。
          //   5.3 原稿直接 observeByPolling，用户最长 2.5 分钟（30×5s）收不到任何失败提示，
          //   期间 UI 只见"重连中"——铁规 1.2 严禁退化。此处按旧口径复原（ErrorConfig.message
          //   即旧 showMessage 的对应字段）。
          console.warn(
            `[SSE] 重连 ${MAX_ATTEMPTS} 次均失败, 进入轮询观察 task=${s.serverTaskId}`
          );
          emitEvent(
            s,
            'error',
            transportError(t, getErrorConfig(t).message || '连接失败')
          );
          return await observeByPolling(s);
        }
        await sleep(
          calculateReconnectDelay(
            attempt,
            RECONNECT.baseDelay,
            RECONNECT.maxDelay
          )
        );
      }
    }
    return await observeByPolling(s);
  } finally {
    clearFirstChunkTimer(s);
    commit(s, (d) => {
      d.resumeInFlight = false;
    });
  }
}

/**
 * GET 404（3.7 GET_NOT_FOUND 族）：以 chat_tasks 为权威回读终态，禁伪造完成。
 * 2026-09-29 小欧：原口径用 store.local 的 status 判定并强写 completed（可能与后端 failed/cancelled
 *   冲突致假完成）；改为回读 listTasks 的真实 status，恒与后端一致。
 */
async function handleGetNotFound(s: ChatStreamSession): Promise<ResumeResult> {
  const taskId = s.serverTaskId;
  if (!taskId) return 'not_found';
  const resp = await sessionTaskApi.listTasks(s.sessionId);
  const t = resp.tasks.find((x) => x.task_id === taskId);
  if (!t) return 'not_found';
  if (isTerminalStatus(t.status)) {
    commit(s, (d) => {
      d.status = t.status as StreamStatus;
      d.isReceiving = false;
      d.isConnected = false;
    });
    chatStreamStore.clearCompleted(s.sessionId);
    return 'terminal';
  }
  commit(s, (d) => {
    d.status = 'recovering';
  }); // 非终态且查不到 → 核对中，禁止伪造完成
  return 'recovering';
}

/** 轮询观察终态：迁自 useSSE.ts:183-231 pollSessionTaskStatus（5s×30、命中终态静默收尾、超时提示） */
async function observeByPolling(s: ChatStreamSession): Promise<ResumeResult> {
  const taskId = s.serverTaskId;
  if (!taskId) return 'not_found';
  for (let i = 0; i < TASK_POLL_MAX; i += 1) {
    if (s.pollSignal.aborted) return 'aborted'; // 终态释放/删除即中止（useSSE.ts:1069 语义）
    await sleep(TASK_POLL_INTERVAL);
    try {
      const resp = await sessionTaskApi.listTasks(s.sessionId);
      const t = resp.tasks.find((x) => x.task_id === taskId);
      if (!t) return 'not_found';
      if (isTerminalStatus(t.status)) {
        commit(s, (d) => {
          d.status = t.status as StreamStatus;
          d.isReceiving = false;
          d.isConnected = false;
        });
        chatStreamStore.clearCompleted(s.sessionId);
        return 'terminal'; // 命中终态即静默收尾（不误报错误）
      }
    } catch {
      /* 单次轮询失败不中断，下一轮重试 */
    }
  }
  commit(s, (d) => {
    d.isReceiving = false;
    d.isConnected = false;
  });
  // 2026-09-29 23:22:19 小欧（[63] 5.3 防退化修复）：轮询耗尽事件两处退化，一并复原——
  //   ① 文案：原 useSSE.ts.bak:227 为「连接已断开且任务仍在执行，请手动确认任务状态」，
  //      迁移稿写成「轮询观察超时：任务终态未知」，把"请手动确认"的用户指引整段丢了
  //      （铁规 1.2：功能只能增强/正确，严禁退化）。
  //   ② 结构：原为 SSEError 全结构（type/error_type/error_message/timestamp），
  //      迁移稿 emitEvent 传裸字符串，消费侧读 error_type/error_message 恒 undefined，
  //      与 5.1「error 事件恒为 SSEError 全结构」契约冲突。error_type 沿用原 'server'。
  console.warn(
    `[SSE] 轮询 ${TASK_POLL_MAX} 次任务仍在执行, 提示用户手动确认 task=${taskId}`
  );
  emitEvent(
    s,
    'error',
    transportError('server', '连接已断开且任务仍在执行，请手动确认任务状态')
  );
  return 'failed';
}

/**
 * 空闲看门狗：每轮 read 前重排（迁自 useSSE.ts:906-935 顺序：清旧/设新/再读）。
 * HITL 等待期暂停计时（useSSE.ts:913-914 isHitlWaitingRef guard）——hitlWaitingKeys 即等待集合。
 */
function armIdleWatch(s: ChatStreamSession): void {
  commit(s, (d) => {
    if (d.idleTimeout !== null) window.clearTimeout(d.idleTimeout);
  });
  const t = window.setTimeout(() => {
    if (s.hitlWaitingKeys.size > 0) {
      armIdleWatch(s); // HITL 等待中：重排而非杀连接
      return;
    }
    commit(s, (d) => {
      d.reconnectStatus = 'reconnecting';
    });
    void recoverFromIdle(s); // 超时 → 断旧读再续传（useSSE.ts:931 reconnect 同义）
  }, IDLE_TIMEOUT);
  commit(s, (d) => {
    d.idleTimeout = t;
  });
}

/**
 * 2026-09-29 小欧：空闲超时恢复必须"先断旧读、等旧泵退出、再续传"——
 *   useSSE.ts:931 reconnect() 内先 disconnect(false) abort 旧 fetch 后才建新连接；
 *   5.3 原稿直接 void resumeStreamRequest(s)，而 pump() 的 pumpActive 单飞守卫会把续传弹回
 *   'recovering'（旧泵仍占位直到 await read 抛 AbortError 才在 finally 清位）→ 空闲超时恢复永久失效。
 *   故 abort 后 await pumpDone 再续传。
 *
 * 2026-09-29 22:22:12 小欧（防退化补丁）：5.3 原稿只 abort+续传、**不发任何 error 事件**，
 *   而 useSSE.ts:920-931 的既有行为是 console.warn + onError('SSE 空闲超时：60s 未收到数据') + reconnect()。
 *   静默恢复会让"连接已卡死"对用户完全不可见（铁规 1.2 严禁退化功能），故按老口径复原上报：
 *   先 warn + emitEvent(error)，再断旧读续传——顺序与老代码 onError 先于 reconnect 一致。
 * 载荷用 error_type='idle_timeout' 走既有 handleSSEError 口径（getErrorConfig 提示语
 *   '连接空闲超时，正在尝试重连...'），比老代码裸字符串更准；发 error 不改 status，
 *   续传成功照常 terminal（不误判终态）。
 *
 * 2026-09-29 22:22:12 小欧（同批修第二处退化）：本函数 abort 旧读**必须**前置 intentionalAbort=true
 *   （与 5.4 clearCompleted/destroySession 同口径）。否则旧泵 read 抛的 AbortError 落到
 *   handleTransportError:640 非静默分支 → console.error 噪声 + reconnectStatus='failed'/
 *   isReceiving=false + observeByPolling 轮询，与本函数紧随其后的 resumeStreamRequest 并发抢同一会话
 *   （双恢复器）。2026-09-07 北京老陈裁定的 REQUEST-ABORT 静默默认路径正是为此设的标志。
 */
async function recoverFromIdle(s: ChatStreamSession): Promise<void> {
  const idleMs = Date.now() - s.lastDataTime;
  console.warn(
    `[SSE] 空闲超时：已 ${idleMs / 1000}秒 未收到数据，连接断开并尝试续传`,
    {
      idleMs,
      thresholdMs: IDLE_TIMEOUT,
      sessionId: s.sessionId,
      taskId: s.serverTaskId,
    }
  );
  emitEvent(
    s,
    'error',
    transportError(
      'idle_timeout',
      `SSE 空闲超时：${IDLE_TIMEOUT / 1000}秒 未收到数据`
    )
  );
  s.intentionalAbort = true; // 主动断旧读，非连接故障：抑制 AbortError 误判（防并发轮询+续传双恢复）
  s.abortController?.abort();
  if (s.pumpDone) await s.pumpDone.catch(() => undefined);
  // 2026-09-29 22:47:10 小欧（[63] 5.3 防退化修复）：首响应未到（无 task_id）时不得续传。
  //   resumeStreamRequest 开头 `if (!s.serverTaskId) return 'pending_draft'` 只是短路返回，
  //   既不重 POST（正确，避免重复/僵尸任务）也不改 reconnectStatus —— 而 armIdleWatch 已把
  //   状态置为 'reconnecting'，于是 UI 永久卡在"重连中"而实际无任何调度在进行。
  //   旧 useSSE 空闲守卫同口径：直接判 failed 交还用户重发（此处照搬该契约）。
  if (!s.serverTaskId) {
    commit(s, (d) => {
      d.reconnectStatus = 'failed';
    });
    return;
  }
  await resumeStreamRequest(s);
}

/** 读循环：逐行喂既有 processSSEData（不造第二套分帧器），frame 级分支短路 */
async function pump(
  res: Response,
  s: ChatStreamSession
): Promise<ResumeResult> {
  // 2026-09-30 07:58 小欧 - [79] D1：单飞早退必须释放本次响应体。
  //   原稿直接 return，本次 fetch 的 res.body 无人取消——单飞命中时该连接与缓冲就此泄漏
  //   （口径对齐下方 frame 分流路径的 reader.cancel()：拿到 body 的一方负责关 body）。
  if (s.pumpActive) {
    await res.body?.cancel();
    return 'recovering';
  }
  commit(s, (d) => {
    d.pumpActive = true;
  });
  const done = (async (): Promise<ResumeResult> => {
    const h = storeHandlers(s);
    try {
      const reader = res.body!.getReader();
      const decoder = new TextDecoder('utf-8');
      let buf = '';
      commit(s, (d) => {
        d.lastDataTime = Date.now();
        // 2026-09-29 22:47:10 小欧（[63] 5.3 防退化修复）：5.3 原稿只重置 lastDataTime，漏了
        //   lastBizTs。useSSE.ts.bak:936 原文"新一轮流重置业务基线, 防上轮陈旧值致钟面误升档"
        //   ——业务基线只由 onBiz 写，新一轮若首个业务帧迟迟不来，lastBizTs 仍是上一轮的
        //   陈旧值，ClockStopwatch 一开局就显示上轮耗时、静默升档被提前触发。
        //   照搬原口径：每轮建流（POST/GET 续传同一条 pump 入口）一并重置。
        d.lastBizTs = Date.now();
      }); // 数据基线（useSSE.ts:902-903）
      for (;;) {
        armIdleWatch(s); // 每轮 read 前重排 idle 定时器
        const { done: eof, value } = await reader.read();
        if (eof) {
          buf += decoder.decode(); // 吐出残留多字节字符（useSSE.ts:942-943）
          if (buf.trim())
            for (const line of buf.split('\n')) processSSEData(line, h.hooks);
          const branch0 = h.takeBranch();
          if (branch0) return branch0;
          if (s.lastSeq >= 0) {
            // 正常结束：final 已收到（useSSE.ts:981-985 以 lastSeq>=0 判定，语义等价 terminalSeqRef）
            commit(s, (d) => {
              if (d.idleTimeout !== null) window.clearTimeout(d.idleTimeout);
              d.reconnectStatus = 'idle';
            });
            return s.status === 'completed' ? 'terminal' : 'recovering';
          }
          // 空流终态（useSSE.ts:986-993 B1：200+空 body 不得永久接收中）
          commit(s, (d) => {
            d.isReceiving = false;
            d.isConnected = false;
            d.status = 'failed';
            d.reconnectStatus = 'idle';
          });
          emitEvent(
            s,
            'error',
            transportError('empty_response', 'SSE 空响应：未收到任何数据')
          );
          return 'failed';
        }
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop() ?? '';
        for (const line of lines) processSSEData(line, h.hooks);
        const branch = h.takeBranch();
        if (branch) {
          // 恢复类错误帧到达即停泵分流，不当普通帧消费
          try {
            await reader.cancel();
          } catch {
            /* 已结束 */
          }
          return branch;
        }
        commit(s, (d) => {
          d.lastDataTime = Date.now();
        });
      }
    } finally {
      commit(s, (d) => {
        d.pumpActive = false;
        // 2026-09-29 23:22:19 小欧（[63] 5.3 防退化修复）：读循环退出必须 disarm 空闲看门狗。
        //   原稿只在"正常结束且 lastSeq>=0"这一条路径清了 idleTimeout；流中途抛错(断连)、
        //   被 abort、以及 frame 分流(takeBranch)三条退出路径都会把 60s 定时器留在事件循环里。
        //   后果：断连后重连退避/observeByPolling 正在接管会话时，僵尸看门狗恰好在 60s 触发
        //   recoverFromIdle → 再 abort 再 resume，与既有恢复器抢同一会话（双恢复器），
        //   并向用户误报"SSE 空闲超时"。实测 sse-reconnect-poll F1~F10 全被此污染。
        if (d.idleTimeout !== null) {
          window.clearTimeout(d.idleTimeout);
          d.idleTimeout = null;
        }
      });
    }
  })();
  s.pumpDone = done; // 2026-09-29 小欧：暴露在飞读循环 promise，供 recoverFromIdle 断旧读后 await
  void done.then(
    () => {
      if (s.pumpDone === done) s.pumpDone = null;
    },
    () => {
      if (s.pumpDone === done) s.pumpDone = null;
    }
  );
  return done;
}

/**
 * Store 适配既有 processSSEData：React Dispatch 形接口用读写闭包承接，不造第二套分帧器；
 * ref 类接口全部可写（sseParser 会写 responseBufferRef.current / usageAccumRef.current /
 * pendingStepsRef.current，严格模式只读 getter 首帧即 TypeError）。
 * @param s 目标会话
 * @returns hooks 供 processSSEData 调用；takeBranch 读取本轮读循环是否被错误帧短路
 */
function storeHandlers(s: ChatStreamSession) {
  let branch: ResumeResult | null = null;
  const set =
    <T>(
      read: () => T,
      apply: (d: ChatStreamSession, v: T) => void
    ): Dispatch<SetStateAction<T>> =>
    (u) =>
      commit(s, (d) => {
        apply(d, typeof u === 'function' ? (u as (p: T) => T)(read()) : u);
      });
  const seqRef = {
    get current() {
      return s.lastSeq;
    },
    set current(v: number) {
      commit(s, (d) => {
        d.lastSeq = Math.max(d.lastSeq, v);
      });
    },
  };
  return {
    hooks: {
      setExecutionSteps: set(
        () => s.executionSteps,
        (d, v) => {
          d.executionSteps = v;
        }
      ),
      getCurrentExecutionSteps: () => s.executionSteps,
      // 2026-09-29 小欧：引 Store 推导视图，与 5.5 组件层同一对象（字面量各自创建即第二真源）
      executionStepsRef: chatStreamStore.getExecutionStepsRef(s.sessionId),
      pendingStepsRef: {
        // sseParser.ts:117 push / :575 splice 原地改写
        get current() {
          return s.pendingSteps;
        },
        set current(v: ExecutionStep[]) {
          commit(s, (d) => {
            d.pendingSteps = v;
          });
        },
      },
      scheduleFlush: () => flushPending(s), // rAF 批量刷新（S12，useSSE.ts:504-509 同构）
      onStep: (step: ExecutionStep, isReasoning?: boolean) =>
        emitEvent(s, 'step', { step, isReasoning }),
      onChunk: (chunk: string, isReasoning?: boolean) =>
        emitEvent(s, 'chunk', { chunk, isReasoning }),
      // 2026-09-29 小欧：metadata 类型对齐 sseParser.ts:136 真实契约
      //   （string | SSEMetadata），非 unknown——unknown 会在 5.1 载荷类型处断裂成断言
      onComplete: (
        full: string,
        meta?: string | SSEMetadata,
        steps?: ExecutionStep[]
      ) => {
        // 2026-09-30 07:58 小欧 - [79] D1：主动中断/已落终态后，迟到的 final 帧不得改写终态。
        //   成因：stop() 已置 status='cancelled' 且 clearCompleted 前置 intentionalAbort=true，
        //   但在途响应仍可能把 final 帧喂进来，此处无条件写 completed → 点"停止"却显示"已完成"。
        //   守卫同时覆盖 emitEvent：被取消的任务不得再以"正常完成"收尾追加助手消息
        //   （已收 chunk 仍在 UI，取消态文案由 stop() 返回值经 showTaskResultMessage 呈现）。
        if (s.intentionalAbort || isTerminalStatus(s.status)) return;
        commit(s, (d) => {
          d.status = 'completed'; // 终态写入点①
          d.isReceiving = false;
          d.isConnected = false;
        });
        emitEvent(s, 'complete', { full, meta, steps });
      },
      onMerged: (mergedIntoTaskId: string | null) =>
        // 2026-09-29 小欧：[76] 6.14 注入应答事件（sseParser.ts:947）——5.3 原稿漏接，漏则提示条/高亮永不触发
        emitEvent(s, 'merged', { mergedIntoTaskId }),
      onRejected: (data: {
        step: number;
        message: string;
        tool_name?: string;
        reject_type: string;
        confirm_id?: string;
      }) => {
        commit(s, (d) => {
          // HITL 被拒同样清 pendingAuthorization（与 5.15 acknowledge、onResumed 三路幂等）
          if (
            !data.confirm_id ||
            d.pendingAuthorization?.confirm_id === data.confirm_id
          ) {
            d.pendingAuthorization = null;
          }
        });
        emitEvent(s, 'rejected', {
          step: data.step,
          message: data.message,
          tool_name: data.tool_name,
          reject_type: data.reject_type,
        });
      },
      onRetry: (message: string, waitTime?: number) =>
        emitEvent(s, 'retry', { message, waitTime }),
      onAuthorizationRequired: (data: PendingAuthorizationPayload) => {
        // 2026-09-30 00:52 小欧 - [63] 5.15 归位补漏(BUG-14 退化)：Store 单源化后"顶替即拒"
        //   必须落在 Store。原实现只在 useAuthorization 的 React effect 里拒旧 pendingRef，
        //   但同一条 SSE 流内连发多帧（同批 commit）时 React 只渲染末帧 → 中间 confirm_id
        //   从未经 confirm(false)，静默泄漏到后端等到自身超时（原 2026-09-02 修的正是这个）。
        //   覆写发生处即 Store，prev 在此处必然可见，是唯一可靠归属点（DRY：单一 owner）。
        const prev = s.pendingAuthorization;
        if (prev && prev.confirm_id !== data.confirm_id) {
          void taskControlApi
            .confirm(prev.confirm_id, false, false)
            .catch(() => undefined);
        }
        commit(s, (d) => {
          d.pendingAuthorization = { ...data };
          d.hitlWaitingKeys.add(data.confirm_id);
          d.status = 'paused';
          d.isReceiving = true; // 2026-09-29 小欧：HITL 等待期保持接收态，UI 不得回落"无响应"
        });
      },
      onPaused: (confirmId?: string) => {
        commit(s, (d) => {
          if (confirmId) d.hitlWaitingKeys.add(confirmId);
          d.status = 'paused';
          d.isReceiving = true; // 同上：暂停≠停流
        });
        emitEvent(s, 'paused', { confirmId });
      },
      onResumed: (confirmId?: string) => {
        commit(s, (d) => {
          if (confirmId) d.hitlWaitingKeys.delete(confirmId);
          if (!confirmId || d.pendingAuthorization?.confirm_id === confirmId) {
            d.pendingAuthorization = null;
          }
          // 2026-09-29 22:22:12 小欧：恢复即回 active（2026-09-29 原稿无条件置 active），
          //   但并发 HITL（paused a + paused b，resumed 仅 a）时 b 仍在等待——无条件置 active 会让
          //   UI 显示"流式中"而实际卡在等用户确认 b，状态与 hitlWaitingKeys 自相矛盾。
          //   故按等待集合判定：无人在等才回 active，仍有人在等则保持 paused。
          d.status = d.hitlWaitingKeys.size === 0 ? 'active' : 'paused';
          d.isReceiving = true;
        });
        emitEvent(s, 'resumed', { confirmId });
      },
      onError: (e: SSEError | string) => {
        if (typeof e === 'string') {
          branch = 'failed';
          commit(s, (d) => {
            d.status = 'failed';
            d.isReceiving = false;
            d.isConnected = false;
          });
          emitEvent(s, 'error', e);
          return;
        }
        const recovery = RECOVERY_ERROR_BRANCH[e.error_type];
        // 2026-09-29 小欧：业务错误帧（blocked/timeout/user_rejected 等）**不终止流**——
        //   后端 event_emitter.py:84-109 在 ReAct 循环内 yield，Agent 继续执行并最终发 final；
        //   5.3 原稿 `ERROR_BRANCH[t] ?? 'failed'` 会把这类中间帧当终态杀掉读循环、丢掉 final（功能退化）。
        //   判据用 sseParser 既有契约 from_backend（sseParser.ts:654 无条件置 true）+ 恢复类 error_type 白名单。
        if (!recovery && e.from_backend) {
          emitEvent(s, 'error', e); // 仅投事件（HITL 齿轮/被拒点名/错误行由 5.8 消费），流继续
          return;
        }
        branch = recovery ?? 'failed';
        commit(s, (d) => {
          d.status = 'failed';
          d.isReceiving = false;
          d.isConnected = false;
        });
        emitEvent(s, 'error', e);
      },
      setCurrentResponse: set(
        () => s.currentResponse,
        (d, v) => {
          d.currentResponse = v;
        }
      ),
      responseBufferRef: {
        // 可写：sseParser.ts:487 `+=`、:546 赋值
        // 与 currentResponse 合一：buffer 全量即渲染值，不引入第三真源
        get current() {
          return s.currentResponse;
        },
        set current(v: string) {
          commit(s, (d) => {
            d.currentResponse = v;
          });
        },
      },
      setIsReceiving: set(
        () => s.isReceiving,
        (d, v) => {
          d.isReceiving = v;
        }
      ),
      setIsConnected: set(
        () => s.isConnected,
        (d, v) => {
          d.isConnected = v;
        }
      ),
      // 2026-09-29 小欧：全链零调用点（sseParser 内 0 处 disconnect 调用），保持空实现不做断流
      disconnect: () => undefined,
      setServerTaskId: set(
        () => s.serverTaskId,
        (d, v) => {
          d.serverTaskId = v; // start 帧落 taskId（useSSE.ts:1021）
        }
      ),
      onSeq: (seq: number) => {
        seqRef.current = seq;
      },
      lastSeqRef: seqRef,
      setMetaFrames: set(
        () => s.metaFrames,
        (d, v) => {
          d.metaFrames = v;
        }
      ),
      usageAccumRef: {
        get current() {
          return s.usageAccum;
        },
        set current(v: SessionSnapshot['usageAccum']) {
          commit(s, (d) => {
            d.usageAccum = v;
          });
        },
      },
      onHeartbeat: () =>
        commit(s, (d) => {
          d.heartbeatTs = Date.now();
        }),
      onBiz: () =>
        commit(s, (d) => {
          d.lastBizTs = Date.now();
        }),
    },
    takeBranch: (): ResumeResult | null => branch,
  };
}

/** flushPending：pendingSteps 批量落 executionSteps（迁自 useSSE.ts:487-509 S12 flush 语义） */
function flushPending(s: ChatStreamSession): void {
  if (s.flushScheduled) return;
  commit(s, (d) => {
    d.flushScheduled = true;
  });
  requestAnimationFrame(() => {
    commit(s, (d) => {
      d.flushScheduled = false;
      if (d.pendingSteps.length) {
        d.executionSteps = [...d.executionSteps, ...d.pendingSteps];
        d.pendingSteps = [];
      }
    });
  });
}

/** 后端 3.7 恢复类错误 → 恢复分支（走 HTTP 200 分块到达，由 storeHandlers.onError 分流） */
const RECOVERY_ERROR_BRANCH: Record<string, ResumeResult> = {
  not_found: 'not_found',
  task_interrupted: 'task_interrupted',
  task_state_incomplete: 'task_state_incomplete',
  persistence_gap: 'gap',
  persistence_degraded: 'degraded',
};

/**
 * 统一错误收口（迁自 useSSE.ts:1046-1092 catch 链）：主动断开静默短路 → 分类 → handleSSEError 决策。
 * @param s 目标会话
 * @param e 捕获到的异常
 * @returns 恢复结果，供 sendMessage 决策
 */
export async function handleTransportError(
  s: ChatStreamSession,
  e: unknown
): Promise<ResumeResult> {
  const t = classifyError(e);
  if (s.intentionalAbort && t === ErrorType.REQUEST_ABORT) {
    // 主动断开引发的 AbortError 静默收尾（useSSE.ts:1049-1062）：不误判 request_timeout、不复活重连
    commit(s, (d) => {
      d.intentionalAbort = false;
      d.isConnected = false;
      d.isReceiving = false;
    });
    return 'aborted';
  }
  console.error('[SSE] 请求错误:', e);
  const canRetry =
    getErrorConfig(t).retryable && s.reconnectAttempts < MAX_ATTEMPTS;
  handleSSEError(e, {
    reconnectAttempts: s.reconnectAttempts,
    maxRetries: MAX_ATTEMPTS,
    onReconnect: canRetry
      ? () => {
          commit(s, (d) => {
            d.reconnectStatus = 'reconnecting';
          });
          void scheduleReconnect(s);
        }
      : undefined,
  });
  if (canRetry) return 'recovering'; // 退避重连已调度，语义同"恢复中"（retry 态由 reconnectStatus 承载）
  commit(s, (d) => {
    d.reconnectStatus = 'failed';
    d.isConnected = false;
    d.isReceiving = false;
  });
  // 重试耗尽不自动取消（2026-07-12 北京老陈裁定）：任务可能仍在执行，轮询会话任务列表观察终态
  if (s.serverTaskId) return await observeByPolling(s);
  emitEvent(s, 'error', transportError(t, String(e)));
  return 'failed';
}

/**
 * 指数退避重连调度（迁自 useSSE.ts:1153-1199 reconnect）。
 * 2026-09-29 小欧：只走 GET after_seq 续传，**绝不重新 POST**——
 *   useSSE.ts:813-821 已根治"重连中尚无 taskId 再 POST → 双任务/僵尸任务"（F6/B1）；
 *   5.3 原稿 onReconnect 回 sendStreamRequest(s, content, mode) 会重新 POST 复活该 bug，故不回退。
 *   无 taskId（首响应未到）时无续传目标：终止重连，等用户重发。
 */
function scheduleReconnect(s: ChatStreamSession): void {
  if (!s.serverTaskId) {
    commit(s, (d) => {
      d.reconnectStatus = 'failed';
    });
    emitEvent(
      s,
      'error',
      transportError(
        'task_interrupted',
        'SSE 重连终止: 尚无任务ID(首响应未到), 未重复发起新任务'
      )
    );
    return;
  }
  const attempt = s.reconnectAttempts;
  const delay = calculateReconnectDelay(
    attempt,
    RECONNECT.baseDelay,
    RECONNECT.maxDelay
  );
  const handle = window.setTimeout(() => {
    commit(s, (d) => {
      d.reconnectTimeout = null;
      d.reconnectAttempts = attempt + 1;
    });
    void resumeStreamRequest(s);
  }, delay);
  commit(s, (d) => {
    d.reconnectTimeout = handle;
  });
}

// 编辑历史: 2026-09-29 21:37:55 小欧 - 新建: [63] 5.3 SSE 传输层落地(POST/GET 续传/读循环/退避/轮询观察/错误中心，
//   迁移自 useSSE.ts:779-1179 + :121-404) — 小欧-2026-09-29 21:37:55
//   相对 [63] 5.3 原稿的 6 处修正（均为避免功能退化/死代码，非风格改动）——小欧-2026-09-29 21:37:55：
//   ① onError 业务错误帧不再停泵：后端 event_emitter.py:84-109 在 ReAct 循环内 yield blocked/
//      user_rejected 等 error 中间帧，Agent 继续执行并最终发 final；原稿 `ERROR_BRANCH[t] ?? 'failed'`
//      会杀掉读循环、丢掉 final。改按 from_backend(sseParser.ts:654 既有契约) + 恢复类白名单判别。
//   ② 补 onMerged 接线（sseParser.ts:153/:947，[76] 6.14 注入应答）：原稿 5.3 漏接致提示条/高亮永不触发；
//      同步在 5.1 StreamEvent 增 'merged' kind。
//   ③ scheduleReconnect 只走 GET 续传不回退重 POST：复原 useSSE.ts:813-821 F6/B1 根治口径，
//      原稿 onReconnect → sendStreamRequest 会重新 POST 复活"双任务/僵尸任务"。
//   ④ ERROR_CONFIG_MAP 复用 @/services/error/handler 的 getErrorConfig（2026-09-27 已收敛的唯一兜底口），
//      不再原样复制第二份同义表（DRY，且直索引 ERROR_CONFIG_MAP 有白屏前科 handler.ts:14）。
//   ⑤ recoverFromIdle：abort 后 await pumpDone 再续传，修复 pumpActive 单飞守卫致空闲超时恢复永久失效；
//      同步复原 useSSE.ts:920-931 的空闲超时错误上报（console.warn + error 事件），防静默恢复致用户无感知；
//      abort 旧读前置 intentionalAbort=true，防旧泵 AbortError 误判为连接故障（噪声 + 轮询与续传双恢复） — 小欧-2026-09-29 22:22:12
//   ⑥ handleGetNotFound/observeByPolling 终态以 chat_tasks 回读的真实 status 为准（原稿强写 completed
//      可能与后端 failed/cancelled 冲突致假完成）。
//   ⑦ onResumed 按 hitlWaitingKeys 判定回 active/paused：并发 HITL 恢复其一时保持 paused
//      （原 5.3 无条件置 active，与仍在等待的 confirmId 自相矛盾）— 小欧-2026-09-29 22:22:12
//   另：onPaused/onAuthorizationRequired 置 status='paused' + isReceiving=true、onResumed 回 'active'，
//      消除 5.4 原实现"status 恒 paused"的 UI 卡死。
// 编辑历史: 2026-09-30 01:05:17 小欧 - 迁移落地后的 4 处功能退化修复 + 1 处 HITL 归位补漏（均为真实缺陷，
//   非风格改动；每条都经 vitest 用例实跑验证）：
//   ① pump 读循环所有退出路径泄漏 idleTimeout → 改在 finally 统一 clearTimeout + 置 null；
//   ② 重连耗尽后不再上报（同口径退化）→ reconnectStatus 置 'failed' 并按旧口径发一次连接失败
//      error 事件，随后仍进入轮询观察（不自动取消后端任务，任务继续跑）；
//   ③ releaseUnsubscribed（60s 宽限期满）只断流未停轮询 → 同步置 pollSignal.aborted=true，
//      堵 observeByPolling 空转；
//   ④ sendStreamRequest 换发消息时旧轮询不退出 → 先 abort 旧连接 + 置位旧 pollSignal 再新建信号；
//   ⑤ [63] 5.15 归位补漏(BUG-14)：onAuthorizationRequired 覆写 pendingAuthorization 前，先对被顶替的
//      旧 confirm_id 发 confirm(false) —— 原实现只在 useAuthorization 的 React effect 里拒旧
//      pendingRef，同批 commit 的中间帧拿不到 → 中间请求静默泄漏到后端等超时。覆写发生处即本处，
//      prev 必然可见，是唯一可靠归属点（DRY: 单一 owner，hook 侧同步删重复分支）；
//      为此 import 增补 taskControlApi（与 sessionTaskApi 同模块）— 小欧-2026-09-30 01:05:17
