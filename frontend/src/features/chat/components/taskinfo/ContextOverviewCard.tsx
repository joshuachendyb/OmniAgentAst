/**
 * ContextOverviewCard —— taskinfo「上下文」浮层卡片
 * 小欧 2026-10-04（设计见上下文卡片设计文档）
 *
 * 历史任务挂弹框只显历史上下文段（DB 首帧回放，无对话上下文段）；实时任务见卡片全部内容。
 * 编辑历史: 2026-10-04 小欧 - 自 TaskInfoBar 抽出为独立组件(G6 浮层①); 摘要单行省略(去展开按钮),
 * 仅 truncated 补警示行; token 折算复用 infoMaps.formatTokenK(DRY)
 * 编辑历史: 2026-10-04 小欧 - 新增可选 prop contextWindow: 装入条补「占窗率 = 估算token/窗口」, 窗口缺失则不渲染
 * 编辑历史: 2026-10-04 小欧 - 显出跨任务注入两字段(injected_message_count/injected_estimated_tokens,
 * 此前帧收了未渲染): 增第二行, 仅注入条数>0 时显示(多数任务为 0, 显示是噪声)
 * 编辑历史: 2026-10-07 小欧 - token 同时给完整值与 K 缩写(格式由 formatTokenK 收于 K);
 * 删 contextSummary prop 与其兜底: 上下文数据只认 history_context 帧(overview)
 * 编辑历史: 2026-10-08 小欧 "不能误导用户" 四处纠正: ①`压缩比 R×`→`已压缩 X%`且仅
 * compressed=true 时显(后端 injected_ratio 下线: 该值>1 才代表压缩生效, 标签方向相反且未压缩时≠1.0);
 * ②`装入历史对话 N 条`→`上下文 N 条`+tooltip 说明口径(message_count 是 conv 全量, 含本轮提问与工具调用);
 * ③`最近: X`→`最近提问: X`(后端 summary 改取注入源最后一条 user, 不再回显本轮提问); ④占窗率加(估算)标注;
 * ⑤summary 段去单行省略改 pre-wrap 保留换行(全文一字不删); ⑥卡片宽 320→560(2048 字符在窄栏不可读)
 * 编辑历史: 2026-10-09 小欧 - 双分组嵌套直显(删 hasTokens/numOrNull 开关); 卡片内拆两段+分割线
 * 编辑历史: 2026-10-10 小欧 (本日汇总, 仅留此一条): ①只读 conv_context/inject_context
 * 定稿结构(禁旧扁平兼容), compressed 原样直显; ②删两段 `?? ctx.text` 兜底与 summary-only 态(见
 * infoMaps), 行内值历史任务改取 inject token; ③排版: 标题行抽 <SectionHead> 共用(DRY), 标签列定宽
 * HEAD_LABEL_WIDTH='9em', 数据行缩进与其同起点, 而分割线/摘要框/截断警示框左侧顶卡片边通栏(框内文字
 * paddingLeft:0), 标题右侧禁折行; ④截断警示框挪进「对话上下文」段内(truncated 属 conv_context)。
 * 排版经四轮反复(框缩进/文字缩进/通栏), 上列③为最终形态, 冲突的中间态注释已清理。
 */
import React, { useState } from 'react';
import type { ContextOverviewFrame } from '@/types/sse';
import {
  CONTEXT_STATE_MAP,
  mapStatus,
  formatTokenK,
  type ContextState,
} from './infoMaps';
import { pickConv, pickInject } from '@/utils/contextFrame';
import { FloatingEntry } from './FloatingEntry';
import { MetricItem } from './MetricItem';
import {
  Colors,
  FontSize,
  FontWeight,
  Radius,
  Spacing,
} from '@/utils/stepStyles';

interface Props {
  /** history_context 帧数据(实时唯一来源); 历史任务为空串 — 小欧 2026-10-04 */
  overview: string | ContextOverviewFrame | null;
  /** false = 历史任务：弹框只显历史上下文段（DB 首帧回放，无对话上下文段） — 小欧 2026-10-09 */
  isLiveContext: boolean;
  /** 当前任务模型上下文窗口(usage 帧带来)；缺失则不显占窗率 — 小欧 2026-10-04 */
  contextWindow?: number | null;
}

