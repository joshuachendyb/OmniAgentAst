// 编辑历史: 2026-11-02 小欧 - 新建: 顶栏流状态灯数据源, 1s 采样 store 聚合快照(不订阅 store, 免每 token 重渲顶栏) — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 判据拆三线: lastBizTs=有无产出 / heartbeatTs=连接断没断 / lastDataTime=对齐 60s 判死; 补"连接中"档 — 小欧-2026-11-02
// 编辑历史: 2026-11-03 06:40:41 小欧 - 8 档各带 phase 标识(表现层按它选视觉, 不拿中文文案当键); sameView 同步比较 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 06:52:40 小欧 - 标签去术语并统一 3 字: 无流→无任务 / 流进行中→流持续 / 等待确认→待确认,
//   八档等宽, 胶囊不因档位跳宽; 流持续与流迟滞成对(在出数 / 出数迟滞), 只改文案, phase 与判据不变 — 小欧-2026-11-03
import { useSyncExternalStore } from 'react';

import { chatStreamStore } from '../streams/chatStreamStore';
import type { StreamPulse } from '../streams/chatStreamStore';
import type { Tone } from '../../../utils/tone';

/** 采样周期: 只展示"距今秒数", 1s 粒度足够 — 2026-11-02 小欧 */
const PULSE_TICK_MS = 1000;

/**
 * 静默阈值 30s = 后端心跳上限 25s(settings_registry range_[5,25]) + 5s 余量;
 * 心跳必先于阈值到达, 灯不会在"正常的静默期"掉到更重的档 — 2026-11-02 小欧
 */
const STALE_SEC = 30;

export type StreamTone = Tone;

/** 2026-11-03 06:40:41 小欧 - 8 档状态名(与 CSS 类 spin-<phase> 一一对应):
 *  表现层只认 phase, 不再拿中文文案当判断键(改文案不会悄悄失效) — 小欧-2026-11-03 */
export type StreamPhase =
  | 'idle'
  | 'connecting'
  | 'running'
  | 'stalled'
  | 'reconnecting'
  | 'waiting'
  | 'silent'
  | 'down';

export interface StreamPulseView {
  phase: StreamPhase;
  tone: StreamTone;
  text: string;
  main: string;
  pulse: StreamPulse;
  /** 最近心跳距今秒；null = 本会话从未收到心跳（静默期才有心跳，流式输出中不会刷新） */
  heartbeatAgeSec: number | null;
  /** 最近业务帧距今秒；null = 本会话从未收到业务帧 — 判"有没有产出"的唯一依据 */
  bizAgeSec: number | null;
  /** 最近收到任意字节（含心跳）距今秒；null = 本会话未产生数据 — 只用于对齐 transport 判死窗口 */
  dataAgeSec: number | null;
  /** 业务帧已静默（≥30s 无产出） */
  bizStale: boolean;
  /** 连心跳都没有了（≥30s 无任何字节） */
  dataStale: boolean;
}

const ageOf = (ts: number, nowMs: number): number | null =>
  ts > 0 ? Math.max(0, Math.round((nowMs - ts) / 1000)) : null;

/**
 * 2026-11-02 小欧 - 流状态 → 灯态单一派生口（纯函数，可单测）。
 * 优先级：断流 > 重连/恢复 > 等确认 > 未建流 > 有产出 > 只有心跳 > 都没了。
 */
