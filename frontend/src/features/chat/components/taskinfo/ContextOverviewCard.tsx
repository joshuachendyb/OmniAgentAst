/**
 * ContextOverviewCard —— taskinfo「上下文」浮层卡片
 * 小欧 2026-10-04（设计见 doc-10月优化/[6]）
 *
 * 历史任务只显行内值、不挂弹框（无实时数据可展示）；实时任务见卡片内容。
 * 编辑历史: 2026-10-04 小欧 - 自 TaskInfoBar 抽出为独立组件(G6 浮层①); 历史任务只显行不挂弹框(isLiveContext=false 早返回);
 *   摘要单行省略(去展开按钮), 仅 truncated 补警示行; token 折算复用 infoMaps.formatTokenK(DRY)
 * 编辑历史: 2026-10-04 小欧 - 新增可选 prop contextWindow: 装入条补「占窗率 = 估算token/窗口」, 窗口缺失则不渲染
 * 编辑历史: 2026-10-04 小欧 - 显出跨任务注入三字段(injected_message_count/injected_estimated_tokens/injected_ratio,
 *   此前帧收了未渲染): 增第二行, 仅注入条数>0 时显示(多数任务为 0, 显示是噪声)
 * 编辑历史: 2026-10-07 小欧 - injected_ratio 由百分比改为倍数(后端语义改为压缩比=注入量/装入量,
 *   原百分比在压缩场景会显示成 5650%); token 同时给完整值与 K 缩写(格式由 formatTokenK 收于 K)
 * 编辑历史: 2026-10-07 小欧 - 删 contextSummary prop 与其兜底: 上下文数据只认 history_context 帧(overview);
 *   原在 overview 非对象时回退 start.content, 会让未压缩/未注入任务显示错误上下文
 * 编辑历史: 2026-10-08 小欧 北京老陈裁定"不能误导用户" 四处纠正: ①`压缩比 R×`→`已压缩 X%`且仅
 *   compressed=true 时显(后端 injected_ratio 下线: 该值>1 才代表压缩生效, 标签方向相反且未压缩时≠1.0);
 *   ②`装入历史对话 N 条`→`上下文 N 条`+tooltip 说明口径(message_count 是 conv 全量, 含本轮提问与工具调用);
 *   ③`最近: X`→`最近提问: X`(后端 summary 改取注入源最后一条 user, 不再回显本轮提问); ④占窗率加(估算)标注。
 * 编辑历史: 2026-10-08 小欧 北京老陈裁定 B 全展开不折叠: ⑤summary 段去单行省略, 改 pre-wrap 保留六段换行,
 *   限高 52vh 可滚(内容一字不删); ⑥标题随场景显式化(已注入摘要/最近提问); ⑦卡片宽 320→560(2048 字符在窄栏不可读)。
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
  /** history_context 帧数据(实时唯一来源); 历史任务为空串 — 小欧 2026-10-04 */
  overview: string | ContextOverviewFrame | null;
  /** false = 历史任务：只显行内值，不挂弹框 — 小欧 2026-10-04 */
  isLiveContext: boolean;
  /** 当前任务模型上下文窗口(usage 帧带来)；缺失则不显占窗率 — 小欧 2026-10-04 */
  contextWindow?: number | null;
}

