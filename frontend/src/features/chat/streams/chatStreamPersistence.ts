// 编辑历史: 2026-09-29 21:37:55 小欧 - 新建: [63] 5.2 持久化锚点组(L2)三窄接口 load/save/remove + isAnchorGroupIntact 同源校验 + 草稿 saveDraft/loadDraft；双 key 读取(v2 + legacy 归一) — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-09-29 21:37:55 小欧 - 两处按本章纪律"写入失败必须可诊断且不得伪装成功"补 try/catch:
//   ① saveDraft/loadDraft 文档原稿裸调 sessionStorage，容量满/隐私模式会把异常抛进草稿保存调用方;
//   ② load 原稿 getItem 在 try 外，同类环境下读快照直接抛给页面。逻辑与接口签名零变化 — 小欧-2026-09-29 21:37:55
// 编辑历史: 2026-10-01 小欧 - 解 [1] B9：isAnchorGroupIntact 末条判据由 `b.taskId !== null ||
//   b.pendingMessage === null` 改为"按已发/待发区分"（sent = pendingMessage 非 null 且 state !== 'queued'
//   时才要求 taskId 非空）。原判据在"待发草稿落盘"窗口（sendMessage 先 commit pendingMessage.state='queued'
//   + persistNow，而 start 帧尚未到达、taskId 仍是上一任务旧值或 null）会整份判废 → 待发草稿与已发意图全丢 — 小欧-2026-10-01
// 编辑历史: 2026-10-03 小欧 - 文档[4] 5.8.16: legacyToBackup lastContextLinkMode 改名 linkEnabled
//   (与 backupTypes 同步) — 小欧-2026-10-03
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

// 输入草稿 per-session 持久化：视图卸载不丢草稿，与流快照 key 分离
const DRAFT_KEY = (sessionId: string) => `sse_draft_v1_${sessionId}`;

export function saveDraft(sessionId: string, text: string): void {
  try {
    if (text) sessionStorage.setItem(DRAFT_KEY(sessionId), text);
    else sessionStorage.removeItem(DRAFT_KEY(sessionId));
  } catch (e) {
    console.warn('[Persistence] 草稿保存失败，刷新后草稿不恢复:', e);
  }
}

export function loadDraft(sessionId: string): string {
  try {
    return sessionStorage.getItem(DRAFT_KEY(sessionId)) ?? '';
  } catch (e) {
    console.warn('[Persistence] 草稿读取失败:', e);
    return '';
  }
}
