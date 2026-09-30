// [63] 5.4：会话级流运行时唯一真源——模块级单例 Store 持有 Map<sessionId, ChatStreamSession>、
//   SSE 连接、步骤与任务锚点。页面只订阅，卸载仅解绑（订阅者链表保证 L1：卸载不销毁流）。
//   状态写入唯一入口 commit()（SLAP：transport 只调 commit，不直写字段）。
import type { ExecutionStep } from '@/types/execution';
import type { MutableRefObject } from 'react';
import { emptyMetaFrames } from '@/types/sse'; // 值函数必须值 import（type-only 不可调用）
import type { ClockSignals } from '@/types/sse';
import type {
  SessionSnapshot,
  StreamBackup,
  StreamEvent,
  StreamStatus,
  ResumeResult,
} from './backupTypes'; // 5.1 唯一定义处
import {
  load as backupLoad,
  save as backupSave,
  remove as backupRemove,
  saveDraft,
  isAnchorGroupIntact,
} from './chatStreamPersistence';
import { sendStreamRequest, resumeStreamRequest } from './chatStreamTransport';
import { taskControlApi, sessionTaskApi } from '@/services/api/task.api';

/** 终态状态集（3.10.1 权威口径）：completed/failed/cancelled 由 chat_tasks 与 final 帧共同决定 */
export const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled'] as const;

/** 2026-09-30 08:31 小欧 - [79] D3：终态条目内存保留时长（沿用原 10 分钟口径）。
 *  仅删内存条目，sessionStorage 备份不受影响——重开该会话按 5.2 正常恢复。 */
const TERMINAL_TTL_MS = 600_000;

/** 2026-09-30 08:31 小欧 - [79] D3：内存会话条目容量上限。
 *  超出时按"可回收时刻"先后 LRU 淘汰；活跃（在飞/非终态）与被订阅的会话永不被淘汰。 */
const MAX_SESSIONS = 32;

export function isTerminalStatus(status: string): boolean {
  return (TERMINAL_STATUSES as readonly string[]).includes(status);
}

/** 2026-09-30 07:58 小欧 - [79] D1：会话状态 → ResumeResult 单一判定口。
 *  sendMessage 尾与 resume 活流守卫共用同一口径（DRY：终态/非终态二分只写一次，不两处各抄一遍）。 */
function resumeResultOf(s: ChatStreamSession): ResumeResult {
  return s.status === 'completed' || isTerminalStatus(s.status) ? 'terminal' : 'recovering';
}

/** 2026-09-30 07:58 小欧 - [79] D1：该会话是否有在飞工作（活流守卫判据，单一判定口）。
 *  只认三个瞬态标志：读循环在飞(pumpActive)/发送在途(isProcessing)/续传在途(resumeInFlight)——
 *  三者各自在对应流程收尾时复位，能精确覆盖"状态正在被写"的所有窗口。
 *  刻意不认 isConnected：它非瞬态，仅在终态与错误路径才置 false，断线后残留 true，
 *  用它判活会把断线待重连的会话误判为活流，从而跳过本该做的恢复（实测 8 项重连用例转红）。 */
function hasInflightWork(s: ChatStreamSession): boolean {
  return s.pumpActive || s.isProcessing || s.resumeInFlight;
}

const EMPTY_SNAPSHOT: SessionSnapshot = Object.freeze({
  serverTaskId: null,
  lastSeq: -1,
  executionSteps: [],
  currentResponse: '',
  metaFrames: emptyMetaFrames(),
  usageAccum: { prompt: 0, completion: 0, total: 0 },
  isReceiving: false,
  isConnected: false,
  status: 'idle' as StreamStatus,
  pendingAuthorization: null,
  reconnectStatus: 'idle' as const,
  // 2026-09-29 22:47:10 小欧 [63] 5.6：0 = 未收到心跳（与 ZERO_CLOCK 钟面恒 0 同口径）
  heartbeatTs: 0,
});

/** render 期零信号（无 session 不创建；钟面恒 0——真实 heartbeatTs 0=未收到） */
const ZERO_CLOCK: ClockSignals = {
  lastBizTsRef: {
    get current() {
      return 0;
    },
    set current(_v: number) {
      /* 只读零信号 */
    },
  } as MutableRefObject<number>,
  lastDataTsRef: {
    get current() {
      return 0;
    },
    set current(_v: number) {
      /* 只读零信号 */
    },
  } as MutableRefObject<number>,
  heartbeatTs: 0,
};