/**
 * 段标题行的标签列宽 —— 「对话上下文」/「历史上下文」两段同宽(均为 5 个汉字 + 4 汉字留白)
 *
 * 2026-10-10 标题后固定空 4 个汉字宽再显右侧信息, 且**下方数据行的起始位置
 * 必须与标题行右侧文字的起始位置对齐**。做法: 标签列定宽(本常量), 段内数据行统一
 * paddingLeft 同宽 —— 对齐由"同一常量"保证, 不靠手调数值 (DRY, 改一处两段同时生效)。
 */
const HEAD_LABEL_WIDTH = '9em';

/**
 * 段标题行 —— 两段共用(DRY: 样式只此一处, 不各写一套)
 *
 * 2026-10-10: ①标签列定宽 HEAD_LABEL_WIDTH, 右侧信息起点 = 该宽度, 与下方数据行同起点;
 * ②禁折行禁折叠 —— 右侧 whiteSpace:nowrap 单行直显; ③标签 nowrap + flexShrink:0 永不被挤压。
 */
const SectionHead: React.FC<{
  dotColor: string;
  title: string;
  children?: React.ReactNode;
}> = ({ dotColor, title, children }) => (
  <div style={{ display: 'flex', alignItems: 'baseline' }}>
    <div
      style={{
        width: HEAD_LABEL_WIDTH,
        flexShrink: 0,
        display: 'flex',
        alignItems: 'baseline',
        fontWeight: FontWeight.BOLD,
        color: Colors.TEXT.PRIMARY,
        whiteSpace: 'nowrap',
      }}
    >
      <span
        style={{
          display: 'inline-block',
          width: 6,
          height: 6,
          borderRadius: '50%',
          background: dotColor,
          marginRight: Spacing.XS,
        }}
      />
      {title}
    </div>
    {children}
  </div>
);