export const ContextOverviewCard: React.FC<Props> = ({
  overview,
  isLiveContext,
  contextWindow,
}) => {
  const [open, setOpen] = useState(false);
  // 2026-10-04 小欧: 切到历史任务时清弹框态, 否则切回实时任务弹框自动重开
  useEffect(() => {
    if (!isLiveContext) setOpen(false);
  }, [isLiveContext]);

  const ctxState: ContextState = mapStatus({ overview });
  const ctx = CONTEXT_STATE_MAP[ctxState];
  const tokens =
    typeof overview === 'object' && overview ? overview.estimated_tokens : null;
  const summary =
    typeof overview === 'object' && overview ? (overview.summary ?? '') : '';
  const hasTokens = ctxState === 'ok' || ctxState === 'truncated';
  const count =
    typeof overview === 'object' && overview ? overview.message_count : null;

  // 2026-10-04 小欧: 跨任务注入字段仅 injected_message_count>0 时显(多数任务为 0, 显示是噪声 YAGNI)。
  //   2026-10-08 删 ratio 字段: 后端 injected_ratio 已下线, 压缩率改由 overview.compressed 直渲。
  const injected =
    typeof overview === 'object' && overview
      ? {
          count: overview.injected_message_count ?? 0,
          tokens: overview.injected_estimated_tokens ?? 0,
        }
      : null;
  // 2026-10-08 小欧 压缩率: 派生时收窄 union 类型, 不在 JSX 内直接访问(TS18047/TS2339);
  //   仅压缩时产出, 未压缩返 null → 整段不显, 不用"1.0×"冒充"压缩了"
  const compressInfo =
    typeof overview === 'object' && overview && overview.compressed === true
      ? { savedPct: overview.compress_saved_pct ?? 0 }
      : null;

  // 2026-10-04 小欧: 装入条数 + 估算 token + 占窗率 同行(北京老陈定); 占窗率=估算 token / 窗口, 窗口缺失则不显
  const usedPct =
    tokens != null && contextWindow
      ? Math.round((tokens / contextWindow) * 100)
      : null;
  const metricLine =
    count != null || hasTokens ? (
      <div>
        {injected && injected.count > 0 && (
          <div>
            跨任务注入 {injected.count} 条 · 估算Token约{' '}
            {injected.tokens.toLocaleString()} ({formatTokenK(injected.tokens)})
            {/* 2026-10-08 小欧 北京老陈裁定"不能误导用户": 原显 `压缩比 R×`, 而该值>1 才代表压缩生效 →
                标签与数值方向相反, 且未压缩时也不等于 1.0。改显"已压缩 X%"且仅压缩时才显。 */}
            {compressInfo && (
              <>
                {' · 已压缩 '}
                {compressInfo.savedPct.toFixed(1)}%
              </>
            )}
          </div>
        )}
        <div>
          {/* 2026-10-08 小欧 标签订正: 原 `装入历史对话 N 条`, 但 message_count 是 conversation_history
              全量(含本轮 system/提问/工具调用), 注入105装入117 时用户会以为多出 12 条不知来路。 */}
          {count != null && (
            <span title="上下文全部消息条数（含本轮提问与工具调用），非仅历史对话">
              上下文 {count} 条
            </span>
          )}
          {count != null && hasTokens && <span> · </span>}
          {hasTokens && <span>估算Token约 {formatTokenK(tokens)}</span>}
          {/* 占窗率: 分子是 MessageBuilder 粗估 token, 与 TaskInfoBar 的 prompt token 不同口径,
              故标注(估算)并在 title 里说明, 避免用户误当精确值。 */}
          {hasTokens && usedPct != null && (
            <span
              title={`按估算 token ${tokens} ÷ 窗口 ${contextWindow} 计算，非 LLM 实测 prompt`}
            >
              {' · 占窗率(估算) '}
              {usedPct}%
            </span>
          )}
        </div>
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
        // 2026-10-08 小欧 320→560: 摘要全文可达 2048 字符(六段 Markdown), 320px 窄栏会挤成细长条。
        //   纵向不设上限(北京老陈令: 全展开不折叠), 只放宽宽让每行可读。
        width: 560,
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
            // 2026-10-08 小欧 北京老陈裁定 B(全展开不折叠): ①内容改真来源 —— 后端 compressed 时给「真正注入 conv
            //   的那段摘要」, 未压缩给最近一次历史提问(原字段恒为用户本轮提问, 等于回显自己, 属误导);
            //   ②去单行省略与 textOverflow, 改 pre-wrap 保留六段换行; ③标题随场景显式化, 不让用户猜。
            <div
              style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                color: Colors.TEXT.PRIMARY,
                // 2026-10-08 小欧: 全展开但可滚(北京老陈"不能折叠"≠"不可达")。摘要实测 2048 字符
                //   ≈ 800~1200px 高, 不限高会溢出视口底部看不到; maxHeight+overflowY 令全文在框内滚动。
                maxHeight: '52vh',
                overflowY: 'auto',
              }}
            >
              <div
                style={{
                  fontWeight: FontWeight.BOLD,
                  position: 'sticky',
                  top: 0,
                }}
              >
                {compressInfo ? '已注入摘要' : '最近提问'}
              </div>
              <div>{summary}</div>
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
