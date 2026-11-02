/**
 * StreamStatusPill - 顶栏 SSE 流状态小灯：只答"当前这条流活没活、心跳新不新"，
 * 与 ServiceStatusPill(进程能不能应答)、ConfigStatusPill(配置是否允许发消息)三者正交。
 *
 * @author 小欧
 * @date 2026-11-02
 */
// 编辑历史: 2026-11-02 小欧 - 新建: 只读 store 聚合快照(1s 采样), 不发任何请求; 浮层显会话/状态/任务/心跳/静默/判死阈值 — 小欧-2026-11-02
import React from 'react';
import { Badge, Tooltip } from 'antd';

import { useStreamPulse } from '../../features/chat/hooks/useStreamPulse';
import type { StreamTone } from '../../features/chat/hooks/useStreamPulse';
import { IDLE_TIMEOUT } from '../../features/chat/streams/chatStreamTransport';
import {
  Colors,
  FontSize,
  Radius,
  Spacing,
  BorderWidth,
} from '../../utils/stepStyles';
import { PillTip, PILL_TIP_ROOT_MAX_W, type PillTipRow } from './PillTip';

// 2026-11-02 小欧 - 顶栏白底悬停浅灰, 与配置/服务胶囊同令牌 — 小欧-2026-11-02
const HOVER_BG = Colors.BG.HOVER;

const TONE_COLOR: Record<StreamTone, string> = {
  ok: Colors.SUCCESS,
  warn: Colors.WARNING,
  alert: Colors.ORANGE_RED,
  error: Colors.ERROR,
  neutral: Colors.TEXT.SECONDARY,
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
const ageText = (sec: number | null): string =>
  sec === null ? '未收到' : `${sec} 秒前`;

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
        {
          label: '业务帧',
          value: ageText(view.bizAgeSec),
          tone: view.bizStale ? 'warn' : undefined,
          group: '数据',
        },
        { label: '心跳', value: ageText(view.heartbeatAgeSec) },
        { label: '最后字节', value: ageText(view.dataAgeSec) },
        { label: '判死', value: `${IDLE_TIMEOUT / 1000}s 无字节` },
        ...(p.activeSessions > 1
          ? [{ label: '并发', value: `${p.activeSessions} 条流` }]
          : []),
      ]
    : [{ label: '流', value: '无进行中的任务' }];

  // 2026-11-02 小欧 - 文字与状态点同色; antd Badge 没有橘红 status, alert 档走自定义 color 点 — 小欧-2026-11-02
  const label = (
    <span
      style={{
        fontSize: FontSize.SECONDARY,
        color: TONE_COLOR[view.tone],
      }}
    >
      {view.text}
    </span>
  );

  return (
    <Tooltip
      color={Colors.BG.PRIMARY}
      styles={{
        root: { maxWidth: PILL_TIP_ROOT_MAX_W },
        body: {
          padding: `${Spacing.MD}px ${Spacing.LG}px`,
          border: `${BorderWidth.THIN}px solid ${Colors.BORDER.VERTICAL}`,
          borderRadius: Radius.LG,
        },
      }}
      title={
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
                    tone: 'warn' as const,
                  },
                  {
                    text: `${IDLE_TIMEOUT / 1000}s 内无任何字节才判死并断点续传`,
                    tone: 'warn' as const,
                  },
                ]
              : undefined
          }
        />
      }
    >
      <span
        role="button"
        aria-label="SSE 流状态"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: `${Spacing.XS}px ${Spacing.MD}px`,
          borderRadius: Radius.SM,
          cursor: 'help',
          transition: 'background 0.2s',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = HOVER_BG;
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = 'transparent';
        }}
      >
        {view.tone === 'alert' ? (
          <Badge color={Colors.ORANGE_RED} text={label} />
        ) : (
          <Badge status={view.badge} text={label} />
        )}
      </span>
    </Tooltip>
  );
};

export { StreamStatusPill };
