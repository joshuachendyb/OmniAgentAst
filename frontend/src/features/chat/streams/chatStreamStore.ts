// [63] 5.4：会话级流运行时唯一真源——模块级单例 Store 持有 Map<sessionId, ChatStreamSession>、
//   SSE 连接、步骤与任务锚点。页面只订阅，卸载仅解绑（订阅者链表保证 L1：卸载不销毁流）。
//   状态写入唯一入口 commit()（SLAP：transport 只调 commit，不直写字段）。

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

// 编辑历史: 2026-09-30 10:35 小欧 - P0 根因修复后的死代码清理（北京老陈裁定「死的删除」）：
//   sendMessage 尾原 `if (d.status === 'idle' || d.status === 'recovering') d.status = 'active'` 删除。
//   不可达性（逐路径证毕）：P0 修复已把 active 兜底移入 sendStreamRequest 开篇 commit（transport:143），
//   本行执行时机在 `await sendStreamRequest()` 之后，status 必然是 pump 退出后的终态/paused/failed/active；
//   'recovering' 仅 GET 续传路径（transport:309 handleGetNotFound）赋值、'idle' 仅 resume 无 taskId 路径
    //   （backup invalid / adoptLiveTaskOrDraft）赋值，均不经过 sendMessage 主流程 → 条件恒 false。
//   与 P0 修复配套：修复前该分支是"已完成会话发新消息 final 被吞"（P0）的反向误修点，
//   修复后语义由 transport 单点承担，store 侧仅剩 pendingMessage 置 sent。
// 编辑历史: 2026-09-30 14:30 小欧 - 删 clearCompleted 越权写瞬态标志；evictOverflow 查在飞工作；清理收敛单一出口；restore 改展开式
// 编辑历史: 2026-09-30 18:14:06 小欧 - T1/H13 守卫修复（[81] v1.1 复核确认的实质项）：
//   T1: resume 补退避窗口守卫（reconnectTimeout≠null 回读当前态），防 restore 覆盖在飞状态致序号倒退 + 提前 GET；
//   H13: sendMessage 补空串守卫（return 'idle'），禁 ensureSession 造 '' 鬼会话，与 resume/stop 对称 — 小欧-2026-09-30 18:14:06
// 编辑历史: 2026-10-01 小欧 - 解 [1] B13/B4/B5（见 doc-10月优化/[1]刷新后显示其他任务结果）：
//   ①toBackup 补 lastBizTs/lastDataTime（钟面"静默升档"判据所依，原只在内存，刷新后恒 0 致长静默期不再升档）；
//   ②新增 findLiveTask(sessionId, excludeTaskId) 抽 DB 权威的"近 300s 内仍在执行"判定，由 attachActiveTask 与
//   resume 共用（DRY）——原判定散在两处且口径不一（B4 处根本没有 DB 校验），致"备份锚点陈旧"无处纠正 — 小欧-2026-10-01


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
import {
  sendStreamRequest,
  resumeStreamRequest,
  readAuthoritativeTask,
} from './chatStreamTransport';
import { taskControlApi, sessionTaskApi } from '@/services/api/task.api';
import type { SessionTaskItem } from '@/services/api/task.api';

/** 终态状态集（3.10.1 权威口径）：completed/failed/cancelled 由 chat_tasks 与 final 帧共同决定 */
export const TERMINAL_STATUSES = ['completed', 'failed', 'cancelled'] as const;

/** 2026-09-30 08:31 小欧 - 终态条目内存保留时长（沿用原 10 分钟口径）。
 *  仅删内存条目，sessionStorage 备份不受影响——重开该会话按 5.2 正常恢复。 */
const TERMINAL_TTL_MS = 600_000;

/** 2026-09-30 08:31 小欧 - 内存会话条目容量上限。
 *  超出时按"可回收时刻"先后 LRU 淘汰；活跃（在飞/非终态）与被订阅的会话永不被淘汰。 */
const MAX_SESSIONS = 32;

export function isTerminalStatus(status: string): boolean {
  return (TERMINAL_STATUSES as readonly string[]).includes(status);
}

/** 2026-09-30 07:58 小欧 - 会话状态 → ResumeResult 单一判定口。
 *  sendMessage 尾与 resume 活流守卫共用同一口径（DRY：终态/非终态二分只写一次，不两处各抄一遍）。 */
function resumeResultOf(s: ChatStreamSession): ResumeResult {
  return s.status === 'completed' || isTerminalStatus(s.status) ? 'terminal' : 'recovering';
}