export interface ChatStreamSession extends SessionSnapshot {
  sessionId: string;
  revision: number;
  // 锚点组（5.2 落盘口径，四元组 + 接收中标记已在 SessionSnapshot 内）
  pendingMessage: { clientMessageId: string; content: string; state: 'queued' | 'sent' } | null;
  lastContextLinkMode: 'linked' | 'independent';
  /** HITL 待确认请求属流状态，保证非激活视图/多 Tab 下弹窗与 confirmId 归属正确 */
  hitlWaitingKeys: Set<string>;
  // 连接与定时器资源句柄（clearAllTimers 五件套：idle/firstChunk/reconnect/saveSteps/intentionalAbort）
  abortController: AbortController | null;
  idleTimeout: number | null;
  firstChunkTimeout: number | null; // 180s 头超时
  reconnectTimeout: number | null; // 指数退避延时
  saveStepsTimer: number | null; // 5s 防抖落盘
  intentionalAbortTimer: number | null;
  pollSignal: { aborted: boolean };
  reconnectAttempts: number;
  isProcessing: boolean; // 发送防重
  intentionalAbort: boolean;
  lastDataTime: number;
  lastBizTs: number;
  heartbeatTs: number;
  pendingSteps: ExecutionStep[];
  flushScheduled: boolean; // rAF flush 去重
  pumpActive: boolean; // 读循环单飞标志，防双 pump
  /** 2026-09-29 小欧：在飞读循环的完成 promise（5.3 recoverFromIdle 断旧读后 await 它再续传，
   *  否则 pumpActive 单飞守卫会把空闲超时恢复永久弹回 'recovering'） */
  pumpDone: Promise<ResumeResult> | null;
  resumeInFlight: boolean; // 恢复单飞标志，防重复 resume 建双 GET
  // 订阅与快照
  snapshot: SessionSnapshot;
  listeners: Set<() => void>;
  eventListeners: Set<(e: StreamEvent) => void>;
  /** 无人订阅回收的宽限起点（epoch ms）；null 表示当前有订阅者 */
  releasedAt: number | null;
  /** 2026-09-30 08:31 小欧 - [79] D3：首次落终态的时刻（null = 未落终态）。
   *  双重职责：① 终态 TTL 排期的计时起点（与"是否曾零订阅"解耦）；② 容量淘汰的 LRU 排序键。 */
  terminalAt: number | null;
  /** 2026-09-30 08:31 小欧 - [79] D3：终态 TTL 排期句柄（重排前先清，幂等不叠定时器）。 */
  terminalEvictTimer: number | null;
  /** executionSteps 推导 ref 视图（getExecutionStepsRef 惰性创建、引用稳定）——
   *  读写均落 Store 快照，非第二真源；5.3 parser 与 5.5 组件层共用同一对象 */
  executionStepsRefView?: { current: ExecutionStep[] };
  /** 钟面信号视图（getClockSignals 惰性创建、引用稳定，与 executionStepsRefView 同模式）——
   *  三个字段均为活 getter，恒读本 session，非第二真源 */
  clockSignalsView?: ClockSignals;
}

const sessions = new Map<string, ChatStreamSession>();

/** 唯一写入口：一切字段变更经此函数，尾随快照重建与订阅通知 */
export function commit(s: ChatStreamSession, fn: (d: ChatStreamSession) => void): void {
  // 2026-09-30 08:31 小欧 - [79] D3：终态跃迁在此单点捕获（所有终态写入路径都经 commit，
  //   无需在各写入点分别设防），落终态即排期 TTL —— 排期与"是否曾零订阅"解耦。
  //   原稿把终态 TTL 嵌在 releaseUnsubscribed 的宽限期回调内，导致"用户盯着看完"的会话
  //   （全程有订阅者，宽限期回调首行即 return）永不被排期，标签页不关即永久泄漏。
  const wasTerminal = isTerminalStatus(s.status);
  fn(s);
  bump(s);
  schedulePersist(s);
  if (!wasTerminal && isTerminalStatus(s.status)) {
    s.terminalAt = Date.now();
    chatStreamStore.scheduleTerminalEviction(s.sessionId);
  } else if (wasTerminal && !isTerminalStatus(s.status)) {
    // 2026-09-30 08:31 小欧 - [79] D3：离开终态即作废 terminalAt，维持"该字段 ⟺ 当前处于终态"
    //   的不变式。不作废则复用的会话带着陈旧极旧值，LRU 序里会被优先淘汰（该会话明明刚被用过）。
    //   已武装的 TTL 句柄无需在此清：到点 evictSession 见非终态自会拒收，且下次落终态时幂等重排。
    s.terminalAt = null;
  }
}

/** 快照重建与订阅通知；不合成事件，事件只由 emitEvent 按真实帧发出。
 *  纯资源字段写入（abortController/定时器等不进快照）不换引用、不通知，杜绝无谓重渲染。 */
function bump(s: ChatStreamSession): void {
  const next: SessionSnapshot = {
    serverTaskId: s.serverTaskId,
    lastSeq: s.lastSeq,
    executionSteps: s.executionSteps,
    currentResponse: s.currentResponse,
    metaFrames: s.metaFrames,
    usageAccum: s.usageAccum,
    isReceiving: s.isReceiving,
    isConnected: s.isConnected,
    status: s.status,
    pendingAuthorization: s.pendingAuthorization,
    reconnectStatus: s.reconnectStatus,
    heartbeatTs: s.heartbeatTs,
  };
  if (shallowEqualSnapshot(s.snapshot, next)) return; // 快照内容未变：不 revision、不通知
  s.revision += 1;
  s.snapshot = next;
  s.listeners.forEach((cb) => cb());
}