export const deriveStreamState = (
  p: StreamPulse,
  nowMs: number
): StreamPulseView => {
  const heartbeatAgeSec = ageOf(p.heartbeatTs, nowMs);
  const dataAgeSec = ageOf(p.lastDataTime, nowMs);
  const bizAgeSec = ageOf(p.lastBizTs, nowMs);
  const bizStale = bizAgeSec !== null && bizAgeSec >= STALE_SEC;
  const dataStale = dataAgeSec !== null && dataAgeSec >= STALE_SEC;
  // "在产出"必须有证据: 有业务帧且未超阈值。从没收到过业务帧一律不算产出 — 2026-11-02 小欧
  const hasOutput = bizAgeSec !== null && bizAgeSec < STALE_SEC;
  const base = {
    pulse: p,
    heartbeatAgeSec,
    bizAgeSec,
    dataAgeSec,
    bizStale,
    dataStale,
  };

  if (!p.active) {
    return {
      ...base,
      phase: 'idle',
      tone: 'neutral',
      text: '无任务',
      main: '当前没有进行中的任务流',
    };
  }
  if (p.status === 'failed' || p.reconnectStatus === 'failed') {
    return {
      ...base,
      phase: 'down',
      tone: 'error',
      text: '流中断',
      main: '连接已断开且未能自动恢复，可在会话内重新发送',
    };
  }
  if (p.reconnectStatus === 'reconnecting' || p.status === 'recovering') {
    return {
      ...base,
      phase: 'reconnecting',
      tone: 'warn',
      text: '重连中',
      main: '连接中断，正按 after_seq 断点续传',
    };
  }
  if (p.status === 'paused') {
    return {
      ...base,
      phase: 'waiting',
      tone: 'warn',
      text: '待确认',
      main: '任务在等人工确认，空闲计时已暂停',
    };
  }
  // 请求已发出、读循环还没建立(响应头未到): 不是"没产出", 只是还没开始收 — 2026-11-02 小欧
  if (!p.pumpActive) {
    return {
      ...base,
      phase: 'connecting',
      tone: 'neutral',
      text: '连接中',
      main: '请求已发出，等待后端开始推送事件',
    };
  }
  if (hasOutput) {
    return {
      ...base,
      phase: 'running',
      tone: 'ok',
      text: '流持续',
      main: '后端正在推送事件',
    };
  }
  // 业务帧停了, 但心跳还在 → 后端在思考/跑工具, 连接未断
  if (heartbeatAgeSec !== null && heartbeatAgeSec < STALE_SEC) {
    return {
      ...base,
      phase: 'stalled',
      tone: 'warn',
      text: '流迟滞',
      main:
        bizAgeSec === null
          ? '心跳正常，尚未收到业务事件（后端在思考或执行工具，连接未断）'
          : `已 ${bizAgeSec} 秒无事件输出，心跳正常（后端在思考或执行工具，连接未断）`,
    };
  }
  // 心跳也过期 → 连保活都断了, 只等 transport 60s 判死。橘红: 比迟滞更重, 但还没到中断
  return {
    ...base,
    phase: 'silent',
    tone: 'alert',
    text: '流静默',
    main:
      dataAgeSec === null
        ? '尚未收到任何数据（业务帧与心跳均无）'
        : `已 ${dataAgeSec} 秒无任何数据（业务帧与心跳均无）`,
  };
};

const sameView = (a: StreamPulseView, b: StreamPulseView): boolean =>
  a.phase === b.phase &&
  a.tone === b.tone &&
  a.text === b.text &&
  a.main === b.main &&
  a.heartbeatAgeSec === b.heartbeatAgeSec &&
  a.bizAgeSec === b.bizAgeSec &&
  a.dataAgeSec === b.dataAgeSec &&
  a.bizStale === b.bizStale &&
  a.dataStale === b.dataStale &&
  a.pulse.sessionId === b.pulse.sessionId &&
  a.pulse.status === b.pulse.status &&
  a.pulse.reconnectStatus === b.pulse.reconnectStatus &&
  a.pulse.serverTaskId === b.pulse.serverTaskId &&
  a.pulse.activeSessions === b.pulse.activeSessions &&
  a.pulse.pumpActive === b.pulse.pumpActive;

// 2026-11-02 小欧 - 全应用共用一个 1s ticker + 一份快照: 顶栏两个胶囊读同一事实, 不同步各自的定时器 — 小欧-2026-11-02
let cachedView: StreamPulseView | null = null;
let timer: number | null = null;
const listeners = new Set<() => void>();

const readView = (): StreamPulseView => {
  const next = deriveStreamState(chatStreamStore.getPulse(), Date.now());
  if (!cachedView || !sameView(cachedView, next)) cachedView = next;
  return cachedView;
};

const subscribe = (listener: () => void): (() => void) => {
  listeners.add(listener);
  if (timer === null) {
    timer = window.setInterval(() => {
      readView();
      listeners.forEach((fn) => fn());
    }, PULSE_TICK_MS);
  }
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && timer !== null) {
      window.clearInterval(timer);
      timer = null;
    }
  };
};

/** 2026-11-02 小欧 - 顶栏流状态灯: 共享 1s 采样, 派生结果无变化时引用不变, 无谓重渲为零。 */
export function useStreamPulse(): StreamPulseView {
  return useSyncExternalStore(subscribe, readView, readView);
}
