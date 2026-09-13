// 编辑历史: 2026-09-11 小欧 - 第七章 M3b(R6/R6-1): 新增 TitleBlock——任务统计 title 段独立组件,
//   数据源=final 帧(outcome/duration/model/provider/token), 绝不读 DB; 两行排版视觉优先 — 小欧-2026-09-11
// 2026-09-11 小欧 - 修: 去 as 强转(DRY/类型安全), 复用 formatTokenCompact 公用函数; 第一行=状态+时长+模型, 第二行=4组token
// 2026-09-11 小欧 - 三堂会审修复: P1-3删??null(与TokenLayer number|undefined对齐, TS2322归零); P2模型顺序统一provider/model(站点惯例+StaticStatsBlock一致); P2 cancelled归default(非error红语义) — 小欧-2026-09-11
// 2026-09-12 小欧 - P1-6三堂会审修复: 抽renderToken()消4组token包裹渲染重复(DRY); 原IIFE三连Typography.Text改4行直线调用 — 小欧-2026-09-12
// 2026-09-13 小欧 - 用CircleArrow/PillBadge可复用组件替换Tag和▲▼; 间距: pill↔time=12px time↔model=15px — 小欧-2026-09-13
import React from 'react';
import { Typography } from 'antd';
import type { ExecutionStep } from '@/types/execution';
import { Colors, formatTokenCompact } from '@/utils/stepStyles';
import { CircleArrow } from '@/components/CircleArrow';
import { PillBadge } from '@/components/PillBadge';

interface TitleBlockProps {
  finalStep?: ExecutionStep | null;
  expanded: boolean;
  onToggle: () => void;
}

const TitleBlock: React.FC<TitleBlockProps> = ({
  finalStep,
  expanded,
  onToggle,
}) => {
  if (!finalStep) return null;
  const outcome = finalStep.outcome;
  const duration = finalStep.duration;
  const model = finalStep.model;
  const provider = finalStep.provider;
  // 2026-09-12 小欧 P1-6: 抽renderToken()——4组token包裹渲染同构, 抽单一helper消重复 — 小欧-2026-09-12
  const renderToken = (text: string | false | null | undefined) =>
    text ? (
      <Typography.Text
        type="secondary"
        style={{ fontSize: 11, whiteSpace: 'nowrap' }}
      >
        {text}
      </Typography.Text>
    ) : null;
  // 2026-09-11 小欧 三堂会审P1-3: 删 ?? null——TokenLayer 字段类型 number|undefined, 传 null 违 TS2322；此处语义完全等价保留 — 小欧-2026-09-11
  const prompt =
    finalStep.prompt_tokens ?? finalStep.accumulated_usage?.prompt_tokens;
  const completion =
    finalStep.completion_tokens ??
    finalStep.accumulated_usage?.completion_tokens;
  const total =
    finalStep.total_tokens ?? finalStep.accumulated_usage?.total_tokens;
  const taskAcc = finalStep.task_accumulated_tokens;
  const sessAcc = finalStep.session_accumulated_tokens;
  const chainAcc = finalStep.chain_accumulated_tokens;
  // 2026-09-13 小欧: outcome→PillBadge背景色映射
  const pillColor =
    outcome === 'completed'
      ? '#52c41a'
      : outcome === 'failed'
        ? '#ff4d4f'
        : '#bfbfbf';
  return (
    <div
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      onClick={onToggle}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onToggle();
        }
      }}
      style={{
        marginTop: 12,
        padding: '8px 12px 0',
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
        cursor: 'pointer',
      }}
    >
      {/* 上行：任务统计 + PillBadge + pill↔time=12px + 运行时长 + time↔model=15px + model/provider + CircleArrow */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Typography.Text strong style={{ fontSize: 13 }}>
          任务统计
        </Typography.Text>
        <PillBadge text={outcome ?? '-'} color={pillColor} shine />
        <span style={{ display: 'inline-block', width: 12 }} />
        <Typography.Text
          type="secondary"
          style={{ fontSize: 11, whiteSpace: 'nowrap' }}
        >
          运行 {duration != null ? `${Math.round(duration)}s` : '-'}
        </Typography.Text>
        <span style={{ display: 'inline-block', width: 15 }} />
        <Typography.Text
          type="secondary"
          style={{ fontSize: 11, whiteSpace: 'nowrap' }}
        >
          {/* 2026-09-11 小欧 三堂会审P2: 统一 provider/model——与站点惯例(useChatPanels L191 provider (model))及 StaticStatsBlock 一致 — 小欧-2026-09-11 */}
          {provider ?? '-'} / {model ?? '-'}
        </Typography.Text>
        <CircleArrow
          expanded={expanded}
          glow
          style={{ marginLeft: 'auto' }}
        />
      </div>
      {/* 下行：token 4组 */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 8,
          marginTop: 2,
          flexWrap: 'wrap',
        }}
      >
        {prompt != null &&
          renderToken(
            formatTokenCompact('累计', {
              prompt_tokens: prompt,
              completion_tokens: completion,
              total_tokens: total,
            })
          )}
        {renderToken(formatTokenCompact('任务', taskAcc))}
        {renderToken(formatTokenCompact('会话', sessAcc))}
        {renderToken(formatTokenCompact('链', chainAcc))}
      </div>
    </div>
  );
};

export { TitleBlock };