const SNAPSHOT_KEYS: (keyof SessionSnapshot)[] = [
  'serverTaskId',
  'lastSeq',
  'executionSteps',
  'currentResponse',
  'metaFrames',
  'usageAccum',
  'isReceiving',
  'isConnected',
  'status',
  'pendingAuthorization',
  'reconnectStatus',
  'heartbeatTs',
];

function shallowEqualSnapshot(a: SessionSnapshot, b: SessionSnapshot): boolean {
  return SNAPSHOT_KEYS.every((k) => a[k] === b[k]);
}

/** 落盘调度：普通帧 5s 防抖（句柄存 session.saveStepsTimer），终态立即写 */
function schedulePersist(s: ChatStreamSession): void {
  if (isTerminalStatus(s.status)) {
    chatStreamStore.persistNow(s.sessionId);
    return;
  }
  if (s.saveStepsTimer !== null) return; // 防抖窗内不再重排
  s.saveStepsTimer = window.setTimeout(() => {
    s.saveStepsTimer = null;
    chatStreamStore.persistNow(s.sessionId);
  }, 5000); // 与 useSSE.ts:475 同为 5s 防抖
}

/** 真实帧事件投递：kind 归一化在 5.3 storeHandlers 各回调内完成；无帧不投递 */
export function emitEvent<K extends StreamEvent['kind']>(
  s: ChatStreamSession,
  kind: K,
  payload: Extract<StreamEvent, { kind: K }>['payload']
): void {
  const e: StreamEvent = {
    seq: s.lastSeq,
    taskId: s.serverTaskId,
    sessionId: s.sessionId,
    kind,
    payload,
    revision: s.revision,
    occurredAt: Date.now(),
  } as StreamEvent;
  s.eventListeners.forEach((cb) => cb(e));
}

/** POST 前查重附着：同内容 + created_at 300s 窗内 + executing 的活动任务只读跟随。
 *  附着即置 taskId/active 并 resume（不发第二 POST）；未附着返回 null 交调用方走正常路径。 */
async function attachActiveTask(
  s: ChatStreamSession,
  content: string
): Promise<ResumeResult | null> {
  const resp = await sessionTaskApi.listTasks(s.sessionId);
  const now = Date.now();
  const active = resp.tasks.find((t) => {
    if (t.status !== 'executing' || t.user_input !== content || t.task_id === s.serverTaskId) {
      return false;
    }
    const age = now - Date.parse(t.created_at);
    return Number.isNaN(age) || age <= 300_000; // 300s 窗；解析失败不拦，后端并发保护兜底
  });
  if (!active) return null;
  commit(s, (d) => {
    d.serverTaskId = active.task_id;
    d.pendingMessage = null;
    d.status = 'active';
  });
  chatStreamStore.persistNow(s.sessionId);
  return resumeStreamRequest(s);
}

/** 2026-09-30 08:31 小欧 - [79] D3：容量上限淘汰（终态 LRU）。
 *  只淘汰"已无人订阅且已可回收"的条目，排序键 = 终态时刻 terminalAt ?? 退订时刻 releasedAt。
 *  两键皆 null（仍有订阅者）即不可回收——故正在跑/正在看的会话永不被淘汰。
 *  刚建的条目两键皆 null，天然不在候选内，无需特判"别淘汰自己"。
 *  逐个交 evictSession 复用其断连接/清定时器/删条目全套动作，不另写删除逻辑。 */
function evictOverflow(): void {
  if (sessions.size <= MAX_SESSIONS) return;
  const candidates = [...sessions.values()]
    .filter(
      (s) =>
        s.listeners.size === 0 &&
        s.eventListeners.size === 0 &&
        (isTerminalStatus(s.status) || s.status === 'idle')
    )
    .map((s) => ({ s, key: s.terminalAt ?? s.releasedAt }))
    .filter((x): x is { s: ChatStreamSession; key: number } => x.key !== null)
    .sort((a, b) => a.key - b.key); // 最旧可回收者先走
  for (const { s } of candidates) {
    if (sessions.size <= MAX_SESSIONS) break;
    chatStreamStore.evictSession(s.sessionId);
  }
}

