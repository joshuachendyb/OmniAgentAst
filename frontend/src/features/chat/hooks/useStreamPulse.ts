// 编辑历史: 2026-11-02 小欧 - 新建: 顶栏 SSE 流状态灯数据源。1s 采样 store 聚合快照(不订阅 store, 免每 token 重渲顶栏), 派生纯函数导出供单测 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - 状态机改为看业务帧: 心跳只证明连接没断, 不能证明后端在产出;
//   原判据用"任何字节"(含 `: ping`) → 只发心跳的空转流永远显示"流进行中" — 小欧-2026-11-02
import { useEffect, useState } from 'react';

import { chatStreamStore } from '../streams/chatStreamStore';
import type { StreamPulse } from '../streams/chatStreamStore';

/** 采样周期: 只展示"距今秒数", 1s 粒度足够 — 2026-11-02 小欧 */
const PULSE_TICK_MS = 1000;

/**
 * 静默阈值: 30s。
 *
 * 三处口径共用一个数, 靠的是后端的时序预算: 流一静默, 后端 25s 发一次 `: ping`;
 * 因此"30s 没业务帧"= 一个心跳周期已经过去还没产出, "30s 没字节"= 连心跳都断了一轮。
 * 两个判断都以此为界, 不各设一套数字 (改后端 HEARTBEAT_INTERVAL 须同步本值)。
 *
 * 关键区分 (这是原实现的病根):
 *   - lastBizTs  只被业务帧(chunk/action/observation/stats…)刷新 → 答"后端在不在干活"
 *   - heartbeatTs 只被 `: ping` 刷新                              → 答"连接断没断"
 *   - lastDataTime 任何字节都刷新                                 → 只用于和 transport 判死窗口对齐
 *   只看 lastDataTime 会把"只发心跳的空转"当成"正在产出", 灯永远是绿的。
 * — 2026-11-02 小欧
 */
const STALE_SEC = 30;

export type StreamTone = 'ok' | 'warn' | 'error' | 'neutral';

export interface StreamPulseView {
  tone: StreamTone;
  badge: 'success' | 'processing' | 'warning' | 'error' | 'default';
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
 * 优先级：断流 > 重连/恢复 > 等确认 > 有产出 > 只有心跳 > 都没了。
 * 判据全部取 store 既有字段，不新造状态。
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
  // "在产出"必须有证据: 有业务帧且未超阈值。从没收到过业务帧(会话刚建)一律不算产出 ——
  //   宁可让灯显示"等待后端", 也不要让只发心跳的空转流冒充"进行中" — 2026-11-02 小欧
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
      tone: 'neutral',
      badge: 'default',
      text: '无流',
      main: '当前没有进行中的任务流',
    };
  }
  // 2026-11-02 小欧 - status='failed' 是终态, store 聚合口不会把终态会话算作活跃流;
  //   该分支只作纯函数防御(外部直接喂终态快照时仍判中断), 真正的"流中断"由 reconnectStatus=failed 表达 — 小欧-2026-11-02
  if (p.status === 'failed' || p.reconnectStatus === 'failed') {
    return {
      ...base,
      tone: 'error',
      badge: 'error',
      text: '流中断',
      main: '连接已断开且未能自动恢复，可在会话内重新发送',
    };
  }
  if (p.reconnectStatus === 'reconnecting' || p.status === 'recovering') {
    return {
      ...base,
      tone: 'warn',
      badge: 'warning',
      text: '重连中',
      main: '连接中断，正按 after_seq 断点续传',
    };
  }
  if (p.status === 'paused') {
    return {
      ...base,
      tone: 'warn',
      badge: 'warning',
      text: '等待确认',
      main: '任务在等人工确认，空闲计时已暂停',
    };
  }
  if (p.isReceiving || p.status === 'active' || p.status === 'retrying') {
    // 一档: 业务帧在流动 → 后端真在产出
    if (hasOutput) {
      return {
        ...base,
        tone: 'ok',
        badge: 'processing',
        text: '流进行中',
        main: '后端正在推送事件',
      };
    }
    // 二档: 业务帧停了, 但心跳还在 → 连接正常、后端暂时没输出(思考/跑工具/排队)
    if (heartbeatAgeSec !== null && heartbeatAgeSec < STALE_SEC) {
      return {
        ...base,
        tone: 'warn',
        badge: 'warning',
        text: '流迟滞',
        main:
          bizAgeSec === null
            ? '心跳正常，尚未收到任何业务事件（后端在思考或执行工具，连接未断）'
            : `已 ${bizAgeSec} 秒无事件输出，心跳正常（后端在思考或执行工具，连接未断）`,
      };
    }
    // 三档: 心跳也过期 → 连保活都断了, 只等 transport 60s 判死
    return {
      ...base,
      tone: 'warn',
      badge: 'warning',
      text: '流静默',
      main: `已 ${dataAgeSec ?? 0} 秒无任何数据（业务帧与心跳均无）`,
    };
  }
  return {
    ...base,
    tone: 'neutral',
    badge: 'default',
    text: '已连接',
    main: '会话存在但当前无数据推送',
  };
};

const sameView = (a: StreamPulseView, b: StreamPulseView): boolean =>
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
  a.pulse.activeSessions === b.pulse.activeSessions;

/** 2026-11-02 小欧 - 顶栏流状态灯: 1s 采样。派生结果无变化时返回旧引用, 无谓重渲为零。 */
export function useStreamPulse(): StreamPulseView {
  const [view, setView] = useState<StreamPulseView>(() =>
    deriveStreamState(chatStreamStore.getPulse(), Date.now())
  );

  useEffect(() => {
    const tick = () => {
      const next = deriveStreamState(chatStreamStore.getPulse(), Date.now());
      setView((prev) => (sameView(prev, next) ? prev : next));
    };
    tick();
    const id = window.setInterval(tick, PULSE_TICK_MS);
    return () => window.clearInterval(id);
  }, []);

  return view;
}
