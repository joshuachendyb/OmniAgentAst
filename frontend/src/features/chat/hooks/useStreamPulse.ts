// 编辑历史: 2026-11-02 小欧 - 新建: 顶栏 SSE 流状态灯数据源。1s 采样 store 聚合快照(不订阅 store, 免每 token 重渲顶栏), 派生纯函数导出供单测 — 小欧-2026-11-02
import { useEffect, useState } from 'react';

import { chatStreamStore } from '../streams/chatStreamStore';
import type { StreamPulse } from '../streams/chatStreamStore';

/** 采样周期: 只展示"距今秒数", 1s 粒度足够 — 2026-11-02 小欧 */
const PULSE_TICK_MS = 1000;

/**
 * 静默判定: 30s 内没有任何字节(业务帧/心跳都算)才标黄。
 * 不能用 heartbeatTs 判健康 —— 后端只在静默 25s 时才发 `: ping`, 正常流式输出时业务帧不断、
 * 心跳反而不发, 用心跳年龄判"迟滞"会把最活跃的时刻判成异常(实测踩中)。 — 2026-11-02 小欧
 */
const DATA_STALE_SEC = 30;

export type StreamTone = 'ok' | 'warn' | 'error' | 'neutral';

export interface StreamPulseView {
  tone: StreamTone;
  badge: 'success' | 'processing' | 'warning' | 'error' | 'default';
  text: string;
  main: string;
  pulse: StreamPulse;
  /** 最近心跳距今秒；null = 本会话从未收到心跳（静默期才有心跳，流式输出中不会刷新） */
  heartbeatAgeSec: number | null;
  /** 最近收到任意字节距今秒；null = 本会话未产生数据 */
  dataAgeSec: number | null;
  /** 流进行中但长时间无任何字节（含心跳） */
  dataStale: boolean;
}

const ageOf = (ts: number, nowMs: number): number | null =>
  ts > 0 ? Math.max(0, Math.round((nowMs - ts) / 1000)) : null;

/**
 * 2026-11-02 小欧 - 流状态 → 灯态单一派生口（纯函数，行为可单测）。
 * 优先级：断流 > 重连/恢复 > 等确认 > 流进行中 > 已连接无推送 > 无流。
 * 判据全部取 store 既有字段，不新造状态。
 */
export const deriveStreamState = (
  p: StreamPulse,
  nowMs: number
): StreamPulseView => {
  const heartbeatAgeSec = ageOf(p.heartbeatTs, nowMs);
  const dataAgeSec = ageOf(p.lastDataTime, nowMs);
  const base = { pulse: p, heartbeatAgeSec, dataAgeSec };

  if (!p.active) {
    return {
      ...base,
      tone: 'neutral',
      badge: 'default',
      text: '无流',
      main: '当前没有进行中的任务流',
      dataStale: false,
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
      dataStale: false,
    };
  }
  if (p.reconnectStatus === 'reconnecting' || p.status === 'recovering') {
    return {
      ...base,
      tone: 'warn',
      badge: 'warning',
      text: '重连中',
      main: '连接中断，正按 after_seq 断点续传',
      dataStale: false,
    };
  }
  if (p.status === 'paused') {
    return {
      ...base,
      tone: 'warn',
      badge: 'warning',
      text: '等待确认',
      main: '任务在等人工确认，空闲计时已暂停',
      dataStale: false,
    };
  }
  if (p.isReceiving || p.status === 'active' || p.status === 'retrying') {
    // 2026-11-02 小欧 - 判据用 lastDataTime(任何字节)而非 heartbeatTs: 见 DATA_STALE_SEC 注释 — 小欧-2026-11-02
    const stale = dataAgeSec !== null && dataAgeSec >= DATA_STALE_SEC;
    return {
      ...base,
      tone: stale ? 'warn' : 'ok',
      badge: stale ? 'warning' : 'processing',
      text: stale ? '流静默' : '流进行中',
      main: stale
        ? `已 ${dataAgeSec} 秒未收到任何数据（业务帧与心跳均无）`
        : 'SSE 连接活跃，正在接收服务端事件',
      dataStale: stale,
    };
  }
  return {
    ...base,
    tone: 'neutral',
    badge: 'default',
    text: '已连接',
    main: '会话存在但当前无数据推送',
    dataStale: false,
  };
};

const sameView = (a: StreamPulseView, b: StreamPulseView): boolean =>
  a.tone === b.tone &&
  a.text === b.text &&
  a.main === b.main &&
  a.heartbeatAgeSec === b.heartbeatAgeSec &&
  a.dataAgeSec === b.dataAgeSec &&
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