export const chatStreamStore = {
  /** 显式创建；getSnapshot 路径绝不创建 */
  ensureSession(sessionId: string): ChatStreamSession {
    let s = sessions.get(sessionId);
    if (s) return s;
    s = {
      sessionId,
      revision: 0,
      ...EMPTY_SNAPSHOT,
      // 数组/对象字段不随展开共享 EMPTY_SNAPSHOT 引用（Object.freeze 仅浅层）：创建即独立实例
      executionSteps: [],
      currentResponse: '',
      metaFrames: emptyMetaFrames(),
      usageAccum: { prompt: 0, completion: 0, total: 0 },
      pendingAuthorization: null,
      pendingMessage: null,
      lastContextLinkMode: 'independent',
      hitlWaitingKeys: new Set(),
      abortController: null,
      idleTimeout: null,
      reconnectTimeout: null,
      firstChunkTimeout: null,
      saveStepsTimer: null,
      intentionalAbortTimer: null,
      pollSignal: { aborted: false },
      reconnectAttempts: 0,
      isProcessing: false,
      intentionalAbort: false,
      lastDataTime: 0,
      lastBizTs: 0,
      heartbeatTs: 0,
      pendingSteps: [],
      flushScheduled: false,
      pumpActive: false,
      pumpDone: null,
      resumeInFlight: false,
      snapshot: EMPTY_SNAPSHOT,
      listeners: new Set(),
      eventListeners: new Set(),
      releasedAt: null,
      terminalAt: null,
      terminalEvictTimer: null,
    };
    sessions.set(sessionId, s);
    evictOverflow();
    return s;
  },

  hasSession: (sessionId: string) => sessions.has(sessionId),

  /** 终态 TTL 排期（幂等）：重排前先清旧句柄，终态时起算，到点交 evictSession 删内存条目。
   *  两个触发点共用本方法：① commit 检测到终态跃迁（与"是否曾零订阅"解耦的主路径）；
   *  ② releaseUnsubscribed 发现已落终态——补上"上次 TTL 到点因有订阅者被拒、计时空转"的缺口。 */
  scheduleTerminalEviction(sessionId: string): void {
    const s = sessions.get(sessionId);
    if (!s || !isTerminalStatus(s.status)) return;
    if (s.terminalEvictTimer !== null) window.clearTimeout(s.terminalEvictTimer);
    s.terminalEvictTimer = window.setTimeout(() => {
      s.terminalEvictTimer = null;
      this.evictSession(sessionId);
    }, TERMINAL_TTL_MS);
  },

  /** 返回缓存引用；session 不存在时返回冻结空快照，不惰性创建 */
  getSnapshot(sessionId: string): SessionSnapshot {
    return sessions.get(sessionId)?.snapshot ?? EMPTY_SNAPSHOT;
  },

  subscribe(sessionId: string, listener: () => void): () => void {
    const s = this.ensureSession(sessionId);
    s.listeners.add(listener);
    s.releasedAt = null; // 有订阅者 → 取消回收计时
    return () => {
      s.listeners.delete(listener);
      if (s.listeners.size === 0 && s.eventListeners.size === 0) {
        this.releaseUnsubscribed(sessionId); // 最后一个订阅者离开即起宽限计时
      }
    };
  },

  subscribeEvents(sessionId: string, listener: (e: StreamEvent) => void): () => void {
    const s = this.ensureSession(sessionId);
    s.eventListeners.add(listener);
    s.releasedAt = null;
    return () => {
      s.eventListeners.delete(listener);
      if (s.listeners.size === 0 && s.eventListeners.size === 0) {
        this.releaseUnsubscribed(sessionId);
      }
    };
  },

  /**
   * 发送：先落盘 queued 再 POST；taskId 由 start 帧经 setServerTaskId 落定后置 sent；
   * POST 前经 attachActiveTask 查重附着（同内容 + 300s 窗内活动任务只读跟随，不发第二 POST）。
   * @param sessionId 会话 id
   * @param content 用户消息正文
   * @param mode 上下文链接模式
   * @returns 发送与恢复结果（UI 据此提示）
   */
  async sendMessage(
    sessionId: string,
    content: string,
    mode: 'linked' | 'independent' = 'independent'
  ): Promise<ResumeResult> {
    const s = this.ensureSession(sessionId);
    if (s.isProcessing) return 'recovering'; // 防双发
    commit(s, (d) => {
      d.isProcessing = true;
      d.pendingMessage = { clientMessageId: crypto.randomUUID(), content, state: 'queued' };
      d.lastContextLinkMode = mode; // 2026-09-29 小欧：记录本次模式，续传/回放沿用（原字段零写入即死字段）
    });
    this.persistNow(sessionId);
    try {
      const attached = await attachActiveTask(s, content); // 附着分支内部已 resume + 持久化
      if (attached !== null) return attached;
      this.clearSteps(sessionId); // 新请求清旧步骤（真实 useSSE.ts:791-795）
      await sendStreamRequest(s, content, mode);
      commit(s, (d) => {
        if (d.pendingMessage) d.pendingMessage = { ...d.pendingMessage, state: 'sent' };
        if (d.status === 'idle' || d.status === 'recovering') d.status = 'active';
      });
      this.persistNow(sessionId);
      return resumeResultOf(s);
    } finally {
      commit(s, (d) => {
        d.isProcessing = false;
      }); // 无论成败复位
    }
  },

  /**
   * 恢复状态机：PENDING_NO_TASK / ACTIVE / GET_* / STOP_RACE 全部在此分派。
   * @param sessionId 会话 id（空/缺省 → 无可恢复对象，直接 idle；禁 ensureSession 造 '' 假会话）
   * @returns 恢复结果
   */
  async resume(sessionId?: string): Promise<ResumeResult> {
    // 2026-09-29 小欧：无 id（如首屏无 URL session_id）即无可恢复对象，短路防造幽灵会话（5.17 调用形态）
    if (!sessionId) return 'idle';
    // 2026-09-30 07:58 小欧 - [79] D1：活流守卫——该会话已有在飞读循环/连接时直接回读当前状态。
    //   成因：useChatInit 每次 urlSessionId 变化都调 resume()，切回正在跑的会话时 restore() 用备份
    //   覆盖在飞状态（lastSeq/steps/currentResponse 倒退闪烁、isConnected 假 false），
    //   随后 resumeStreamRequest 再抢占 abortController，泄漏旧连接并起第二条流。
    //   落点选在 restore() 的唯一调用方 resume()：一次拦住"覆盖状态"与"起第二条流"两个后果
    //   （restore 不再重复设防，避免同一不变量两处判断）。
    const cur = sessions.get(sessionId);
    if (cur && hasInflightWork(cur)) return resumeResultOf(cur);
    const s = this.ensureSession(sessionId);
    const restored = await this.restore(sessionId);
    if (restored === 'invalid') {
      commit(s, (d) => {
        d.status = 'idle';
      });
      return 'idle';
    }
    if (!s.serverTaskId) return this.recoverWithoutTaskId(s);
    return resumeStreamRequest(s);
  },

  /** 无 taskId 的恢复：查重附着同内容活动任务；无则交还显式待发草稿，绝不自动 POST */
  async recoverWithoutTaskId(s: ChatStreamSession): Promise<ResumeResult> {
    const attached = await attachActiveTask(s, s.pendingMessage?.content ?? '');
    if (attached !== null) return attached;
    commit(s, (d) => {
      d.status = 'idle';
    });
    return 'pending_draft';
  },

  /**
   * 停止任务：真实取消端点 taskControlApi.cancel → {success,message}。
   * STOP_RACE = 后端 set_cancelled 失败（"不存在,可能已结束" → success:false）：
   * 此时回读权威终态确认，不报错不重试；成功路径后端已 set_cancelled。
   * @param sessionId 会话 id
   * @returns 后端/回读文案（5.14 showTaskResultMessage 直接展示）
   */
  async stop(sessionId: string): Promise<{ success: boolean; message: string }> {
    // 2026-09-29 小欧：无会话 id / 该会话未建运行时 → 直接短路，
    //   禁走 ensureSession（否则凭空造出 '' 幽灵会话，违反 4.6 空会话不落库原则）
    if (!sessionId) return { success: false, message: '无进行中的任务' };
    const s = this.ensureSession(sessionId);
    if (!s.serverTaskId) return { success: false, message: '无进行中的任务' };
    const r = await taskControlApi.cancel(s.serverTaskId, s.sessionId);
    if (!r.success) {
      // STOP_RACE：任务已自然完成/不存在 → 回读权威终态
      const resp = await sessionTaskApi.listTasks(s.sessionId);
      const t = resp.tasks.find((x) => x.task_id === s.serverTaskId);
      commit(s, (d) => {
        d.status = t && isTerminalStatus(t.status) ? (t.status as StreamStatus) : 'completed';
        d.isReceiving = false;
      });
      this.clearCompleted(sessionId); // 终态确认 → 释放全套流资源
      this.persistNow(sessionId);
      return { success: true, message: t ? `任务已结束（${t.status}）` : '任务不存在，可能已结束' };
    }
    commit(s, (d) => {
      d.status = 'cancelled';
      d.isReceiving = false;
    }); // 以后端 set_cancelled 为准，不强写
    this.clearCompleted(sessionId);
    this.persistNow(sessionId);
    return { success: true, message: r.message || '任务已取消' };
  },

  /** 终态资源全套释放——与真实卸载五件套等价；只释放客户端资源：
   *  不 cancel、不删备份、不改任务状态。 */
  clearCompleted(sessionId: string): void {
    const s = sessions.get(sessionId);
    if (!s || !isTerminalStatus(s.status)) return;
    s.intentionalAbort = true; // 2026-09-29 小欧：主动断连接前置标志，否则 AbortError 被判为连接故障弹错误/复活重连
    s.abortController?.abort();
    s.abortController = null;
    if (s.idleTimeout !== null) window.clearTimeout(s.idleTimeout);
    if (s.reconnectTimeout !== null) window.clearTimeout(s.reconnectTimeout);
    if (s.firstChunkTimeout !== null) window.clearTimeout(s.firstChunkTimeout);
    if (s.saveStepsTimer !== null) window.clearTimeout(s.saveStepsTimer);
    if (s.intentionalAbortTimer !== null) window.clearTimeout(s.intentionalAbortTimer);
    s.idleTimeout = null;
    s.reconnectTimeout = null;
    s.firstChunkTimeout = null;
    s.saveStepsTimer = null;
    s.intentionalAbortTimer = null;
    s.pollSignal.aborted = true; // 中止轮询观察
    s.isProcessing = false;
    s.pumpActive = false;
    s.resumeInFlight = false;
    s.reconnectAttempts = 0;
    commit(s, (d) => {
      d.reconnectStatus = 'idle';
    });
    s.pendingMessage = null;
    s.hitlWaitingKeys.clear(); // 待发/HITL 态随终态清空
  },

  /** 清空该会话已收步骤与正文缓冲（新请求/停止后置空）；真源清空与备份删除同一动作，
   *  故不走 commit 的落盘调度（防抖会把已删备份重新写回），截断在途防抖后直接 bump 通知。 */
  clearSteps(sessionId: string): void {
    const s = sessions.get(sessionId);
    if (!s) return;
    if (s.saveStepsTimer !== null) {
      window.clearTimeout(s.saveStepsTimer);
      s.saveStepsTimer = null;
    }
    s.executionSteps = [];
    s.currentResponse = '';
    s.pendingSteps = [];
    s.isReceiving = false;
    backupRemove(sessionId);
    bump(s);
  },

  /** 推导 ref 视图：读——session.executionSteps（commit 后即新值）；写——commit 进 Store */
  getExecutionStepsRef(sessionId: string): { current: ExecutionStep[] } {
    const s = this.ensureSession(sessionId);
    if (!s.executionStepsRefView) {
      s.executionStepsRefView = {
        get current() {
          return s.executionSteps;
        },
        set current(v: ExecutionStep[]) {
          commit(s, (d) => {
            d.executionSteps = v;
          });
        },
      };
    }
    return s.executionStepsRefView;
  },

  /** 用户已处理授权弹窗（确认/拒绝）——Store 侧清 pendingAuthorization（防切回页面重弹旧请求） */
  acknowledgeAuthorization(sessionId: string): void {
    const s = sessions.get(sessionId);
    if (s)
      commit(s, (d) => {
        d.pendingAuthorization = null;
      });
  },

  setReceiving(sessionId: string, v: boolean): void {
    const s = sessions.get(sessionId);
    if (!s || s.isReceiving === v) return;
    commit(s, (d) => {
      d.isReceiving = v;
    });
    this.persistNow(sessionId);
  },

  setServerTaskId(sessionId: string, taskId: string): void {
    const s = sessions.get(sessionId);
    if (!s || s.serverTaskId === taskId) return;
    commit(s, (d) => {
      d.serverTaskId = taskId;
    });
    this.persistNow(sessionId);
  },

  /** 钟面信号：lastBizTs/lastDataTime 以 getter 桥接 session 数字字段（heartbeatTs 直接读值），
   *  保持 ref 语义稳定，供 waitClock 消费；session 不存在返回零信号（render 期不创建 session）。 */
  getClockSignals(sessionId: string): ClockSignals {
    const s = sessions.get(sessionId);
    if (!s) return ZERO_CLOCK;
    // 2026-09-29 22:47:10 小欧（[63] 5.4 防退化修复）：本函数原先每次调用都新建 ref 对象。
    //   5.5 桥接的 waitClock 用 useMemo([id, snapshot.heartbeatTs]) 缓存，而首次 render 时
    //   session 还没被 useEffect 的 ensureSession 建出来 → 那一刻返回 ZERO_CLOCK（恒 0）；
    //   空流/无心跳场景下 heartbeatTs 恒 0，memo 永不重算 → 组件永久持有零钟面
    //   （lastBizTs 永远读 0，等待动画与静默升档全失效）。
    //   改为与 getExecutionStepsRef 同模式：按会话惰性缓存、字段全为活 getter，
    //   引用稳定且恒读真值，memo 缓存与否都不再影响正确性。
    if (s.clockSignalsView) return s.clockSignalsView;
    s.clockSignalsView = {
      lastBizTsRef: {
        get current() {
          return s.lastBizTs;
        },
        set current(v: number) {
          commit(s, (d) => {
            d.lastBizTs = v;
          });
        },
      } as MutableRefObject<number>,
      lastDataTsRef: {
        get current() {
          return s.lastDataTime;
        },
        set current(v: number) {
          commit(s, (d) => {
            d.lastDataTime = v;
          });
        },
      } as MutableRefObject<number>,
      // 活 getter：缓存对象也恒反映最新心跳（否则 memo 依赖命中却拿到陈旧值）
      get heartbeatTs() {
        return s.heartbeatTs;
      },
    };
    return s.clockSignalsView;
  },

  /** 宽限期后只释放客户端资源：不 cancel、不停任务、不删快照；
   *  终态快照再经终态 TTL 后删条目（sessionStorage 备份不受影响，重开按 5.2 恢复）。 */
  releaseUnsubscribed(sessionId: string, graceMs = 60_000): void {
    const s = sessions.get(sessionId);
    if (!s || s.listeners.size > 0) return;
    s.releasedAt = Date.now();
    // 2026-09-30 08:31 小欧 - [79] D3：已落终态者立即排期 TTL，不等宽限期。
    //   覆盖"上次 TTL 到点时仍有订阅者被 evictSession 拒收、计时空转"的情形——退订即补排。
    if (isTerminalStatus(s.status)) this.scheduleTerminalEviction(sessionId);
    window.setTimeout(() => {
      const cur = sessions.get(sessionId);
      if (!cur || cur.listeners.size > 0 || cur.releasedAt === null) return;
      cur.intentionalAbort = true; // 2026-09-29 小欧：释放即断连接，前置主动中断标志
      cur.abortController?.abort();
      cur.abortController = null;
      // 2026-09-29 23:52:07 小欧（[63] 5.2/5.3 · F6）：必须一并中止轮询观察。
      //   本方法自身注释承诺"cancel、轮询停止"，但 observeByPolling 只认 pollSignal
      //   （chatStreamTransport.ts 内首行 `if (s.pollSignal.aborted) return 'aborted'`），
      //   原稿只 abort abortController → 宽限期满后轮询照跑满 30 tick（150s）继续打后端，
      //   正是 2026-09-08 F6【真实bug】"组件卸载后轮询 runaway"在新架构下的复现。
      //   口径：卸载**不立即**停（5.2 规定只退订、不 abort/清会话，给重渲染/切页留 60s 缓冲），
      //   宽限期满仍无订阅才停——既守住 5.2，又保证轮询有界不失控。
      cur.pollSignal.aborted = true;
      if (cur.idleTimeout !== null) window.clearTimeout(cur.idleTimeout);
      if (cur.reconnectTimeout !== null) window.clearTimeout(cur.reconnectTimeout);
      cur.idleTimeout = null;
      cur.reconnectTimeout = null;
      console.info(
        `[Store] 无人订阅宽限期到，释放客户端资源 session=${sessionId}（任务未停，条目保留）`
      );
      // 2026-09-30 08:31 小欧 - [79] D3：原此处"终态再 setTimeout(evictSession, 600_000)"
      //   整删——终态 TTL 已改由 commit 终态跃迁 / 本方法入口统一排期（scheduleTerminalEviction），
      //   保留会在有订阅者时静默空转，是 D3"用户盯着看完的会话永不被回收"的病根之一。
    }, graceMs);
  },

  /** 删除内存条目：只删 Map entry，不删 sessionStorage 备份，不碰后端任务 */
  evictSession(sessionId: string): void {
    const cur = sessions.get(sessionId);
    if (!cur || cur.listeners.size > 0) return;
    if (!isTerminalStatus(cur.status) && cur.status !== 'idle') return;
    cur.intentionalAbort = true;
    cur.abortController?.abort();
    cur.abortController = null;
    if (cur.idleTimeout !== null) window.clearTimeout(cur.idleTimeout);
    if (cur.saveStepsTimer !== null) window.clearTimeout(cur.saveStepsTimer);
    cur.idleTimeout = null;
    cur.saveStepsTimer = null;
    // 2026-09-30 08:31 小欧 - [79] D3：清本路径新增的终态 TTL 句柄。
    //   evictOverflow 走本方法删除条目时该定时器仍武装着，不清则白挂 10 分钟
    //   （到点 sessions.get 已空，空跑一次；无害但属资源遗留）。
    if (cur.terminalEvictTimer !== null) window.clearTimeout(cur.terminalEvictTimer);
    cur.terminalEvictTimer = null;
    cur.pollSignal.aborted = true;
    sessions.delete(sessionId);
  },

  /** 删除会话专用（4.6.2）：后端删除接口确认成功后调用——断连接+清定时器+移除条目+删快照与草稿。
   *  与 evictSession 不同：不受 listeners.size/终态限制（删除是显式终局命令）；不调后端 cancel。 */
  destroySession(sessionId: string): void {
    const cur = sessions.get(sessionId);
    if (cur) {
      cur.intentionalAbort = true;
      cur.abortController?.abort();
      cur.abortController = null; // 断 SSE/fetch 连接
      cur.pollSignal.aborted = true; // 断轮询观察
      for (const t of [
        cur.idleTimeout,
        cur.reconnectTimeout,
        cur.saveStepsTimer,
        cur.firstChunkTimeout,
        cur.intentionalAbortTimer,
        cur.terminalEvictTimer, // 2026-09-30 08:31 小欧 - [79] D3：并入既有五定时器清理循环
      ]) {
        if (t !== null) window.clearTimeout(t);
      }
      cur.idleTimeout = null;
      cur.reconnectTimeout = null;
      cur.saveStepsTimer = null;
      cur.firstChunkTimeout = null;
      cur.intentionalAbortTimer = null;
      sessions.delete(sessionId); // 移除 Map 条目（显式终局，不看 listeners.size）
    }
    backupRemove(sessionId); // 删快照
    saveDraft(sessionId, ''); // 清草稿
  },

  persistNow(sessionId: string): void {
    backupSave(this.toBackup(sessionId));
  },

  /** 恢复：legacy 归一已由 5.2 load 完成（legacyToBackup），本函数不再有 version!==2 死分支。
   *  ① 过滤未完成 action 预览步（真实 useSSE.ts:612-614：拦截/拒绝的 action 不落库）；
   *  ② 不恢复 isConnected——连接态由在飞连接决定，恢复后未连即 false。 */
  async restore(sessionId: string): Promise<'ok' | 'invalid'> {
    const raw = backupLoad(sessionId);
    if (!raw || raw.version !== 2) return 'invalid';
    const s = this.ensureSession(sessionId);
    const b = raw as StreamBackup;
    if (!isAnchorGroupIntact(b)) return 'invalid'; // 锚点组非同一快照即丢弃，走历史加载
    commit(s, (d) =>
      Object.assign(d, {
        serverTaskId: b.taskId,
        lastSeq: b.lastSeq,
        executionSteps: b.steps.filter(
          (st) => !(st.type === 'action' && st.preview === true)
        ),
        currentResponse: b.currentResponse,
        metaFrames: b.metaFrames,
        usageAccum: b.usageAccum,
        isReceiving: b.isReceiving,
        isConnected: false,
        status: b.status,
        pendingAuthorization: b.pendingAuthorization,
        pendingMessage: b.pendingMessage,
        hitlWaitingKeys: new Set(b.hitlWaitingKeys ?? []),
        lastContextLinkMode: b.lastContextLinkMode,
      })
    );
    return 'ok';
  },

  /** 生成不可变备份快照：lastSeq 与 steps 必须来自同一 revision（原子性要求） */
  toBackup(sessionId: string): StreamBackup {
    const s = this.ensureSession(sessionId);
    return {
      version: 2,
      revision: s.revision,
      sessionId: s.sessionId,
      taskId: s.serverTaskId,
      lastSeq: s.lastSeq,
      steps: [...s.executionSteps],
      metaFrames: s.metaFrames,
      currentResponse: s.currentResponse,
      usageAccum: { ...s.usageAccum },
      isReceiving: s.isReceiving,
      isConnected: s.isConnected,
      status: s.status,
      pendingAuthorization: s.pendingAuthorization,
      hitlWaitingKeys: [...s.hitlWaitingKeys],
      pendingMessage: s.pendingMessage,
      lastContextLinkMode: s.lastContextLinkMode,
      updatedAt: Date.now(),
      // 2026-09-29 22:47:10 小欧 [63] 5.6：随备份落盘，供刷新后恢复心跳钟面（0=未收到）
      heartbeatTs: s.heartbeatTs,
    };
  },
};

