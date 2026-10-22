// 编辑历史: 2026-09-29 21:37:55 小欧 - 新建: [63] 5.2 持久化锚点组(L2)三窄接口 load/save/remove + isAnchorGroupIntact 同源校验 + 草稿 saveDraft/loadDraft；双 key 读取(v2 + legacy 归一) — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-29 21:37:55 小欧 - 两处按本章纪律"写入失败必须可诊断且不得伪装成功"补 try/catch:
//   ① saveDraft/loadDraft 文档原稿裸调 sessionStorage，容量满/隐私模式会把异常抛进草稿保存调用方;
//   ② load 原稿 getItem 在 try 外，同类环境下读快照直接抛给页面。逻辑与接口签名零变化 — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-10-01 小欧 - 解 [1] B9：isAnchorGroupIntact 末条判据由 `b.taskId !== null ||
//   b.pendingMessage === null` 改为"按已发/待发区分"（sent = pendingMessage 非 null 且 state !== 'queued'
//   时才要求 taskId 非空）。原判据在"待发草稿落盘"窗口（sendMessage 先 commit pendingMessage.state='queued'
//   + persistNow，而 start 帧尚未到达、taskId 仍是上一任务旧值或 null）会整份判废 → 待发草稿与已发意图全丢 — 小欧-2026-10-01
// 编辑历史: 2026-10-03 小欧 - legacyToBackup lastContextLinkMode 改名 linkEnabled
//   (与 backupTypes 同步) — 小欧-2026-10-03
// 编辑历史: 2026-10-13 18:10 小欧 - : 草稿存储 sessionStorage → localStorage(前者关浏览器即销毁);
//   保留期=跟随会话生命周期+7天孤儿兜底+50条上限(会话删则草稿删经 destroySession→saveDraft(sid,') 自动成立);
//   值改 {t,ts} 并兼容旧纯字符串; 清理曾挂在每次按键上(全量扫描 localStorage), 已加 5 秒节流
// 编辑历史: 2026-10-22 小欧 - legacyToBackup 补 sentRefLedger: []（台账入备份后成为必填字段，
//   legacy 数据无台账，补空数组）— 小欧-2026-10-22
// [63] 5.2：三窄接口 + 同文件辅助（isAnchorGroupIntact、saveDraft/loadDraft），
//        不碰 Store 内部字段、不触发 SSE、不改 React 状态
import type { StreamBackup } from './backupTypes';
import { emptyMetaFrames } from '@/types/sse'; // 值函数必须值 import（type-only 不可作值调用）

// 落盘/恢复前校验：结构完整性 + 同源（version/sessionId/taskId/revision/lastSeq 五项）
// v1.29 修：原实现只查 lastSeq/taskId 两项却声明五项，且用 (sent)===isReceiving 业务等式——
//   sendMessage 后 pendingMessage 恒 'sent' 而完成时 isReceiving=false，终态快照恒被判 invalid 丢弃；
//   业务态不参与结构校验（步骤恢复另见"恢复合并规则"：合法快照的 steps 一律不丢）
export function isAnchorGroupIntact(b: StreamBackup): boolean {
  const pending = b.pendingMessage;
  // 2026-10-01 小欧 [1] B9: 原末条写作 `b.taskId !== null || b.pendingMessage === null`，
  //   在"待发草稿落盘"窗口(sendMessage 先 commit pendingMessage.state='queued' + persistNow,
  //   start 帧尚未到达, taskId 仍是上一任务旧值或 null)会整份判废 → 待发草稿与已发意图全丢。
  //   判据应区分"已发"与"待发": 仅当消息确实已发出(state≠queued)才要求 taskId 非空。
  const sent = pending !== null && pending.state !== 'queued';
  return (
    b.version === 2 &&
    typeof b.sessionId === 'string' &&
    b.sessionId.length > 0 &&
    typeof b.revision === 'number' &&
    b.revision >= 0 &&
    b.lastSeq >= -1 &&
    (!sent || b.taskId !== null)
  );
}

