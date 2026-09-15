// 编辑历史: 2026-09-11 小欧 - 第七章 M3b(title段独立组件): 新增 TitleBlock——任务统计 title 段独立组件,
//   数据源=final 帧(outcome/duration/model/provider/token), 绝不读 DB; 两行排版视觉优先 — 小欧-2026-09-11
// 2026-09-11 小欧 - 修: 去 as 强转(DRY/类型安全), 复用 formatTokenCompact 公用函数; 第一行=状态+时长+模型, 第二行=4组token
// 2026-09-11 小欧 - 三堂会审修复: P1-3删??null(与TokenLayer number|undefined对齐, TS2322归零); P2模型顺序统一provider/model(站点惯例+StaticStatsBlock一致); P2 cancelled归default(非error红语义) — 小欧-2026-09-11
// 2026-09-12 小欧 - P1-6三堂会审修复: 抽renderToken()消4组token包裹渲染重复(DRY); 原IIFE三连Typography.Text改4行直线调用 — 小欧-2026-09-12
// 2026-09-13 小欧 - 用CircleArrow/PillBadge可复用组件替换Tag和▲▼; 间距: pill↔time=12px time↔model=15px — 小欧-2026-09-13
// 2026-09-15 小欧 - [40]第一阶段: S1标题13→14(FontSize.PRIMARY); S2间距12/15→Spacing(LG/XL,15无档取XL16收敛);
//   S3字号11→常量; S4 pill三态色令牌化; ④时长/模型灰字改TEXT.PRIMARY+12px;
//   ⑤⑥非completed且provider/model不缺失才渲染模型段(completed隐藏模型,字段缺失不显示); H2累计组强调; A3容器title悬停提示 — 小欧-2026-09-15
import React from 'react';
import { Typography } from 'antd';
import type { ExecutionStep } from '@/types/execution';
import { Colors, FontSize, Spacing, formatTokenCompact } from '@/utils/stepStyles';
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
  // 2026-09-15 小欧 [40]①S3/H2: 字号11→FontSize.SMALL; 新增 strong——累计组整行强调(PRIMARY色+500字重) — 小欧-2026-09-15
  const renderToken = (
    text: string | false | null | undefined,
    strong = false,
  ) =>
    text ? (
      <Typography.Text
        type={strong ? undefined : 'secondary'}
        style={{
          fontSize: FontSize.SMALL,
          whiteSpace: 'nowrap',
          color: strong ? Colors.TEXT.PRIMARY : undefined,
          fontWeight: strong ? 500 : undefined,
        }}
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
  // 2026-09-15 小欧 [40]①S4: pill三态色令牌化(SUCCESS/ERROR/BORDER.STRONG)去硬编码 — 小欧-2026-09-15
  const pillColor =
    outcome === 'completed'
      ? Colors.SUCCESS
      : outcome === 'failed'
        ? Colors.ERROR
        : Colors.BORDER.STRONG;
  return (
    <div
      role="button"
      tabIndex={0}
      aria-expanded={expanded}
      title={expanded ? '点击收起统计详情' : '点击展开统计详情'}
      onClick={onToggle}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onToggle();
        }
      }}
      style={{
        marginTop: Spacing.LG,
        padding: `${Spacing.MD}px ${Spacing.LG}px 0`,
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
        cursor: 'pointer',
      }}
    >
      {/* 上行：任务统计 + PillBadge + 运行时长 + [非completed时 model/provider] + CircleArrow
          2026-09-15 小欧 [40]①: S2间距→Spacing(12=LG,15无档收敛XL16); S3标题13→14(FontSize.PRIMARY);
          ④时长/模型灰字改TEXT.PRIMARY+FontSize.SECONDARY; ⑤非completed才渲染模型段; ⑥provider/model均缺不渲染 — 小欧-2026-09-15 */}
      <div style={{ display: 'flex', alignItems: 'center', gap: Spacing.MD }}>
        <Typography.Text strong style={{ fontSize: FontSize.PRIMARY }}>
          任务统计
        </Typography.Text>
        <PillBadge text={outcome ?? '-'} color={pillColor} shine />
        <span style={{ display: 'inline-block', width: Spacing.LG }} />
        <Typography.Text
          style={{
            fontSize: FontSize.SECONDARY,
            whiteSpace: 'nowrap',
          }}
        >
          运行耗时 {duration != null ? `${Math.round(duration)}s` : '-'}
        </Typography.Text>
        {outcome !== 'completed' && (provider || model) && (
          <>
            <span style={{ display: 'inline-block', width: Spacing.XL }} />
            <Typography.Text
              style={{
                fontSize: FontSize.SECONDARY,
                whiteSpace: 'nowrap',
              }}
            >
              {/* 2026-09-11 小欧 三堂会审P2: 统一 provider/model——与站点惯例(useChatPanels L191 provider (model))及 StaticStatsBlock 一致 — 小欧-2026-09-11 */}
              {provider ?? '-'} / {model ?? '-'}
            </Typography.Text>
          </>
        )}
        <CircleArrow
          size={24}
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
          gap: Spacing.MD,
          marginTop: Spacing.XS / 2,
          flexWrap: 'wrap',
        }}
      >
        {prompt != null &&
          renderToken(
            formatTokenCompact('累计', {
              prompt_tokens: prompt,
              completion_tokens: completion,
              total_tokens: total,
            }),
            true
          )}
        {renderToken(formatTokenCompact('任务', taskAcc))}
        {renderToken(formatTokenCompact('会话', sessAcc))}
        {renderToken(formatTokenCompact('链', chainAcc))}
      </div>
    </div>
  );
};

export { TitleBlock };
