/**
 * ContextOverviewCard —— taskinfo「历史上下文」浮层卡片
 * 小欧 2026-10-04（设计见 doc-10月优化/[6]，v1.1 三堂会审定案）
 *
 * 3 行：装入 N 条 · 约 X.XK ／ 最近: 摘要(默认3行，点击展开) ／ truncated 才补一行警示。
 * 从 TaskInfoBar 的 78 行内联 IIFE 抽出，因新增折叠态继续堆叠会混层(SRP/SLAP)。
 */
import React, { useState } from 'react';
import type { ContextOverviewFrame } from '@/types/sse';
import { CONTEXT_STATE_MAP, mapStatus, type ContextState } from './infoMaps';
import { FloatingEntry } from './FloatingEntry';
import { MetricItem } from './MetricItem';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';

/** token 估算值格式化：9200 → “9.2K”。仅本组件用，不建公用工具 */
const fmtApproxTokens = (n: number | null | undefined): string => {
  if (n == null || Number.isNaN(n)) return '–';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
};

interface Props {
  /** 与 mapStatus 的 ContextSource.overview 同形：实时帧为对象，历史任务为空串 */
  overview: string | ContextOverviewFrame | null;
  /** start 帧的 context_summary 兜底（mapStatus 的第二个数据源） */
  contextSummary: string;
  /** false = 历史任务（无实时帧，设计如此）— 小欧 2026-10-04 */
  isLiveContext: boolean;
}

export const ContextOverviewCard: React.FC<Props> = ({
  overview,
  contextSummary,
  isLiveContext,
}) => {
  const [open, setOpen] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const ctxState: ContextState = mapStatus({
    overview,
    contextSummary,
    isLiveContext,
  });
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

  const metrics = [
    count != null ? `装入 ${count} 条` : null,
    hasTokens ? `约 ${fmtApproxTokens(tokens)}` : null,
  ]
    .filter(Boolean)
    .join(' · ');

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
          <div>{metrics || ctx.text}</div>
          {summary && (
            <div>
              {/* 北京老陈 2026-09-09 令: 摘要不截断 —— 落为默认 3 行 + 可展开见全文 */}
              <div
                style={{
                  display: '-webkit-box',
                  WebkitLineClamp: expanded ? undefined : 3,
                  WebkitBoxOrient: 'vertical',
                  overflow: 'auto',
                }}
              >
                最近: {summary}
              </div>
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                style={{
                  background: 'none',
                  border: 'none',
                  padding: 0,
                  cursor: 'pointer',
                  color: Colors.INFO,
                  fontSize: FontSize.SECONDARY,
                }}
              >
                {expanded ? '收起' : '展开全文'}
              </button>
            </div>
          )}
          {/* 2026-10-04 小欧: 仅 truncated 补一行警示——唯一有用户影响且不能自解释的态;
              原先恒显一行(ok 态显示"正常")与卡片重复且是噪声 — 小欧 2026-10-04 */}
          {ctxState === 'truncated' && (
            <div style={{ color: Colors.WARNING }}>{ctx.tooltip}</div>
          )}
        </>
      }
    >
      <MetricItem
        label="历史上下文"
        value={hasTokens ? fmtApproxTokens(tokens) : ctx.text}
        tone={ctx.tone}
        icon={ctx.icon}
        dataState={ctxState}
      />
    </FloatingEntry>
  );
};
