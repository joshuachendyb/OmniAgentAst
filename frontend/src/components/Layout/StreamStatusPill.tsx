/** StreamStatusPill - 顶栏 SSE 流状态灯(与 Service/Config 胶囊正交)。 @author 小欧 @date 2026-11-02 */
// 编辑历史: 2026-11-02 小欧 - 新建: 只读 store 聚合快照(共享 1s 采样), 不发任何请求 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - badge 由 tone 单点映射, 浮层数据行抽到 streamPillRows 与胶囊共用 — 小欧-2026-11-02
// 编辑历史: 2026-11-03 小欧 - 收口: 浮层卡片/容器栅格/hover 交 PillShell, 删本文件 HOVER_BG — 小欧-2026-11-03
// 编辑历史: 2026-11-03 小欧 - 字号归 PillShell 统一定(12), 标签只留语义色 — 小欧-2026-11-03
import React from 'react';
import { Badge } from 'antd';

import { useStreamPulse } from '../../features/chat/hooks/useStreamPulse';
import type { StreamTone } from '../../features/chat/hooks/useStreamPulse';
import { IDLE_TIMEOUT } from '../../features/chat/streams/chatStreamTransport';
import { Colors } from '../../utils/stepStyles';
import { TONE_COLOR } from '../../utils/tone';
import { PillTip, type PillTipRow } from './PillTip';
import { PillShell } from './PillShell';
import { streamDataRows } from './streamPillRows';

const BADGE_OF: Record<
  StreamTone,
  'success' | 'processing' | 'warning' | 'error' | 'default'
> = {
  ok: 'processing',
  warn: 'warning',
  alert: 'default',
  error: 'error',
  neutral: 'default',
};

/** 流状态原值 → 人话, 未知值原样回显(不吞不猜) — 2026-11-02 小欧 */
const STATUS_TEXT: Record<string, string> = {
  idle: '空闲',
  active: '执行中',
  paused: '待确认',
  retrying: '重试中',
  recovering: '恢复中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
};

const shortId = (id: string | null): string => (id ? id.slice(0, 8) : '—');

const StreamStatusPill: React.FC = () => {
  const view = useStreamPulse();
  const p = view.pulse;

  const rows: PillTipRow[] = p.active
    ? [
        {
          label: '会话',
          value: shortId(p.sessionId),
          mono: true,
          group: '本轮流',
        },
        { label: '状态', value: STATUS_TEXT[p.status] ?? p.status },
        { label: '任务', value: shortId(p.serverTaskId), mono: true },
        ...streamDataRows(view, '数据'),
        { label: '判死', value: `${IDLE_TIMEOUT / 1000}s 无字节` },
        ...(p.activeSessions > 1
          ? [{ label: '并发', value: `${p.activeSessions} 条流` }]
          : []),
      ]
    : [{ label: '流', value: '无进行中的任务' }];

  // 2026-11-02 小欧 - 文字与状态点同色; antd Badge 没有橘红 status, alert 档走自定义 color 点 — 小欧-2026-11-02
  // 2026-11-03 小欧 - 字号由 PillShell 统一定(12); 此处只留语义色, 字号行高成对同源 — 小欧-2026-11-03
  const label = (
    <span style={{ color: TONE_COLOR[view.tone] }}>{view.text}</span>
  );

  return (
    <PillShell
      role="img"
      ariaLabel="SSE 流状态"
      className={view.tone === 'ok' ? 'stream-pill-ok' : undefined}
      tooltip={
        <PillTip
          tone={view.tone}
          title={view.text}
          subtitle={view.main}
          rows={rows}
          items={
            p.active
              ? [
                  {
                    text: '心跳只证明连接没断（后端静默 25s 才发一次）；有无产出看业务帧，二者分开判',
                  },
                  {
                    text: `${IDLE_TIMEOUT / 1000}s 内无任何字节才判死并断点续传`,
                  },
                ]
              : undefined
          }
        />
      }
    >
      {view.tone === 'alert' ? (
        <Badge color={Colors.ORANGE_RED} text={label} />
      ) : (
        <Badge status={BADGE_OF[view.tone]} text={label} />
      )}
    </PillShell>
  );
};

export { StreamStatusPill };
