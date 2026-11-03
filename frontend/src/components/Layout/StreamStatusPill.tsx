/** StreamStatusPill - 顶栏 SSE 流状态灯(与 Service/Config 胶囊正交)。 @author 小欧 @date 2026-11-02 */
// 编辑历史: 2026-11-02 小欧 - 新建: 只读 store 聚合快照(共享 1s 采样), 不发任何请求 — 小欧-2026-11-02
// 编辑历史: 2026-11-02 小欧 - badge 由 tone 单点映射, 浮层数据行抽到 streamPillRows 与胶囊共用 — 小欧-2026-11-02
// 编辑历史: 2026-11-03 小欧 - 收口: 浮层卡片/容器栅格/hover 交 PillShell, 删本文件 HOVER_BG — 小欧-2026-11-03
// 编辑历史: 2026-11-03 小欧 - 字号归 PillShell 统一定(12), 标签只留语义色 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 06:52:40 小欧 - 空态浮层不再复读标题(流/无进行中的任务), 改一行提示 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 12:58:00 小欧 - 增 foregroundSessionId 入参: 胶囊只报当前会话, 并发流只作浮层计数 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 14:30:00 小欧 - 入参改名 subject(PulseSubject): 非会话页为主语 LATEST_RUNNING — 小欧-2026-11-03
// 编辑历史: 2026-11-03 16:40 小欧 - 「其他在跑」改读 runningTasksStore.useMergedRunningTasks(唯一合并口),
//   删 STATUS_TEXT.executing(DB 词表已由 toStreamStatus 归一到 active), 本轮流那条按主语过滤 — 小欧-2026-11-03
import React from 'react';
import { Badge } from 'antd';

import { useStreamPulse } from '../../features/chat/hooks/useStreamPulse';
import type { StreamTone } from '../../features/chat/hooks/useStreamPulse';
import { IDLE_TIMEOUT } from '../../features/chat/streams/chatStreamTransport';
import type { PulseSubject } from '../../features/chat/streams/chatStreamStore';
import type { StreamStatus } from '../../features/chat/streams/backupTypes';
import { useMergedRunningTasks } from '../../features/chat/streams/runningTasksStore';
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

/** 流状态 → 人话, 8 档全覆盖 — 2026-11-02 小欧
 *  2026-11-03 小欧 - 键收窄为 StreamStatus(穷尽): 新增状态值必须同步本表, 漏键即编译错误, 调用方无需 `?? 原文` 兜底。 */
const STATUS_TEXT: Record<StreamStatus, string> = {
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

/** 2026-11-03 小欧 - 任务号去 `task-` 前缀再截 8 位: 带前缀时 8 位只剩 3 位十六进制,
 *  并发的两条任务在浮层里根本区分不出来 — 小欧-2026-11-03 */
const shortTaskId = (id: string | null): string =>
  id ? id.replace(/^task-/, '').slice(0, 8) : '—';

interface StreamStatusPillProps {
  /** 顶栏主语: 会话页=页面发布的会话 id; 非会话页=LATEST_RUNNING */
  subject: PulseSubject;
}

const StreamStatusPill: React.FC<StreamStatusPillProps> = ({ subject }) => {
  const view = useStreamPulse(subject);
  const p = view.pulse;
  const merged = useMergedRunningTasks();

  // 2026-11-03 小欧 - 并发披露: 顶栏同时刻只演一条, 其余在跑任务必须在浮层逐条列出(否则 3 条并发像 1 条);
  //   数据只读唯一合并口, 本轮流那条按主语 serverTaskId 排除。
  const otherTasks = merged.filter((t) => t.taskId !== p.serverTaskId);

  const otherRows: PillTipRow[] = otherTasks.map((o, idx) => ({
    group: idx === 0 ? `其他在跑 ${otherTasks.length} 条` : undefined,
    label: shortId(o.sessionId),
    value: `${shortTaskId(o.taskId)} · ${STATUS_TEXT[o.status]}`,
  }));

  const rows: PillTipRow[] = p.active
    ? [
        {
          label: '会话',
          value: shortId(p.sessionId),
          mono: true,
          group: '本轮流',
        },
        { label: '状态', value: STATUS_TEXT[p.status] },
        { label: '任务', value: shortTaskId(p.serverTaskId), mono: true },
        ...streamDataRows(view, '数据'),
        { label: '判死', value: `${IDLE_TIMEOUT / 1000}s 无字节` },
        ...otherRows,
      ]
    : [{ label: '提示', value: '发送任务后这里显示实时状态' }, ...otherRows];

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
