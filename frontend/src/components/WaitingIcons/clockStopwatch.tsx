// 编辑历史: 2026-09-17 小欧 - 新增: 心跳等待感知微型钟面独立控件(北京老陈[46]第四章定案):
//   短针贴内缘环带扫动(60s归零重扫)＋中央纯秒数(≥10s)＋心跳微闪光波(存活确认)＋三档色(绿/黄/橙红)
//   ＋整数分钟里程碑文字; 与等待图标并存(追加不替换) — 小欧-2026-09-17
import React, { useEffect, useRef, useState } from 'react';
import { Colors } from '@/utils/stepStyles';
import type { ClockSignals } from '@/types/sse'; // 2026-09-17 小欧 [46]: 钟面信号打包类型(定义于类型层, 避免 types→components 反向依赖) — 小欧-2026-09-17

const APPEAR_SEC = 10; // 钟面出现门槛(短等待避免闪烁)
const YELLOW_SEC = 60; // 业务静默转黄
const ORANGE_SEC = 120; // 业务静默转橙红(里程碑文字起点)
const DATA_LOST_SEC = 60; // 任意数据静默≥60s=连接疑似中断(与 useSSE IDLE_TIMEOUT 同源)

const LEVEL_COLOR = {
  green: Colors.SUCCESS, // #52c41a
  yellow: Colors.WARNING, // #AD6800
  orange: Colors.ORANGE_RED, // #fa541c
  gray: Colors.TEXT.TERTIARY, // #999999
} as const;

type Level = keyof typeof LEVEL_COLOR;

export interface ClockStopwatchProps extends ClockSignals {
  /** 里程碑文字主语: llm="等 LLM 已达 N 分钟"; tool="工具执行已达 N 分钟" */
  kind?: 'llm' | 'tool';
}

export const ClockStopwatch: React.FC<ClockStopwatchProps> = ({
  lastBizTsRef,
  lastDataTsRef,
  heartbeatTs,
  kind = 'llm',
}) => {
  // 计时起点 = 组件挂载时刻(performance.now 差值, 防系统时钟跳变/后台节流丢秒)
  const startedAtRef = useRef<number>(performance.now());
  const [, setTick] = useState(0);
  const [beatTick, setBeatTick] = useState(0);

  // 每秒 tick: 驱动短针/秒数/档位刷新; 档位在渲染期直接读 ref(零高频 setState)
  useEffect(() => {
    const id = window.setInterval(() => setTick((t) => t + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  // 心跳到达 → 盘外圈重放一道光波(存活确认, 不参与计时)
  useEffect(() => {
    if (heartbeatTs > 0) setBeatTick((t) => t + 1);
  }, [heartbeatTs]);

  const elapsedSec = Math.floor(
    (performance.now() - startedAtRef.current) / 1000
  );
  if (elapsedSec < APPEAR_SEC) return null; // 短等待不显示

  // 基线未初始化(<=0)视为无静默, 防首帧误判灰档/升档
  const bizSilenceSec =
    lastBizTsRef.current > 0
      ? Math.floor((Date.now() - lastBizTsRef.current) / 1000)
      : 0;
  const dataSilenceSec =
    lastDataTsRef.current > 0
      ? Math.floor((Date.now() - lastDataTsRef.current) / 1000)
      : 0;

  let level: Level = 'green';
  let note: string | null = null;
  if (dataSilenceSec >= DATA_LOST_SEC) {
    level = 'gray';
    note = '连接疑似中断';
  } else if (bizSilenceSec >= ORANGE_SEC) {
    level = 'orange';
    note =
      kind === 'tool'
        ? `工具执行已达 ${Math.floor(bizSilenceSec / 60)} 分钟`
        : `等 LLM 已达 ${Math.floor(bizSilenceSec / 60)} 分钟`;
  } else if (bizSilenceSec >= YELLOW_SEC) {
    level = 'yellow';
  }


  const color = LEVEL_COLOR[level];
  const angle = (elapsedSec % 60) * 6; // 短针 60s 一圈归零重扫

  return (
    <span
      className="clock-stopwatch"
      role="img"
      aria-label={
        note ? `已等待 ${elapsedSec} 秒, ${note}` : `已等待 ${elapsedSec} 秒`
      }
    >
      {/* 尺寸 1.4em 与思考/行动等待图标对齐(工具图标 1.1em 略小, 钟面为其辅助时长信息) — 小欧-2026-09-17 */}
      <svg viewBox="0 0 36 36" width="1.4em" height="1.4em">
        {/* 心跳微闪光波(外圈, 每次心跳重放; key 变更强制重挂以重启动画) */}
        <circle
          key={beatTick}
          className={beatTick > 0 ? 'clock-beat-wave' : undefined}
          cx="18"
          cy="18"
          r="16"
          fill="none"
          stroke={color}
          strokeWidth="1.5"
        />
        {/* 内缘轨道环带 */}
        <circle
          cx="18"
          cy="18"
          r="13"
          fill="none"
          stroke={color}
          strokeWidth="1"
          opacity="0.3"
        />
        {/* 短针: 贴内缘环带扫动(r13→r9), 不穿中心 */}
        <line
          x1="18"
          y1="5"
          x2="18"
          y2="9"
          stroke={color}
          strokeWidth="2"
          strokeLinecap="round"
          transform={`rotate(${angle} 18 18)`}
        />
        {/* 中央纯秒数(≥10s, 无单位; 等宽字体防抖动) */}
        <text
          x="18"
          y="18"
          textAnchor="middle"
          dominantBaseline="central"
          fontSize="11"
          fontWeight="600"
          fill={color}
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          {elapsedSec}
        </text>
      </svg>
      {note && (
        <span className="clock-stopwatch-note" style={{ color }}>
          {note}
        </span>
      )}
    </span>
  );
};