export const ContextOverviewCard: React.FC<Props> = ({
  overview,
  isLiveContext,
  contextWindow,
}) => {
  const [open, setOpen] = useState(false);

  const ctxState: ContextState = mapStatus({ overview });
  const ctx = CONTEXT_STATE_MAP[ctxState];
  // 2026-10-09: 读路径只认定稿双分组。typeof 守卫保留(string 无分组键)
  const convCtx = pickConv(overview);
  const injectCtx = pickInject(overview);
  // 2026-10-09 后端给什么显示什么 —— 空位 "" 直显为空, 不转换不设开关
  const convTokens = convCtx?.estimated_tokens ?? '';
  const injectTokens = injectCtx?.injected_estimated_tokens ?? '';
  // 2026-10-10 行内一个数, 代表"当前能看到的那个上下文"
  // (实时=对话 conv, 历史=跨任务注入 inject), 两组都空则 formatTokenK 返回 '–'
  const tokens = isLiveContext ? convTokens : injectTokens;
  const summary = injectCtx?.summary ?? '';
  const count = convCtx?.message_count ?? '';
  // 2026-10-10 小欧: 空段兜底用 content 原文(后端成品状态文案), 比"–"诚实
  const contentText =
    (typeof overview === 'object' && overview ? overview.content : null) ||
    null;

  // 2026-10-04 小欧: 跨任务注入字段仅 injected_message_count>0 时显(多数任务为 0, 显示是噪声 YAGNI)。
  const injected = injectCtx
    ? {
        count: injectCtx.injected_message_count ?? '',
        tokens: injectCtx.injected_estimated_tokens ?? '',
      }
    : null;
  // 2026-10-09: compressed 是后端成品情况文字, 原样直显不截不断
  const compressedText = injectCtx?.compressed ?? '';
  // 2026-10-10 「历史上下文」段标题行右侧 = content + compressed,
  // 实时任务与历史任务**同此一条**, 其他区块一律不动。
  // content 内含后端拼好的「第N个link任务, 」前缀(前缀已归 content), 两字段相邻直显, 原样不加工
  // 2026-10-10 布局优化: 两字段拆成两个 span —— content 用 TERTIARY、compressed 用 SECONDARY
  // 区分身份, 用 gap 留白分隔(不造分隔符, 不改文字); 任一为空则不占位
  const historyHeadParts = [
    { text: contentText ?? '', color: Colors.TEXT.TERTIARY },
    { text: compressedText, color: Colors.TEXT.SECONDARY },
  ].filter((p) => p.text);
  // 2026-10-10 小欧: 历史段状态点只表"有无注入"(有绿/无灰) —— 不解析 compressed 判失败(不拆成品)

  // 2026-10-04 小欧: 装入条数 + 估算 token + 占窗率 同行; 占窗率=估算 token / 窗口, 窗口缺失则不显
  // 2026-10-09 小欧: tokens 为 "" 时不得算("" != null 恒真, ""/窗口=0 会误显 0%)
  const usedPct =
    typeof convTokens === 'number' && contextWindow
      ? Math.round((convTokens / contextWindow) * 100)
      : null;
  // 2026-10-09: 两段各读一组, 行内 metric 用两者组合; 空值真值性即不渲染
  const injectPart =
    injected && injected.count ? (
      <div>
        跨任务注入 {injected.count} 条
        {/* 2026-10-10: token 空位不合成 —— 原写死"估算Token约 {''}(–)"
 渲染成"跨任务注入 5 条 · 估算Token约 (–)"。改为条数/token 各按真值性显, 空则不显 */}
        {typeof injected.tokens === 'number' ? (
          <span>
            {' · 估算Token约 '}
            {injected.tokens.toLocaleString()} ({formatTokenK(injected.tokens)})
          </span>
        ) : null}
      </div>
    ) : null;
  const convPart =
    count || tokens ? (
      <div>
        {count ? (
          <span title="上下文全部消息条数（含本轮提问与工具调用），非仅历史对话">
            上下文 {count} 条
          </span>
        ) : null}
        {count && tokens ? <span> · </span> : null}
        {tokens ? <span>估算Token约 {formatTokenK(tokens)}</span> : null}
        {/* 占窗率: 分子是 MessageBuilder 粗估 token, 与 TaskInfoBar 的 prompt token 不同口径,
 故标注(估算)并在 title 里说明, 避免用户误当精确值。 */}
        {usedPct != null ? (
          <span
            title={`按估算 token ${convTokens} ÷ 窗口 ${contextWindow} 计算，非 LLM 实测 prompt`}
          >
            {' · 占窗率(估算) '}
            {usedPct}%
          </span>
        ) : null}
      </div>
    ) : null;

  // 2026-10-10 历史任务也挂弹框(原"只显行不挂弹框"已废止), 弹框内只显历史上下文段
  const metric = (
    <MetricItem
      // 2026-10-04 小欧: 标签"上下文"(短, 与卡片标题区分)
      label="上下文"
      // 2026-10-10 小欧: 行内值实时=对话 conv token / 历史=注入 inject token;
      // 空位由 formatTokenK 自返 '–', 不再兜 ctx.text(前端不合成状态文案)
      value={formatTokenK(typeof tokens === 'number' ? tokens : null)}
      tone={ctx.tone}
      icon={ctx.icon}
      dataState={ctxState}
    />
  );
  // 2026-10-09: 历史任务也挂弹框, 只显历史上下文段(无对话上下文段)。
  // 历史任务的 overview 来自 DB 首帧回放(useTaskInfo detail 分支), 只有 inject_context
  return (
    <FloatingEntry
      open={open}
      onOpenChange={setOpen}
      placement="bottomLeft"
      cardId="taskinfo-context-card"
      ariaLabel="历史上下文"
      cardStyle={{
        // 2026-10-08 小欧 320→560: 摘要全文可达 2048 字符(六段 Markdown), 320px 窄栏会挤成细长条。
        // 纵向不设上限(全展开不折叠), 只放宽宽让每行可读。
        width: 560,
        maxWidth: '90vw',
        display: 'flex',
        flexDirection: 'column',
        gap: Spacing.SM,
        // 2026-10-10 布局优化: 显式内边距与行高(此前靠 Popover 兜底, 各段行距不统一, 排版发虚)
        padding: `${Spacing.MD}px ${Spacing.LG}px`,
        lineHeight: 1.6,
        fontSize: FontSize.SECONDARY,
        color: Colors.TEXT.SECONDARY,
      }}
      content={
        <>
          {/* 2026-10-09: 对话上下文段仅实时任务可见 —— conv 是逐轮水位, 历史任务不定格显示 */}
          {isLiveContext && (
            <>
              <SectionHead dotColor={Colors.PRIMARY} title="对话上下文">
                {contentText && (
                  <div
                    style={{
                      color: Colors.TEXT.TERTIARY,
                      whiteSpace: 'nowrap', // 2026-10-10 禁折行: 单行直显
                    }}
                  >
                    {contentText}
                  </div>
                )}
              </SectionHead>
              {/* 2026-10-10 数据行按 HEAD_LABEL_WIDTH 缩进, 起点与标题行右侧文字对齐;
 值为 null 不渲染(否则被容器 gap 撑出空白带) */}
              {convPart && (
                <div style={{ paddingLeft: HEAD_LABEL_WIDTH }}>{convPart}</div>
              )}
              {/* 2026-10-10 截断警示归对话段内 —— truncated 是 conv_context 的字段,
 原挂在卡片最底下, 历史任务(无对话段)就落到了历史上下文下面, 归属错了 */}
              {ctxState === 'truncated' && (
                <div
                  style={{
                    color: Colors.WARNING,
                    background: Colors.BG.WARNING_LIGHT,
                    borderRadius: Radius.SM,
                    // 框通栏贴卡片左边; 框内文字顶到框左边线
                    padding: `${Spacing.XS}px ${Spacing.SM}px`,
                    paddingLeft: 0,
                    textAlign: 'left',
                  }}
                >
                  {ctx.tooltip}
                </div>
              )}
              {/* 2026-10-10 分割线左侧顶到卡片边, 横贯整卡(不缩进) */}
              <div
                style={{
                  borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
                }}
              />
            </>
          )}
          <SectionHead
            dotColor={
              injectCtx?.injected_message_count
                ? Colors.SUCCESS
                : Colors.TEXT.TERTIARY
            }
            title="历史上下文"
          >
            {/* 2026-10-10 标题行右侧 = content + compressed, 实时/历史同此一条 */}
            {historyHeadParts.length > 0 && (
              <div
                style={{
                  display: 'flex',
                  gap: Spacing.XS,
                  whiteSpace: 'nowrap', // 2026-10-10 禁折行: content 与 compressed 单行直显
                }}
              >
                {historyHeadParts.map((p) => (
                  <span key={p.color} style={{ color: p.color }}>
                    {p.text}
                  </span>
                ))}
              </div>
            )}
          </SectionHead>
          {/* 2026-10-10 同对话段, 数据行起点与标题行右侧文字对齐; null 不渲染空 div */}
          {injectPart && (
            <div style={{ paddingLeft: HEAD_LABEL_WIDTH }}>{injectPart}</div>
          )}
          {summary && ( // 2026-10-08 B: 全文显示, pre-wrap 保留换行, 不截断不折叠不滚动
            // 2026-10-10: 框通栏贴卡片左边, 框内文字顶到框左边线(paddingLeft:0)
            <div
              style={{
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                color: Colors.TEXT.PRIMARY,
                background: Colors.BG.SECONDARY,
                border: `1px solid ${Colors.BORDER.LIGHT}`,
                borderRadius: Radius.SM,
                // 框通栏贴卡片左边; 框内文字亦顶到框左边线(paddingLeft:0, 不按标签列缩进)
                padding: `${Spacing.SM}px`,
                paddingLeft: 0,
                textAlign: 'left',
              }}
            >
              <div
                style={{
                  fontWeight: FontWeight.BOLD,
                  marginBottom: Spacing.XS,
                  textAlign: 'left',
                }}
              >
                已注入摘要
              </div>
              <div style={{ lineHeight: 1.7, textAlign: 'left' }}>
                {summary}
              </div>
            </div>
          )}
        </>
      }
    >
      {metric}
    </FloatingEntry>
  );
};