// v1.29 修：旧备份在旧 key（useSSE.ts:119 `SSE_STORAGE_KEY='sse_execution_steps_backup'` →
//   `sse_execution_steps_backup_<sid>`，格式：裸数组 或 {steps,source,timestamp}）。
//   新锚点组格式用 `_v2_` 后缀新 key；load 必须**双 key 读取**——先 v2、没有再读旧 key 归一，
//   禁止旧数据读不到（原稿只读新 key，legacy 分支恒不可达 = 丢用户已见步骤）
const KEY = (sessionId: string) => `sse_execution_steps_backup_v2_${sessionId}`;
const LEGACY_KEY = (sessionId: string) =>
  `sse_execution_steps_backup_${sessionId}`;

// legacy（v1/裸数组）→ v2 最小完整快照归一：步骤与来源保留，锚点给保守初值
function legacyToBackup(sessionId: string, parsed: unknown): StreamBackup {
  const steps = Array.isArray(parsed)
    ? parsed
    : Array.isArray((parsed as { steps?: unknown[] })?.steps)
      ? (parsed as { steps: unknown[] }).steps
      : [];
  return {
    version: 2,
    revision: 0,
    sessionId,
    taskId: null,
    steps: steps as StreamBackup['steps'],
    hitlWaitingKeys: [],
    pendingMessage: null,
    linkEnabled: false,
    allowInterject: false, // 2026-10-07 小欧 - legacy 迁移默认
    updatedAt: Date.now(),
    // 2026-09-29 22:47:10 小欧 [63] 5.6：legacy 数据无心跳信息，按"未收到"给 0
    heartbeatTs: 0,
    lastSeq: -1,
    currentResponse: '',
    metaFrames: emptyMetaFrames(),
    usageAccum: { prompt: 0, completion: 0, total: 0 },
    isReceiving: false,
    isConnected: false,
    status: 'idle',
    pendingAuthorization: null,
    // 2026-10-22 小欧 - legacy 备份无台账（新增必填字段，补空数组）
    sentRefLedger: [],
  };
}

export function load(sessionId: string): StreamBackup | null {
  let raw: string | null = null;
  try {
    raw =
      sessionStorage.getItem(KEY(sessionId)) ??
      sessionStorage.getItem(LEGACY_KEY(sessionId));
  } catch (e) {
    // 隐私模式/存储被禁用：读取不可用即按"无快照"处理，不得把异常抛给页面
    console.warn('[Persistence] 快照读取失败，按无快照处理:', e);
    return null;
  }
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    // v2 原样返回，五项结构校验由调用方 isAnchorGroupIntact
    if (parsed && parsed.version === 2) return parsed as StreamBackup;
    return legacyToBackup(sessionId, parsed); // legacy 归一，步骤不丢
  } catch (e) {
    console.warn('[Persistence] 快照解析失败，按无效处理:', e);
    try {
      sessionStorage.removeItem(KEY(sessionId));
    } catch {
      /* 存储不可用时删键同样会抛，忽略即可（本就走无快照分支） */
    }
    return null; // 解析失败（结构性非法）才丢弃——5.2 校验纪律
  }
}

export function save(b: StreamBackup): void {
  try {
    sessionStorage.setItem(KEY(b.sessionId), JSON.stringify(b));
  } catch (e) {
    // 容量满/隐私模式：写入失败必须标记恢复能力不可用，禁止伪装成功（5.2 约束）
    console.warn('[Persistence] 快照写入失败，刷新恢复能力不可用:', e);
  }
}

export function remove(sessionId: string): void {
  try {
    sessionStorage.removeItem(KEY(sessionId));
  } catch (e) {
    console.warn('[Persistence] 快照删除失败:', e);
  }
}

/**
 * 输入草稿 per-session 持久化：视图卸载不丢草稿，与流快照 key 分离
 *
 * 2026-10-13 18:10 小欧 - : sessionStorage → localStorage。
 *   病根: sessionStorage 按浏览器会话隔离, 关掉标签页/浏览器即整体销毁 —— 草稿全丢。
 *   改 localStorage 后, 关浏览器/崩溃/换标签页都能恢复。
 *   保留期策略(北京老陈定案「C」): 跟随会话生命周期 + 7 天孤儿兜底
 *     - 会话删除时草稿跟着删: History 页三处删除均已调 chatStreamStore.destroySession(sid),
 *       其内部就是 saveDraft(sid, '') 删同一套键, 故此语义**自动成立**, 无需另拉清理线。
 *     - 7 天 TTL 只兜底"孤儿键"(会话记录已没了、草稿键还留着)。
 *     - 50 条上限防会话越开越多把 localStorage 撑满。
 */
