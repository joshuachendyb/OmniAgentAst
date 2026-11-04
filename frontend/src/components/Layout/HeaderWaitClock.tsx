/**
 * HeaderWaitClock - 顶栏等待钟面(品牌字之后)  @author 小欧  @date 2026-11-03
 * 起点取 lastBizTs(不按挂载起算), 门槛与胶囊"流迟滞"同频(bizStale≥30s)防抢跑闪烁, 本组件只提供起点与主语。
 */
// 编辑历史: 2026-11-03 07:52:00 小欧 - 新建: 顶栏钟面从文本/工具/思考三处图标里拆出后的常驻落位,
//   只读 store(经 useStreamPulse 1s 采样), 无新订阅、无新请求 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 07:58:00 小欧 - 门槛改 bizStale(与胶囊流迟滞同频, 修"抢跑+闪烁"), 并 hideNote — 小欧-2026-11-03
// 编辑历史: 2026-11-03 12:58:00 小欧 - 增 foregroundSessionId 入参: 钟面只数当前会话的等待, 由 AppLayout 透传 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 14:30:00 小欧 - 入参改名 subject(PulseSubject): 非会话页为主语 LATEST_RUNNING — 小欧-2026-11-03
import React from 'react';

import { ClockStopwatch } from '@/components/WaitingIcons/clockStopwatch';
import { useStreamPulse } from '@/features/chat/hooks/useStreamPulse';
import type { StreamPhase } from '@/features/chat/hooks/useStreamPulse';
import { chatStreamStore } from '@/features/chat/streams/chatStreamStore';
import type { PulseSubject } from '@/features/chat/streams/chatStreamStore';

/** 允许出顶栏钟面的档位: 业务帧静默(迟滞)、心跳也停(静默)、断线重连中 —— 三者都是"在等, 且没产出" */
const WAITING_PHASES: ReadonlySet<StreamPhase> = new Set([
  'stalled',
  'silent',
  'reconnecting',
]);

interface HeaderWaitClockProps {
  /** 顶栏主语: 会话页=页面发布的会话 id; 非会话页=LATEST_RUNNING */
  subject: PulseSubject;
}

const HeaderWaitClock: React.FC<HeaderWaitClockProps> = ({ subject }) => {
  const view = useStreamPulse(subject);
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