/** 2026-09-30 07:58 小欧 - 该会话是否有在飞工作（活流守卫判据，单一判定口）。
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

// 2026-09-30 08:44:31 小欧 - render 期"缺会话"活视图（按 id 缓存）。
//   病根：getExecutionStepsRef 原无条件 ensureSession，与 [63] 5.4「getSnapshot 路径绝不创建」相悖；
//   useChatStreamSession 又在 render 期显式 ensureSession（该行已删）。二者使组件首渲染即在 Store
//   里建出会话条目——render 会被丢弃时这些条目纯属泄漏，且会挤占 D3 的 MAX_SESSIONS 容量。
//   设计：缺会话时返回**按 id 缓存的活视图**——getter 每次经 sessions.get(id) 现取，
//   故同一对象在会话出现后自动开始报告真值，既满足"render 不创建"，又不会像冻结零信号那样
//   把 useChatStreamSession 的 waitClock useMemo([id, heartbeatTs]) 永久钉在零钟面上。
//   回收：会话一创建即从本表移除（真视图 s.clockSignalsView / s.executionStepsRefView 接管），
//   evictSession / destroySession 删除条目时同步移除。
//
// 2026-09-30 小欧 - 补回收上限：本表对"永不建运行时"的 id 只进不出、无回收路径；
//   上限复用 MAX_SESSIONS，条目为可重建派生视图故超限整表清空而非 LRU
const MAX_MISSING_VIEWS = MAX_SESSIONS;
const missingViews = new Map<string, { clock: ClockSignals; steps: { current: ExecutionStep[] } }>();

/** 钟面活视图：三个字段全为 getter，写入经 commit 回真会话；会话不存在时写为 no-op（禁凭空建会话） */
function makeClockView(resolve: () => ChatStreamSession | undefined): ClockSignals {
  return {
    lastBizTsRef: {
      get current() {
        return resolve()?.lastBizTs ?? 0;
      },
      set current(v: number) {
        const s = resolve();
        if (s)
          commit(s, (d) => {
            d.lastBizTs = v;
          });
      },
    } as MutableRefObject<number>,
    lastDataTsRef: {
      get current() {
        return resolve()?.lastDataTime ?? 0;
      },
      set current(v: number) {
        const s = resolve();
        if (s)
          commit(s, (d) => {
            d.lastDataTime = v;
          });
      },
    } as MutableRefObject<number>,
    get heartbeatTs() {
      return resolve()?.heartbeatTs ?? 0;
    },
  };
}

/** 步骤活视图：与 makeClockView 同模式（DRY，不引第二套抽象） */
function makeStepsView(resolve: () => ChatStreamSession | undefined): {
  current: ExecutionStep[];
} {
  return {
    get current() {
      return resolve()?.executionSteps ?? [];
    },
    set current(v: ExecutionStep[]) {
      const s = resolve();
      if (s)
        commit(s, (d) => {
          d.executionSteps = v;
        });
    },
  };
}

/** 取（并按 id 缓存）缺会话视图；空 id 直接用 ZERO_CLOCK——无 id 即无会话，且 id 变化本身会让 memo 重算 */
function missingViewsOf(sessionId: string): { clock: ClockSignals; steps: { current: ExecutionStep[] } } {
  let v = missingViews.get(sessionId);
  if (!v) {
    // 2026-09-30 小欧 - 超上限整表清空（本表为可重建派生视图，清空不丢真实数据）
    if (missingViews.size >= MAX_MISSING_VIEWS) missingViews.clear();
    const resolve = (): ChatStreamSession | undefined => sessions.get(sessionId);
    v = { clock: makeClockView(resolve), steps: makeStepsView(resolve) };
    missingViews.set(sessionId, v);
  }
  return v;
}

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
  /** 2026-09-30 08:31 小欧 - 首次落终态的时刻（null = 未落终态）。
   *  双重职责：① 终态 TTL 排期的计时起点（与"是否曾零订阅"解耦）；② 容量淘汰的 LRU 排序键。 */
  terminalAt: number | null;
  /** 2026-09-30 08:31 小欧 - 终态 TTL 排期句柄（重排前先清，幂等不叠定时器）。 */
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
/** 终态 TTL 排期（幂等，模块级单点）：重排前先清旧句柄，终态时起算，到点交 evictSession。
 *  2026-09-30 小欧 - 从 chatStreamStore 方法抽为模块级函数（S2）：原先 commit() 反调
 *  chatStreamStore.scheduleTerminalEviction，而 chatStreamStore 定义在 commit 之后 →
 *  定义顺序倒置的循环依赖，仅靠"调用发生在模块初始化之后"侥幸成立。抽为模块级后
 *  commit 不再引用 chatStreamStore，倒置消除（evictSession 的引用只留在定时器回调里，
 *  运行时才求值，语义不变）。 */