// 编辑历史: 2026-09-29 21:37:55 小欧 - 新建: [63] 5.4 会话级流运行时唯一真源(commit 唯一写入口/快照 bump/
//   事件 emitEvent 双通道/终态资源释放/destroySession) — 小欧-2026-09-29 21:37:55
//   相对 [63] 5.4 原稿的 5 处修正 — 小欧-2026-09-29 21:37:55：
//   ① releaseUnsubscribed 原稿调 logger.info(frontend 无 logger 模块, 全仓 0 命中)→ 改 console.info。
//   ② clearTimeout(null) 显式守卫：浏览器虽容忍 null，但 ESLint no-restricted-globals 会报。
//   ③ 终态集抽为导出 TERMINAL_STATUSES + isTerminalStatus（原稿 store 的 TERMINAL 与 transport 的
//      TASK_TERMINAL_STATUSES 两份同义副本，DRY 违规）；transport 已改引本处。
//   ④ clearCompleted/evictSession/releaseUnsubscribed/destroySession 断连接前置 intentionalAbort=true：
//      否则主动 abort 引发的 AbortError 会被 5.3 handleTransportError 判为连接故障，弹错误并复活重连。
//   ⑤ 新增 pumpDone 字段（5.3 recoverFromIdle 依赖）：原稿仅 pumpActive 布尔，无法 await 旧泵退出。
//   另：sendMessage 返回 ResumeResult（原稿 void，UI 无从判断空流/失败终态）；
//   lastContextLinkMode 在 sendMessage 落值（原字段零写入，5.2 备份口径失真）；
//   状态机去 TERMINAL.includes(x as never) 断言，isTerminalStatus(string) 单一判定口。

