/** HitlPendingPill - 顶栏 HITL 待处理项角标 — 商量 2026-11-24
 *
 * 解决：用户不在发起确认的那个会话时，完全不知道"有活要干"（原来只有回到该会话、内容流
 *   送 interact 帧才弹窗）。本胶囊把"全站待确认 / 待回答"数量显性化，点击直达对应会话。
 *
 * 分工：本组件**只做提示与导航**，不承载弹窗正文——点进去后由内容流的 interact 帧渲染弹窗
 *   （弹窗详情唯一来源仍是 chatStreamTransport.interactHandlers）。与信封只负责叫醒，
 *   真相去内容流拿"同一原则。
 *
 * 编辑历史: 2026-11-24 商量 - 新建: 顶栏 HITL 待处理项角标组件, 展示计数并点击跳转对应会话
 */
import React from 'react';
import { Badge } from 'antd';

import { useHitlPending } from '../../features/chat/streams/hitlPendingStore';
import type { HitlPendingItem } from '../../features/chat/streams/hitlPendingStore';
import { PillTip, type PillTipRow } from './PillTip';
import { PillShell } from './PillShell';

interface HitlPendingPillProps {
  /** 点击某一项：跳转到该会话（由壳层提供导航，组件本身不碰 Router） */
  onOpen: (item: HitlPendingItem) => void;
  /** 当前页正在显示的会话 id：该会话下的项已在眼前弹出，不重复计入角标 */
  currentSessionId?: string | null;
}

const KIND_TEXT: Record<string, string> = {
  confirm: '待确认',
  question: '待回答',
};

const shortId = (id: string | null): string => (id ? id.slice(0, 8) : '—');

const HitlPendingPill: React.FC<HitlPendingPillProps> = ({
  onOpen,
  currentSessionId,
}) => {
  const all = useHitlPending();
  // 当前会话下的项：内容流已就地把弹窗渲染出来了，角标只统计"不在眼前"的，避免重复暗示
  const items = all.filter(
    (i) => !currentSessionId || i.session_id !== currentSessionId
  );

  if (items.length === 0) return null; // 无待处理项不占位（与 HeaderWaitClock 同思路）

  const rows: PillTipRow[] = items.map((i, idx) => ({
    group: idx === 0 ? `待处理 ${items.length} 项` : undefined,
    label: KIND_TEXT[i.kind] ?? i.kind,
    value:
      i.kind === 'confirm'
        ? `${i.tool_name || '工具'} · ${shortId(i.session_id)}`
        : `${i.count ?? 0} 题 · ${shortId(i.session_id)}`,
  }));

  return (
    <PillShell
      role="button"
      ariaLabel={`有 ${items.length} 项待处理，点击前往`}
      onClick={() => {
        const first = items[0];
        if (first) onOpen(first);
      }}
      tooltip={
        <PillTip
          tone="warn"
          title={`${items.length} 项待处理`}
          subtitle="点击前往对应会话处理"
          rows={rows}
          items={[
            { text: '确认/问询的详细内容在该会话打开后由实时流给出' },
            { text: '任一设备处理即收敛，其余端角标自动消失' },
          ]}
        />
      }
    >
      <Badge status="warning" text={`待处理 ${items.length}`} />
    </PillShell>
  );
};

export { HitlPendingPill };
