// 编辑历史: 2026-09-17 小欧 - 新增: 心跳等待感知微型钟面独立控件(北京老陈定案):
//   短针贴内缘环带扫动(60s归零重扫)＋中央纯秒数(≥10s)＋心跳微闪光波(存活确认)＋三档色(绿/黄/橙红)
//   ＋整数分钟里程碑文字; 与等待图标并存(追加不替换) — 小欧-2026-09-17
// 编辑历史: 2026-11-03 07:52:00 小欧 - 计时起点可外给 sinceTs(顶栏=距最近业务帧, 不传=挂载起算);
//   里程碑文案改口语(等回复/工具已跑, ≥60min 折为小时+分), 新增 className 供顶栏实例区分 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 07:58:00 小欧 - 新增 hideNote(顶栏宽度硬约束: 只留表盘+秒数, 文字归步骤级钟面/胶囊) — 小欧-2026-11-03
// 编辑历史: 2026-11-03 08:12:00 小欧 - 计时/档位/文案抽到 waitTiming(与文字数码皮共用单一真源), 本文件只留表盘绘制 — 小欧-2026-11-03
import React from 'react';

import { APPEAR_SEC, useWaitTiming } from './waitTiming';
import type { ClockSignals } from '@/types/sse'; // 2026-09-17 小欧: 钟面信号打包类型(定义于类型层, 避免 types→components 反向依赖) — 小欧-2026-09-17

export interface ClockStopwatchProps extends ClockSignals {
  /** 里程碑文字主语: llm="等回复 N 分钟"; tool="工具已跑 N 分钟" */
  kind?: 'llm' | 'tool';
  /**
   * 2026-11-03 小欧 - 计时起点(epoch ms)。>0 时秒数 = Date.now() - sinceTs, 用于语义为
   *   "距某事实多久"的场景(顶栏: 距最近业务帧); 不传则沿用挂载起算。
   */
  sinceTs?: number;
  /** 附加类名(顶栏实例用: 样式/测试可与其它实例区分) */
  className?: string;
  /**
   * 2026-11-03 小欧 - 只留读数不写文字(顶栏实例): 顶栏宽度是硬约束(窄面板本就溢出),
   *   里程碑/断连文字由步骤级数码与三粒胶囊承担, 顶栏只保留固定宽度的表盘+秒数。
   *   组件能力不减: aria-label 仍带 note, 分支判定照旧。
   */
  hideNote?: boolean;
}

/** 钟面表盘: 顶栏那个大计时器的皮(北京老陈定案继承), 口径全部来自 waitTiming */
export const ClockStopwatch: React.FC<ClockStopwatchProps> = ({
  kind = 'llm',
  sinceTs,
  className,
  hideNote = false,
  ...signals
}) => {
  const { elapsedSec, color, note, beatTick } = useWaitTiming(signals, {
    kind,
    sinceTs,
  });
  if (elapsedSec < APPEAR_SEC) return null; // 短等待不显示

  const angle = (elapsedSec % 60) * 6; // 短针 60s 一圈归零重扫

  return (
    <span
      className={className ? `clock-stopwatch ${className}` : 'clock-stopwatch'}
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
      {!hideNote && note && (
        <span className="clock-stopwatch-note" style={{ color }}>
          {note}
        </span>
      )}
    </span>
  );
};