// 编辑历史: 2026-09-29 22:47:10 小欧 - [63] 5.3/5.4 补齐 heartbeatTs 落点 3 处 — 小欧-2026-09-29 22:47:10：
//   ① EMPTY_SNAPSHOT 补 heartbeatTs: 0（0=未收到，与 ZERO_CLOCK 钟面恒 0 同口径）；
//   ② toBackup 落 heartbeatTs: s.heartbeatTs（随备份持久化，供刷新后恢复心跳钟面）；
//   ③ chatStreamPersistence.legacyToBackup 补 heartbeatTs: 0（legacy 数据无心跳信息）。
//   起因：5.6 迁移把 heartbeatTs 加入 SessionSnapshot 后三处初始化未补齐，tsc TS2741 报错。
//
// 编辑历史: 2026-09-29 23:22:19 小欧 - [63] 5.4 防退化修复：getClockSignals 改按会话缓存 — 小欧-2026-09-29 23:22:19：
//   症状：同 A5 零钟面锁死（本文件侧成因）。
//   成因：getClockSignals 原每次调用都新建 ref 对象；而 5.5 桥接 waitClock 用 useMemo 缓存，
//   首渲染时 session 未创建 → 拿到 ZERO_CLOCK 后被永久缓存（heartbeatTs 恒 0 时依赖永不变化）。
//   修复：新增会话字段 clockSignalsView，按会话惰性缓存、三个字段全为活 getter
//   （heartbeatTs 亦改活 getter，否则缓存对象会钉住陈旧心跳），与既有
//   getExecutionStepsRef 的 executionStepsRefView 同一模式（DRY，不引第二套抽象）。
//   修复后引用天然稳定，桥接侧 memo 是否命中都不再影响正确性。