function scheduleTerminalEvictOf(sessionId: string): void {
  const s = sessions.get(sessionId);
  if (!s || !isTerminalStatus(s.status)) return;
  if (s.terminalEvictTimer !== null) window.clearTimeout(s.terminalEvictTimer);
  s.terminalEvictTimer = window.setTimeout(() => {
    s.terminalEvictTimer = null;
    chatStreamStore.evictSession(sessionId);
  }, TERMINAL_TTL_MS);
}

export function commit(s: ChatStreamSession, fn: (d: ChatStreamSession) => void): void {
  // 2026-09-30 08:31 小欧 - 终态跃迁在此单点捕获（所有终态写入路径都经 commit，
  //   无需在各写入点分别设防），落终态即排期 TTL —— 排期与"是否曾零订阅"解耦。
  //   原稿把终态 TTL 嵌在 releaseUnsubscribed 的宽限期回调内，导致"用户盯着看完"的会话
  //   （全程有订阅者，宽限期回调首行即 return）永不被排期，标签页不关即永久泄漏。
  const wasTerminal = isTerminalStatus(s.status);
  fn(s);
  bump(s);
  schedulePersist(s);
  if (!wasTerminal && isTerminalStatus(s.status)) {
    s.terminalAt = Date.now();
    scheduleTerminalEvictOf(s.sessionId);
  } else if (wasTerminal && !isTerminalStatus(s.status)) {
    // 2026-09-30 08:31 小欧 - 离开终态即作废 terminalAt，维持"该字段 ⟺ 当前处于终态"
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

/** 构造备份快照（模块级，2026-09-30 小欧 - 从 chatStreamStore 方法抽出，见 scheduleTerminalEvictOf 的 S2 说明）：
 *  原先 persistNow 反调 this.toBackup、而 persistNow 又被模块级 schedulePersist 调用，
 *  形成"模块级函数 → 后定义的对象 → 该对象方法 → 模块级函数"的绕圈依赖。 */
function toBackupOf(sessionId: string): StreamBackup {
  const s = chatStreamStore.ensureSession(sessionId);
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
    // 2026-10-01 小欧 [1] B13: 钟面静默升档基线随备份落盘(刷新后不丢, 见 backupTypes 注释)
    lastBizTs: s.lastBizTs,
    lastDataTime: s.lastDataTime,
  };
}

function persistNowOf(sessionId: string): void {
  backupSave(toBackupOf(sessionId));
}

/** 落盘调度：普通帧 5s 防抖（句柄存 session.saveStepsTimer），终态立即写 */
function schedulePersist(s: ChatStreamSession): void {
  if (isTerminalStatus(s.status)) {
    persistNowOf(s.sessionId);
    return;
  }
  if (s.saveStepsTimer !== null) return; // 防抖窗内不再重排
  s.saveStepsTimer = window.setTimeout(() => {
    s.saveStepsTimer = null;
    persistNowOf(s.sessionId);
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

/** 查该会话近 300s 内仍在执行的任务（DB 权威）；excludeTaskId 用于排除已知锚点。
 *  2026-10-01 小欧 [1] B4/B5: 由 attachActiveTask 与 resume 共用(DRY)——
 *  原本判定散在两处且口径不一(B4 处根本没有 DB 校验), 致"备份锚点陈旧"无处纠正。 */
async function findLiveTask(
  sessionId: string,
  excludeTaskId: string | null
): Promise<SessionTaskItem | undefined> {
  const resp = await sessionTaskApi.listTasks(sessionId);
  const now = Date.now();
  const hits = resp.tasks.filter((t) => {
    if (t.status !== 'executing' || t.task_id === excludeTaskId) return false;
    const created = Date.parse(t.created_at);
    return Number.isNaN(now - created) || now - created <= 300_000;
  });
  return hits[hits.length - 1]; // 取最新
}

/** POST 前查重附着：created_at 300s 窗内 + executing 的活动任务只读跟随。
 *  附着即置 taskId/active 并 resume（不发第二 POST）；未附着返回 null 交调用方走正常路径。
 *
 *  2026-10-01 小欧 [1] B5: content 由"必填精确比对"放宽为"可选过滤"。
 *   原实现 `t.user_input !== content` 硬性精确比对，而 adoptLiveTaskOrDraft 传入的是
 *   **备份里的 pendingMessage.content**——刷新时该字段往往为空/陈旧/与在跑任务无关
 *   （任务由另一标签页、E2E、后台发起时本标签页根本无该内容）。结果是刷新后必然匹配不上，
 *   直接放弃该 executing 任务 → 无 serverTaskId → 右栏把在跑任务当历史任务读 DB → 显示别的任务结果。
 *   现 content 为空时只按"该会话最新 executing 任务"附着(listTasks 已按 sessionId 限定，不会串会话)；
 *   content 非空时保持原精确比对(POST 防双发场景需要同内容语义)。
 */
async function attachActiveTask(
  s: ChatStreamSession,
  content: string
): Promise<ResumeResult | null> {
  const active = await findLiveTask(s.sessionId, s.serverTaskId);
  if (!active || (content && active.user_input !== content)) return null;
  commit(s, (d) => {
    d.serverTaskId = active.task_id;
    d.pendingMessage = null;
    d.status = 'active';
  });
  persistNowOf(s.sessionId);
  return resumeStreamRequest(s);
}

/** 2026-09-30 08:31 小欧 - 容量上限淘汰（终态 LRU）。
 *  只淘汰"已无人订阅且已可回收"的条目，排序键 = 终态时刻 terminalAt ?? 退订时刻 releasedAt。
 *  两键皆 null（仍有订阅者）即不可回收——故正在跑/正在看的会话永不被淘汰。
 *  刚建的条目两键皆 null，天然不在候选内，无需特判"别淘汰自己"。
 *  逐个交 evictSession 复用其断连接/清定时器/删条目全套动作，不另写删除逻辑。 */
/**
 * 2026-09-30 小欧 - 定时器清理单一出口（6 个句柄）：原三处手抄且字段集各异（evictSession 仅
 *   3 个，漏 reconnectTimeout/firstChunkTimeout/intentionalAbortTimer，已致僵尸 GET 与误置真）
 */
function clearSessionTimers(s: ChatStreamSession): void {
  if (s.idleTimeout !== null) window.clearTimeout(s.idleTimeout);
  if (s.reconnectTimeout !== null) window.clearTimeout(s.reconnectTimeout);
  if (s.firstChunkTimeout !== null) window.clearTimeout(s.firstChunkTimeout);
  if (s.saveStepsTimer !== null) window.clearTimeout(s.saveStepsTimer);
  if (s.intentionalAbortTimer !== null) window.clearTimeout(s.intentionalAbortTimer);
  if (s.terminalEvictTimer !== null) window.clearTimeout(s.terminalEvictTimer);
  s.idleTimeout = null;
  s.reconnectTimeout = null;
  s.firstChunkTimeout = null;
  s.saveStepsTimer = null;
  s.intentionalAbortTimer = null;
  s.terminalEvictTimer = null;
}

/** 条目纯清理（自身不做任何准入判断）：断流 + 清全部定时器 + 删两处 Map。
 *  2026-09-30 小欧 - 抽此函数以免 evictSession 与 evictOverflow 兜底各抄一份清理逻辑（DRY）。
 *  判据由调用方各自负责：evictSession 有终态/订阅守卫；evictOverflow 兜底已自证零订阅零在飞。 */
function purgeSessionEntry(sessionId: string, s: ChatStreamSession): void {
  s.intentionalAbort = true;
  s.abortController?.abort();
  s.abortController = null;
  clearSessionTimers(s);
  s.pollSignal.aborted = true;
  sessions.delete(sessionId);
  missingViews.delete(sessionId); // 与条目同生命周期回收缺会话活视图，防该表独立增长
}

function evictOverflow(): void {
  if (sessions.size <= MAX_SESSIONS) return;
  const candidates = [...sessions.values()]
    .filter(
      (s) =>
        s.listeners.size === 0 &&
        s.eventListeners.size === 0 &&
        (isTerminalStatus(s.status) || s.status === 'idle') &&
        // 2026-09-30 小欧 - 叠加在飞工作判据：sendMessage 置 isProcessing 但不改 status，其前置
        //   网络 await 窗口内本会话仍是上轮终态+零订阅，完全符合淘汰条件 → 流跑在孤儿对象上
        !hasInflightWork(s)
    )
    .map((s) => ({ s, key: s.terminalAt ?? s.releasedAt }))
    .filter((x): x is { s: ChatStreamSession; key: number } => x.key !== null)
    .sort((a, b) => a.key - b.key); // 最旧可回收者先走
  for (const { s } of candidates) {
    if (sessions.size <= MAX_SESSIONS) break;
    chatStreamStore.evictSession(s.sessionId);
  }
  // 2026-09-30 小欧 - 硬上限兜底：上段判据若把全部候选否掉（如大量在飞或有订阅者），循环空转，
  //   而 MAX_SESSIONS 只是"触发淘汰的阈值"不是容量上限 → sessions 可无界增长。
  //   此处放宽为"零订阅 + 无在飞工作"（仍绝不动有订阅者与在飞流），按最后心跳时间最旧先删。
  if (sessions.size > MAX_SESSIONS) {
    const rest = [...sessions.values()]
      .filter(
        s =>
          s.listeners.size === 0 &&
          s.eventListeners.size === 0 &&
          !hasInflightWork(s) &&
          // 2026-10-01 小欧 [1] B14: 补终态/idle 守卫。原兜底分支不看 status, 遇"零订阅 + 无在飞
          //   工作判据未覆盖的中间态"(status=active 但连接刚断、瞬态已复位)会 purge 非终态会话,
          //   其内存态(含 pendingMessage/重连意图)被静默丢弃。本兜底只在超硬上限时触发, 仍按
          //   最旧先删, 但不得删掉终态之外尚有恢复价值的条目。
          (isTerminalStatus(s.status) || s.status === 'idle')
      )
      .sort((a, b) => (a.heartbeatTs ?? 0) - (b.heartbeatTs ?? 0));
    for (const s of rest) {
      if (sessions.size <= MAX_SESSIONS) break;
      purgeSessionEntry(s.sessionId, s);
    }
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
    // 2026-09-30 08:44:31 小欧 - 真会话已建立，缺会话活视图完成交接，即时移除防残留
    missingViews.delete(sessionId);
    evictOverflow();
    return s;
  },

  hasSession: (sessionId: string) => sessions.has(sessionId),

  /** 终态 TTL 排期（幂等）：实现已归模块级 scheduleTerminalEvictOf（见其注释的 S2 说明），
   *  本方法仅为对外 API 保留，内部不再另写一份。 */
  scheduleTerminalEviction(sessionId: string): void {
    scheduleTerminalEvictOf(sessionId);
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
    // 2026-09-30 小欧（H13 修复）：空串短路，禁 ensureSession 造 '' 鬼会话（对照 resume:599/stop:640
    //   已有守卫，本入口补齐对称防御；hook 侧 customSessionId??sessionId??'' 双 null 落空串即由此挡住）
    if (!sessionId) return 'idle';
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
        // 2026-09-30 10:35 小欧 - 删原 `idle||recovering → active` 死分支：active 兜底已移入
        //   sendStreamRequest 开篇，本行执行时机在其后 → 守卫恒 false（北京老陈裁定「死的删除」）
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
    // 2026-09-30 07:58 小欧 - 活流守卫——该会话已有在飞读循环/连接时直接回读当前状态。
    //   成因：useChatInit 每次 urlSessionId 变化都调 resume()，切回正在跑的会话时 restore() 用备份
    //   覆盖在飞状态（lastSeq/steps/currentResponse 倒退闪烁、isConnected 假 false），
    //   随后 resumeStreamRequest 再抢占 abortController，泄漏旧连接并起第二条流。
    //   落点选在 restore() 的唯一调用方 resume()：一次拦住"覆盖状态"与"起第二条流"两个后果
    //   （restore 不再重复设防，避免同一不变量两处判断）。
    const cur = sessions.get(sessionId);
    // 2026-09-30 小欧（T1 修复）：重连退避排期(reconnectTimeout≠null)也属于"状态正在被写"的窗口——
    //   仅凭三瞬态守卫会穿透：退避期 pumpActive/resumeInFlight/isProcessing 全 false，restore() 用旧备份
    //   覆盖在飞 lastSeq/steps（序号倒退）并提前 GET。reconnectTimeout 即"退避进行中"可靠标志，
    //   非 null 一律回读当前状态，绝不 restore/续传。
    if (cur && (hasInflightWork(cur) || cur.reconnectTimeout !== null))
      return resumeResultOf(cur);
    const s = this.ensureSession(sessionId);
    const restored = await this.restore(sessionId);
    // 2026-10-01 小欧 [1] B7: 备份判废(sessionStorage 已空, 如关标签页后重开)时也去 DB 找活任务。
    //   原先此处早退 'idle', 而备份是 sessionStorage 级的 —— 关掉标签页即整体消失, 于是
    //   "关页面再进来"永远恢复不了, 尽管后端 agent 仍在跑、结果也落库(纯前端没跟上)。
    //   两处 whenNone 各自保持改前的返回值语义: 判废路仍回 'idle'(书签访问等无活任务场景
    //   照旧走 initializeSession, loading/重试/404 处理一概不变), 备份有效但无 taskId 路仍回
    //   'pending_draft'。只有真附着到活任务才返回非 idle, 即只有那一种情况行为变。
    if (restored === 'invalid') return this.adoptLiveTaskOrDraft(s, 'idle');
    if (!s.serverTaskId) return this.adoptLiveTaskOrDraft(s, 'pending_draft');
    // 2026-10-01 小欧 [1] B4: DB 权威校验 —— 备份的 serverTaskId 只是缓存, 可能陈旧
    //   (旧任务非终态备份未被覆盖 / 另一入口发起的任务)。若 DB 显示该会话另有一个 executing
    //   任务, 备份锚点即错, 继续对它发 GET 会取回错误任务的数据。改以 DB 为准重新锚定。
    //   不选"丢弃备份走 adoptLiveTaskOrDraft", 因那会多绕一层且丢掉备份里的 lastSeq/steps。
    const live = await findLiveTask(s.sessionId, s.serverTaskId);
    if (live && live.task_id !== s.serverTaskId) {
      commit(s, (d) => {
        d.serverTaskId = live.task_id;
        d.status = 'active';
      });
      persistNowOf(s.sessionId);
    }
    return resumeStreamRequest(s);
  },

  /**
   * 去 DB 找出本会话正在跑的任务并附着；没有则交还草稿本，绝不自动 POST。
   * 2026-10-01 小欧 [1] B6: 原名 recoverWithoutTaskId 名不副实(它并非将就恢复, 而是主动查 taskId), 故改名。
   * @param whenNone 没附着到活任务时返回什么 —— 调用点各自的原语义, 不得统一。
   */
  async adoptLiveTaskOrDraft(
    s: ChatStreamSession,
    whenNone: ResumeResult
  ): Promise<ResumeResult> {
    const attached = await attachActiveTask(s, '');
    if (attached !== null) return attached;
    commit(s, (d) => {
      d.status = 'idle';
    });
    return whenNone;
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
      // STOP_RACE：任务已自然完成/不存在 → 回读权威终态（S1：回读逻辑已抽为 transport 的
      //   readAuthoritativeTask，本处只保留本路径特有的"兜底落 completed + 释放 + 文案"）
      const t = await readAuthoritativeTask(s);
      commit(s, (d) => {
        d.status = t && isTerminalStatus(t.status) ? (t.status as StreamStatus) : 'completed';
      });
      this.clearCompleted(sessionId); // 终态确认 → 释放全套流资源
      this.persistNow(sessionId);
      return { success: true, message: t ? `任务已结束（${t.status}）` : '任务不存在，可能已结束' };
    }
    commit(s, (d) => {
      d.status = 'cancelled';
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
    // 2026-09-30 小欧 - 定时器清理收敛到单一出口（原手抄 5 个、字段集与另两处不一致）
    clearSessionTimers(s);
    // 2026-09-30 小欧 - 收尾两字段在此统一关闭：原先只在 stop() 的两处分支各写 isReceiving，
    //   漏 isConnected（终态后 UI 仍显示已连接）且是重复写。clearCompleted 即本层唯一收尾真源
    //   （transport 侧同名语义的 markDisconnected 是它对 transport 会话操作的等价实现）。
    s.isReceiving = false;
    s.isConnected = false;
    // 2026-09-30 小欧 - clearSessionTimers 清掉了 terminalEvictTimer，但 TTL 仅在"终态跃迁"
    //   与"退订补排"两处排期，此处不重排则订阅常驻时该条目只能靠零订阅淘汰（实际永不删）→ 就地重排。
    this.scheduleTerminalEviction(sessionId);
    s.pollSignal.aborted = true; // 中止轮询观察
    s.isProcessing = false;
    // 2026-09-30 小欧 - 删对 pumpActive/resumeInFlight 的越权写入：abort() 只发信号、由各自
    //   finally 复位，提前置 false 会让双泵守卫失效而可建双流。isProcessing 保留（须能立即重发）
    s.reconnectAttempts = 0;
    commit(s, (d) => {
      d.reconnectStatus = 'idle';
    });
    s.pendingMessage = null;
    s.hitlWaitingKeys.clear(); // 待发/HITL 态随终态清空
  },

  /** 清空该会话已收步骤与正文缓冲（新请求/停止后置空）；真源清空与备份删除同一动作，
   *  故不走 commit 的落盘调度（防抖会把已删备份重新写回），截断在途防抖后直接 bump 通知。
   *  2026-10-01 小欧 [1] B2: 删除备份后**立即落一份空态快照**，消除"删了到重建"之间的裸窗口 ——
   *   原实现 backupRemove 后直到首个 commit(经 5s 防抖)才有备份，该窗口内刷新 → restore 读不到
   *   任何快照 → serverTaskId 与 metaFrames 全空，右栏遂把在跑任务当历史任务读 DB(缺陷成因之一)。 */
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
    // [1] B2: 即落空态快照(无旧 taskId/旧 steps 但结构完整), 消除删备份到重建之间的裸窗口——
    //   该窗口内刷新 → restore 读不到快照 → serverTaskId/metaFrames 全空, 右栏把在跑任务
    //   当历史任务读 DB。恢复路径据此走 adoptLiveTaskOrDraft 按会话在跑任务附着(B5)。
    persistNowOf(sessionId);
    bump(s);
  },

  /** 推导 ref 视图：读——session.executionSteps（commit 后即新值）；写——commit 进 Store。
   *  2026-09-30 08:44:31 小欧 - 会话不存在时**不再 ensureSession**（render 期禁创建），
   *   改返回按 id 缓存的活视图——会话稍后出现，同一对象自动开始报告真步骤（冻结空数组会永久陈旧）。
   *  2026-09-30 小欧 - 删空 id 哨兵分支（原 `sessionId === '' ? EMPTY_STEPS_VIEW : ...`）：
   *   生产两处调用点（transport 传 s.sessionId、useChatStreamSession 已先判空用 EMPTY_STEPS_REF）
   *   均不传空串，该分支物理不可达，属 YAGNI 残留。 */
  getExecutionStepsRef(sessionId: string): { current: ExecutionStep[] } {
    const s = sessions.get(sessionId);
    if (!s) return missingViewsOf(sessionId).steps;
    if (!s.executionStepsRefView) s.executionStepsRefView = makeStepsView(() => s);
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
   *  保持 ref 语义稳定，供 waitClock 消费；session 不存在返回按 id 缓存的零信号活视图（render 期不创建 session）。
   *  2026-09-30 08:44:31 小欧 - 原缺会话分支返回**冻结的** ZERO_CLOCK，而 5.5 桥接的
   *   waitClock 用 useMemo([id, snapshot.heartbeatTs]) 缓存——首渲染拿到冻结零信号后，会话随后
   *   建立也不会换引用（heartbeatTs 仍 0）→ 组件永久持有零钟面，等待动画与静默升档全失效。
   *   改为与真会话视图同构的活视图（同一 makeClockView 构造器，DRY）：会话出现后自动报真值。 */
  getClockSignals(sessionId: string): ClockSignals {
    const s = sessions.get(sessionId);
    if (!s) return sessionId === '' ? ZERO_CLOCK : missingViewsOf(sessionId).clock;
    if (!s.clockSignalsView) s.clockSignalsView = makeClockView(() => s);
    return s.clockSignalsView;
  },

  /** 宽限期后只释放客户端资源：不 cancel、不停任务、不删快照；
   *  终态快照再经终态 TTL 后删条目（sessionStorage 备份不受影响，重开按 5.2 恢复）。 */
  releaseUnsubscribed(sessionId: string, graceMs = 60_000): void {
    const s = sessions.get(sessionId);
    if (!s || s.listeners.size > 0) return;
    s.releasedAt = Date.now();
    // 2026-09-30 08:31 小欧 - 已落终态者立即排期 TTL，不等宽限期。
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
      // [1] B3: clearSessionTimers 会杀掉待执行的 saveStepsTimer, 若此后该任务再无 SSE 帧
      //   (连接已 abort), 这次落盘永久丢失 → 备份停留在旧内容(可能仍是上一个任务的 taskId)。
      //   故在清定时器**之前**先落一次盘, 保证备份与内存一致。
      // [1] B10: 原实现只断连接不清条目、也不复位 status, 条目 status 仍为 active;
      //   下次 resume 的活流守卫只看 pumpActive/resumeInFlight/isProcessing/reconnectTimeout
      //   四个瞬态(此时全 false) → 放行 → restore 用旧备份覆盖, 序号倒退/数据串。
      //   释放即客户端不再持有在飞状态, 非终态一律回落 idle(终态不动, 由 terminalEvict 回收)。
      if (!isTerminalStatus(cur.status)) {
        commit(cur, d => {
          d.status = 'idle';
        });
      }
      persistNowOf(sessionId);
      // 2026-09-30 小欧 - 改走 clearSessionTimers 单一出口（D2）：原只手抄 idle/reconnect 两个，
      //   字段集与另三处不一致，漏 firstChunkTimeout/saveStepsTimer/intentionalAbortTimer
      //   （漏 firstChunkTimeout 会留下到点才 abort 的僵尸定时器，正是 P1-5 同型病根）。
      clearSessionTimers(cur);
      console.info(
        `[Store] 无人订阅宽限期到，释放客户端资源 session=${sessionId}（任务未停，条目保留）`
      );
      // 2026-09-30 08:31 小欧 - 原此处"终态再 setTimeout(evictSession, 600_000)"
      //   整删——终态 TTL 已改由 commit 终态跃迁 / 本方法入口统一排期（scheduleTerminalEviction），
      //   保留会在有订阅者时静默空转，是 D3"用户盯着看完的会话永不被回收"的病根之一。
    }, graceMs);
  },

  /** 删除内存条目：只删 Map entry，不删 sessionStorage 备份，不碰后端任务 */
  evictSession(sessionId: string): void {
    const cur = sessions.get(sessionId);
    if (!cur || cur.listeners.size > 0) return;
    if (!isTerminalStatus(cur.status) && cur.status !== 'idle') return;
    purgeSessionEntry(sessionId, cur);
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
      // 2026-09-30 小欧 - 收敛到单一出口（原 for 循环形态，且漏置 terminalEvictTimer = null）
      clearSessionTimers(cur);
      sessions.delete(sessionId); // 移除 Map 条目（显式终局，不看 listeners.size）
      missingViews.delete(sessionId); // 2026-09-30 08:44:31 小欧 - 同 evictSession 回收缺会话活视图
    }
    backupRemove(sessionId); // 删快照
    saveDraft(sessionId, ''); // 清草稿
  },

  /** 实现已归模块级 persistNowOf（见其注释的 S2 说明），本方法仅为对外 API 保留 */
  persistNow(sessionId: string): void {
    persistNowOf(sessionId);
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
    // 2026-09-30 小欧 - 剥掉备份专属字段后整体展开：原手工列举 13 字段致已落盘的 heartbeatTs
    //   被静默丢弃（恢复后心跳钟面恒 0）；展开式使今后新增快照字段自动纳入，遗漏会被 TS 捕获。
    //   pendingMessage / lastContextLinkMode 是会话真实字段且备份里同名，必须留在 rest 内随之恢复
    //   （曾被一并 void 掉致待发草稿与上下文链接模式丢失，比原缺陷更严重）。
    const { version, revision, sessionId: _sid, taskId, steps, hitlWaitingKeys, updatedAt, isConnected, ...rest } = b;
    void version;
    void revision;
    void _sid;
    void taskId;
    void steps;
    void hitlWaitingKeys;
    void updatedAt;
    void isConnected;
    commit(s, (d) =>
      Object.assign(d, rest, {
        // 2026-10-01 小欧 [1] B8: 终态快照的 taskId 不作续传锚点。
        //   原无条件 serverTaskId = b.taskId，使"上次已完成任务"被当当前任务 → resumeStreamRequest
        //   对已完结 taskId 发 GET(after_seq)，同时守卫 activeTaskId===serverTaskId 被迫成立，
        //   右栏把在跑任务误判为"当前任务"或反之。终态任务无需续传(G3)，置 null 即可；
        //   steps/metaFrames 仍照常恢复，供给历史回放。
        serverTaskId: isTerminalStatus(b.status) ? null : b.taskId,
        executionSteps: b.steps.filter(
          (st) => !(st.type === 'action' && st.preview === true)
        ),
        // 不恢复 isConnected——连接态由在飞连接决定，恢复后未连即 false（见上方方法注释②）
        isConnected: false,
        // 2026-09-30 小欧 - reconnectStatus 同理显式归零：它被 Omit 出备份（连接态属运行时量），
        //   若不重置则沿用内存现值，刷新后可能残留 reconnecting/failed 而 UI 一直显示"重连中"
        reconnectStatus: 'idle',
        hitlWaitingKeys: new Set(b.hitlWaitingKeys ?? []),
      })
    );
    return 'ok';
  },

  /** 生成不可变备份快照：lastSeq 与 steps 必须来自同一 revision（原子性要求）。
   *  实现已归模块级 toBackupOf（见其注释的 S2 说明），本方法仅为对外 API 保留。 */
  toBackup(sessionId: string): StreamBackup {
    return toBackupOf(sessionId);
  },
};