const DRAFT_KEY = (sessionId: string) => `sse_draft_v1_${sessionId}`;
const DRAFT_PREFIX = 'sse_draft_v1_';
/** 孤儿键保留期: 7 天 */
const DRAFT_TTL_MS = 7 * 24 * 60 * 60 * 1000;
/** 同时保留的会话草稿上限, 超出按最旧淘汰 */
const DRAFT_MAX = 50;

interface DraftRecord {
  t: string;
  ts: number;
}

/** 解析草稿值: 兼容旧格式(纯字符串, 无 ts) —— 无 ts 的按"内容有效但不计龄"处理, 不丢内容 */
function parseDraft(raw: string): DraftRecord | null {
  if (!raw.trimStart().startsWith('{')) return { t: raw, ts: Date.now() };
  try {
    const o: unknown = JSON.parse(raw);
    if (typeof o !== 'object' || o === null) return null;
    const r = o as Partial<DraftRecord>;
    if (typeof r.t !== 'string') return null;
    return { t: r.t, ts: typeof r.ts === 'number' ? r.ts : Date.now() };
  } catch {
    return null;
  }
}

/**
 * 2026-10-13 18:45 小欧 - 清理节流。
 *   病根: evictStaleDrafts 要遍历整个 localStorage(不止草稿键, 还有 chat_session_state /
 *   execution_steps_backup 等), 而它原先在**每次按键**时被调用 —— O(总键数) 的同步扫描挂在
 *   打字路径上, 会话开多了键数上百时即成真实卡顿。改为距上次清理不足 EVICT_THROTTLE_MS
 *   直接跳过; 清理本身是"过期/超额才删"的兜底, 晚几秒执行无任何副作用。
 */
const EVICT_THROTTLE_MS = 5000;
let lastEvictAt = 0;

/** 清理过期键 + 超出上限时淘汰最旧; 供写入时调用, 内部按 EVICT_THROTTLE_MS 节流 */
function evictStaleDrafts(): void {
  const now = Date.now();
  if (now - lastEvictAt < EVICT_THROTTLE_MS) return;
  lastEvictAt = now;
  const keys: string[] = [];
  for (let i = 0; i < localStorage.length; i += 1) {
    const k = localStorage.key(i);
    if (k && k.startsWith(DRAFT_PREFIX)) keys.push(k);
  }
  const alive: Array<{ key: string; ts: number }> = [];
  for (const k of keys) {
    const rec = parseDraft(localStorage.getItem(k) ?? '');
    if (rec === null || now - rec.ts > DRAFT_TTL_MS) {
      localStorage.removeItem(k); // 过期或损坏 → 删
      continue;
    }
    alive.push({ key: k, ts: rec.ts });
  }
  if (alive.length <= DRAFT_MAX) return;
  alive.sort((a, b) => a.ts - b.ts);
  for (const r of alive.slice(0, alive.length - DRAFT_MAX))
    localStorage.removeItem(r.key);
}

export function saveDraft(sessionId: string, text: string): void {
  try {
    const key = DRAFT_KEY(sessionId);
    if (text) {
      localStorage.setItem(key, JSON.stringify({ t: text, ts: Date.now() }));
      evictStaleDrafts();
    } else {
      localStorage.removeItem(key);
    }
  } catch (e) {
    console.warn('[Persistence] 草稿保存失败，刷新后草稿不恢复:', e);
  }
}

export function loadDraft(sessionId: string): string {
  try {
    const key = DRAFT_KEY(sessionId);
    const raw = localStorage.getItem(key);
    if (raw === null) return '';
    const rec = parseDraft(raw);
    if (rec === null) return '';
    if (Date.now() - rec.ts > DRAFT_TTL_MS) {
      localStorage.removeItem(key); // 孤儿键过期, 就地清理
      return '';
    }
    return rec.t;
  } catch (e) {
    console.warn('[Persistence] 草稿读取失败:', e);
    return '';
  }
}
