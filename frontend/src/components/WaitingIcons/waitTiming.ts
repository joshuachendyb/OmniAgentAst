/**
 * waitTiming - 等待计时的唯一口径(表盘与文字两套皮共用)  @author 小欧  @date 2026-11-03
 * 分工: 本模块只算"等了多久/该什么色/该说什么", 不画任何东西;
 *   渲染分两皮 —— 顶栏钟面(clockStopwatch, 北京老陈定案继承) 与 步骤级文字数码(waitTimerText)。
 * 口径: 起点 = sinceTs(语义为"距某事实多久", 如顶栏距最近业务帧) 或 挂载时刻(步骤级"本步等了多久")。
 */
// 编辑历史: 2026-11-03 08:12:00 小欧 - 新建: 从 clockStopwatch 抽出计时/档位/文案(单一真源),
//   供表盘(顶栏)与文字数码(步骤标题行)两皮共用, 阈值与判定只此一处 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 08:40:00 小欧 - LEVEL_TINT 去描边只留底色(北京老陈: 有边线不好看) — 小欧-2026-11-03
import { useEffect, useRef, useState } from 'react';

import { Colors } from '@/utils/stepStyles';
import type { ClockSignals } from '@/types/sse';

export const APPEAR_SEC = 10; // 出现门槛(短等待避免闪烁)
export const YELLOW_SEC = 60; // 业务静默转黄
export const ORANGE_SEC = 120; // 业务静默转橙红(里程碑文字起点)
export const DATA_LOST_SEC = 60; // 任意数据静默≥60s=连接疑似中断(与 useSSE IDLE_TIMEOUT 同源)

export type WaitLevel = 'green' | 'yellow' | 'orange' | 'gray';

export const LEVEL_COLOR: Record<WaitLevel, string> = {
  green: Colors.SUCCESS, // #52c41a
  yellow: Colors.WARNING, // #AD6800
  orange: Colors.ORANGE_RED, // #fa541c
  gray: Colors.TEXT.TERTIARY, // #999999
};

/** 文字数码的底色框: 同色淡底(无描边, 北京老陈定案: 有边线不好看), 三档一眼可辨(灰=连接疑似中断) */
export const LEVEL_TINT: Record<WaitLevel, { bg: string }> = {
  green: { bg: 'rgba(82, 196, 26, 0.10)' },
  yellow: { bg: 'rgba(173, 104, 0, 0.10)' },
  orange: { bg: 'rgba(250, 84, 28, 0.10)' },
  gray: { bg: 'rgba(153, 153, 153, 0.12)' },
};

/** 里程碑文案口径: <60min 只报分钟, ≥60min 折"X 小时 Y 分"(不出现"等回复 185 分钟") */
export const formatSpan = (sec: number): string => {
  const min = Math.floor(sec / 60);
  return min >= 60
    ? `${Math.floor(min / 60)} 小时 ${min % 60} 分`
    : `${min} 分钟`;
};

/** 数码读数: <1min 报秒(12s), ≥1min 报 mm:ss(1:23), ≥1h 报 h:mm:ss(1:02:03), 等宽不抖 */
export const formatClock = (sec: number): string => {
  if (sec < 60) return `${sec}s`;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = sec % 60;
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m);
  return h > 0
    ? `${h}:${mm}:${String(s).padStart(2, '0')}`
    : `${mm}:${String(s).padStart(2, '0')}`;
};

export interface WaitTimingOptions {
  /** 里程碑文字主语: llm="等回复 N 分钟"; tool="工具已跑 N 分钟" */
  kind?: 'llm' | 'tool';
  /** 计时起点(epoch ms): >0 按该事实时刻算, 不传则按组件挂载时刻算 */
  sinceTs?: number;
}

export interface WaitTiming extends ClockSignals {
  /** 已等秒数(未到 APPEAR_SEC 时调用方自行不渲染) */
  elapsedSec: number;
  level: WaitLevel;
  color: string;
  tint: { bg: string };
  /** ≥120s 里程碑 / ≥60s 无任何数据(断连) 时的说明文字, 无色档时为 null */
  note: string | null;
  /** 心跳计数(表盘外圈光波用; 文字皮不用, 但保持同源) */
  beatTick: number;
}

export const useWaitTiming = (
  signals: ClockSignals,
  { kind = 'llm', sinceTs }: WaitTimingOptions = {}
): WaitTiming => {
  // 计时起点 = 挂载时刻(performance.now 差值, 防系统时钟跳变/后台节流丢秒);
  //   外给 sinceTs 时改按该事实时刻算, 挂载时刻不再参与 — 2026-11-03 小欧
  const startedAtRef = useRef<number>(performance.now());
  const [, setTick] = useState(0);
  const [beatTick, setBeatTick] = useState(0);

  // 每秒 tick: 驱动读数/档位刷新; 档位在渲染期直接读 ref(零高频 setState)
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  // 心跳到达 → 表盘外圈重放一道光波(存活确认, 不参与计时)
  const { heartbeatTs } = signals;
  useEffect(() => {
    if (heartbeatTs > 0) setBeatTick((t) => t + 1);
  }, [heartbeatTs]);

  const elapsedSec = sinceTs
    ? Math.max(0, Math.floor((Date.now() - sinceTs) / 1000))
    : Math.floor((performance.now() - startedAtRef.current) / 1000);

  // 基线未初始化(<=0)视为无静默, 防首帧误判灰档/升档
  const bizSilenceSec =
    signals.lastBizTsRef.current > 0
      ? Math.floor((Date.now() - signals.lastBizTsRef.current) / 1000)
      : 0;
  const dataSilenceSec =
    signals.lastDataTsRef.current > 0
      ? Math.floor((Date.now() - signals.lastDataTsRef.current) / 1000)
      : 0;

  let level: WaitLevel = 'green';
  let note: string | null = null;
  if (dataSilenceSec >= DATA_LOST_SEC) {
    level = 'gray';
    note = '连接疑似中断';
  } else if (bizSilenceSec >= ORANGE_SEC) {
    level = 'orange';
    note =
      kind === 'tool'
        ? `工具已跑 ${formatSpan(bizSilenceSec)}`
        : `等回复 ${formatSpan(bizSilenceSec)}`;
  } else if (bizSilenceSec >= YELLOW_SEC) {
    level = 'yellow';
  }

  return {
    ...signals,
    elapsedSec,
    level,
    color: LEVEL_COLOR[level],
    tint: LEVEL_TINT[level],
    note,
    beatTick,
  };
};
