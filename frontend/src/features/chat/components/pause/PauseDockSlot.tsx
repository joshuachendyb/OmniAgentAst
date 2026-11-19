// 2026-11-19 小欧 - 人工暂停小浮层: 明确"用户点了暂停按钮"并计时, 停靠 taskinfo 徽条上方
// 设计: 与 question/授权浮层同族(停下来等人), 但只是一条紧凑小条(非 520 大卡), 不阻断操作;
//   显示条件 = agent 真挂起(status=paused) 且 无 HITL/question 弹窗(hasPendingInteraction=false) → 必是手动暂停。
//   倒计时读 paused 帧的 backend_timeout(后端 config 单一真源), 与 question/授权浮层同范式。
import React, { useEffect, useMemo, useRef, useState } from 'react';

import { PauseCircleOutlined } from '@ant-design/icons';
import { Button } from 'antd';

import { CountdownRing } from '@/components/CountdownRing';
import { useChatStreamSession } from '@/features/chat/streams/useChatStreamSession';
import { hasPendingInteraction } from '@/features/chat/streams/chatStreamStore';
import { taskControlApi } from '@/services/api/task.api';
import { Gap, LineHeight } from '@/theme/spacing';
import { Colors, FontSize, Radius, Spacing } from '@/utils/stepStyles';
import { formatTimeHMS } from '@/utils/time';

interface PauseDockSlotProps {
  sessionId: string | null;
  serverTaskId?: string | null;
}

const DEFAULT_PAUSE_TIMEOUT = 300; // 兜底(后端 paused 帧会带真实值覆盖)

export function PauseDockSlot({ sessionId, serverTaskId }: PauseDockSlotProps) {
  const snapshot = useChatStreamSession(sessionId);
  // 手动暂停判据: agent 真挂起 + 无授权/问询弹窗(那两者 status 也是 paused, 需排除)
  const manualPaused =
    snapshot.status === 'paused' && !hasPendingInteraction(snapshot);

  // 从 executionSteps 找最近的 paused 步, 取后端下发的 timeout 和暂停时刻
  const pausedStep = useMemo(
    () =>
      [...snapshot.executionSteps].reverse().find((s) => s.type === 'paused'),
    [snapshot.executionSteps]
  );
  const timeoutSec = pausedStep?.backend_timeout || DEFAULT_PAUSE_TIMEOUT;
  const pausedAt = pausedStep?.timestamp;

  // 倒计时: 基于暂停时刻 + timeout 算剩余秒数, 每秒刷新
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!manualPaused) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [manualPaused]);

  const elapsedSec = pausedAt
    ? Math.max(0, Math.floor((now - pausedAt) / 1000))
    : 0;
  const remainSec = Math.max(0, Math.floor(timeoutSec - elapsedSec));

  // 无 taskId 不显示浮层(也就无从操作), 同时满足 taskControlApi 的 string 参数契约
  if (!manualPaused || !serverTaskId) return null;

  const onResume = () => {
    void taskControlApi.resume(serverTaskId, sessionId ?? undefined);
  };
  const onCancel = () => {
    void taskControlApi.cancel(serverTaskId, sessionId ?? undefined);
  };

  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Gap.SECTION,
        padding: `${Spacing.SM}px ${Spacing.MD}px`,
        borderRadius: Radius.DEFAULT,
        border: `1px solid ${Colors.WAIT_ACTION}`,
        background: Colors.BG.PRIMARY,
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
        fontSize: FontSize.SECONDARY,
        lineHeight: LineHeight.DENSE,
        maxWidth: '100%',
      }}
      role="status"
      aria-label="任务已手动暂停"
    >
      <CountdownRing
        countdown={remainSec}
        confirmTimeout={timeoutSec}
        size={40}
      />
      <div
        style={{ display: 'flex', flexDirection: 'column', gap: Gap.INLINE }}
      >
        <span style={{ color: Colors.TEXT.STRONG, fontWeight: 600 }}>
          <PauseCircleOutlined
            style={{ color: Colors.WAIT_ACTION, marginRight: Spacing.XS }}
          />
          任务已暂停（手动）
        </span>
        <span style={{ color: Colors.TEXT.SECONDARY }}>
          {pausedAt
            ? `你在 ${formatTimeHMS(pausedAt)} 暂停，当前步骤完成后挂起。`
            : '当前步骤完成后挂起。'}
          {remainSec > 0
            ? `剩余约 ${Math.ceil(remainSec / 60)} 分钟后自动继续。`
            : '即将自动继续。'}
        </span>
      </div>
      <Button type="primary" size="small" onClick={onResume}>
        立即继续
      </Button>
      <Button type="text" size="small" danger onClick={onCancel}>
        取消任务
      </Button>
    </div>
  );
}
