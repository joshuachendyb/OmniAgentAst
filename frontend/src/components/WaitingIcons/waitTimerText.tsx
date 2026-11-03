/**
 * WaitTimerText - 步骤级等待计时: 纯数码 + 一个底色框(不摆表盘)  @author 小欧  @date 2026-11-03
 * 定案(北京老陈): 顶栏那个大计时器继承钟面表盘; 步骤标题行右侧/工具首行右侧只放文字数码,
 *   底色框按档位同色淡底+描边(绿=正常等/黄=业务静默60s/橙红=120s/灰=连接疑似中断)。
 * 口径与表盘同一处(waitTiming): 出现门槛 10s、起点=本步挂载、≥120s 里程碑文字只进 aria/title
 *   (不占宽度, 避免标题行忽宽忽窄)。
 */
// 编辑历史: 2026-11-03 08:12:00 小欧 - 新建: 步骤级计时改文字数码皮(表盘只留顶栏),
//   与被替换掉的表盘共用 waitTiming 阈值/文案, 功能分支(门槛/三档色/断连/里程碑)零丢失 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 08:40:00 小欧 - 底色框去描边, 只留淡底色(北京老陈定案) — 小欧-2026-11-03
import React from 'react';

import { APPEAR_SEC, formatClock, useWaitTiming } from './waitTiming';
import type { WaitTimingOptions } from './waitTiming';
import type { ClockSignals } from '@/types/sse';

export interface WaitTimerTextProps extends ClockSignals, WaitTimingOptions {
  /** 附加类名(工具行/标题行需要区分的场景) */
  className?: string;
}

const WaitTimerText: React.FC<WaitTimerTextProps> = ({
  kind = 'llm',
  sinceTs,
  className,
  ...signals
}) => {
  const { elapsedSec, color, tint, note } = useWaitTiming(signals, {
    kind,
    sinceTs,
  });
  if (elapsedSec < APPEAR_SEC) return null; // 短等待不显示, 免闪烁

  return (
    <span
      className={className ? `wait-timer-text ${className}` : 'wait-timer-text'}
      role="timer"
      aria-label={
        note ? `已等待 ${elapsedSec} 秒, ${note}` : `已等待 ${elapsedSec} 秒`
      }
      title={note ?? undefined}
      style={{
        color,
        backgroundColor: tint.bg,
      }}
    >
      {formatClock(elapsedSec)}
    </span>
  );
};

export { WaitTimerText };
