/**
 * HeaderWaitClock - 顶栏等待钟面(品牌字之后)  @author 小欧  @date 2026-11-03
 * 语义: 被挑中那条流「距最近业务帧」的等待秒数, 与胶囊/齿轮同源同一条流(唯一挑选口 buildStreamPulse)。
 * 口径: 起点取自数据(lastBizTs), 不按组件挂载起算 —— 否则进页面十秒后钟面就冒出来且永不消失。
 * 门槛: 与胶囊"流迟滞/流静默"同频(bizStale≥30s), 不许胶囊说"流持续"而旁边表盘已经在数
 *   (实测 2026-11-03: 10s 门槛会让表盘在 10~29s 抢跑, 且业务帧一刷新就消失、10s 后再冒, 反复闪烁)。
 * 分支: ClockStopwatch 原样继承(表盘/指针/秒数/心跳闪动/三档色/里程碑判定), 本组件只提供起点与主语;
 *   顶栏位置窄(hideNote): 文字由步骤级数码与胶囊承担, 表盘宽度恒定不挤布局。
 */
// 编辑历史: 2026-11-03 07:52:00 小欧 - 新建: 顶栏钟面从文本/工具/思考三处图标里拆出后的常驻落位,
//   只读 store(经 useStreamPulse 1s 采样), 无新订阅、无新请求 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 07:58:00 小欧 - 门槛改 bizStale(与胶囊流迟滞同频, 修"抢跑+闪烁"), 并 hideNote — 小欧-2026-11-03
import React from 'react';

import { ClockStopwatch } from '@/components/WaitingIcons/clockStopwatch';
import { useStreamPulse } from '@/features/chat/hooks/useStreamPulse';
import type { StreamPhase } from '@/features/chat/hooks/useStreamPulse';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';

/** 允许出顶栏钟面的档位: 业务帧静默(迟滞)、心跳也停(静默)、断线重连中 —— 三者都是"在等, 且没产出" */
const WAITING_PHASES: ReadonlySet<StreamPhase> = new Set([
  'stalled',
  'silent',
  'reconnecting',
]);

const HeaderWaitClock: React.FC = () => {
  const view = useStreamPulse();
  const p = view.pulse;
  // 无在跑任务 / 本轮还没收到业务帧(刚发出, 起点未知) / 未到静默门槛 / 待确认(人工确认期不算等) → 不渲染
  if (!p.sessionId || p.lastBizTs <= 0) return null;
  if (!view.bizStale || !WAITING_PHASES.has(view.phase)) return null;

  // 主语: 末段是 action(工具已发出、结果未到) → 工具, 其余(思考/决策/落字) → 等回复。
  //   仅影响 ≥120s 时的判定与 aria-label, 不影响计时与档位; 每秒随采样重读, 与流同频
  const steps = chatStreamStore.getExecutionStepsRef(p.sessionId).current;
  const last = steps.length > 0 ? steps[steps.length - 1] : undefined;
  const kind = last?.type === 'action' ? 'tool' : 'llm';

  return (
    <span className="header-wait-clock">
      <ClockStopwatch
        className="clock-stopwatch-header"
        sinceTs={p.lastBizTs}
        kind={kind}
        hideNote
        {...chatStreamStore.getClockSignals(p.sessionId)}
      />
    </span>
  );
};

export { HeaderWaitClock };
