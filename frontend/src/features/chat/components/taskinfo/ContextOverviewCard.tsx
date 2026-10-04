/**
 * ContextOverviewCard —— taskinfo「上下文」浮层卡片
 * 小欧 2026-10-04（设计见 doc-10月优化/[6]）
 *
 * 历史任务只显行内值、不挂弹框（无实时数据可展示）；实时任务见卡片内容。
 * 编辑历史: 2026-10-04 小欧 - 自 TaskInfoBar 抽出为独立组件(G6 浮层①); 历史任务只显行不挂弹框(isLiveContext=false 早返回);
 *   摘要单行省略(去展开按钮), 仅 truncated 补警示行; token 折算复用 infoMaps.formatTokenK(DRY)
 * 编辑历史: 2026-10-04 小欧 - 新增可选 prop contextWindow: 装入条补「占窗率 = 估算token/窗口」, 窗口缺失则不渲染
 */
import React, { useEffect, useState } from 'react';
import type { ContextOverviewFrame } from '@/types/sse';
import {
  CONTEXT_STATE_MAP,
  mapStatus,
  formatTokenK,
  type ContextState,
} from './infoMaps';
import { FloatingEntry } from './FloatingEntry';
import { MetricItem } from './MetricItem';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';

interface Props {
  /** 与 mapStatus 的 ContextSource.overview 同形：实时帧为对象，历史任务为空串 — 小欧 2026-10-04 */
  overview: string | ContextOverviewFrame | null;
  /** start 帧的 context_summary 兜底（mapStatus 的第二个数据源） — 小欧 2026-10-04 */
  contextSummary: string;
  /** false = 历史任务：只显行内值，不挂弹框 — 小欧 2026-10-04 */
  isLiveContext: boolean;
  /** 当前任务模型上下文窗口(usage 帧带来)；缺失则不显占窗率 — 小欧 2026-10-04 */
  contextWindow?: number | null;
}

export const ContextOverviewCard: React.FC<Props> = ({
  overview,
  contextSummary,
  isLiveContext,
  contextWindow,
}) => {
  const [open, setOpen] = useState(false);
  // 2026-10-04 小欧: 切到历史任务时清弹框态, 否则切回实时任务弹框自动重开
  useEffect(() => {
    if (!isLiveContext) setOpen(false);
  }, [isLiveContext]);

  const ctxState: ContextState = mapStatus({ overview, contextSummary });
  const ctx = CONTEXT_STATE_MAP[ctxState];
  const tokens =
    typeof overview === 'object' && overview ? overview.estimated_tokens : null;
  const summary =
    typeof overview === 'object' && overview
      ? (overview.summary ?? '')
      : (contextSummary ?? '');
  const hasTokens = ctxState === 'ok' || ctxState === 'truncated';
  const count =
    typeof overview === 'object' && overview ? overview.message_count : null;

  // 2026-10-04 小欧: 装入条数 + 估算 token + 占窗率 同行(北京老陈定); 占窗率=估算 token / 窗口, 窗口缺失则不显
  const usedPct =
    tokens != null && contextWindow
      ? Math.round((tokens / contextWindow) * 100)
      : null;
  const metricLine =
    count != null || hasTokens ? (
      <div>
        {count != null && <span>装入历史对话 {count} 条</span>}
        {count != null && hasTokens && <span> · </span>}
        {hasTokens && <span>估算Token约 {formatTokenK(tokens)}</span>}
        {hasTokens && usedPct != null && <span> · 占窗率 {usedPct}%</span>}
      </div>
    ) : null;

  // 2026-10-04 小欧: 行内 MetricItem 抽出(历史任务只显行不挂弹框, 北京老陈定)
  const metric = (
    <MetricItem
      // 2026-10-04 小欧: 标签"上下文"(短, 与卡片标题区分)
      label="上下文"
      value={hasTokens ? formatTokenK(tokens) : ctx.text}
      tone={ctx.tone}
      icon={ctx.icon}
      dataState={ctxState}
    />
  );
  // 2026-10-04 小欧: 历史任务无实时数据可展示, 只显行、不挂弹框(北京老陈定)
  if (!isLiveContext) return metric;

  return (
    <FloatingEntry
      open={open}
      onOpenChange={setOpen}
      placement="bottomLeft"
      cardId="taskinfo-context-card"
      ariaLabel="历史上下文"
      cardStyle={{
        width: 320,
        maxWidth: '90vw',
        display: 'flex',
        flexDirection: 'column',
        gap: Spacing.SM,
        fontSize: FontSize.SECONDARY,
        color: Colors.TEXT.SECONDARY,
      }}
      content={
        <>
          <div
            style={{ fontWeight: FontWeight.BOLD, color: Colors.TEXT.PRIMARY }}
          >
            历史上下文
          </div>
          <div>{metricLine ?? ctx.text}</div>
          {summary && (
            // 2026-10-04 小欧: 摘要单行省略, 去展开按钮(北京老陈: 按钮不好看)
            <div
              style={{
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              title={summary}
            >
              最近: {summary}
            </div>
          )}
          {/* 2026-10-04 小欧: 仅 truncated 补警示行, ok 态不重复卡片内容 */}
          {ctxState === 'truncated' && (
            <div style={{ color: Colors.WARNING }}>{ctx.tooltip}</div>
          )}
        </>
      }
    >
      {metric}
    </FloatingEntry>
  );
};
