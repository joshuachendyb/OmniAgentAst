// 编辑历史: 2026-09-11 小欧 - M3b(title段独立组件): 新增 TitleBlock——任务统计 title 段独立组件,
//   数据源=final 帧(outcome/duration/model/provider/token), 绝不读 DB; 两行排版视觉优先 — 小欧-2026-09-11
// 2026-09-11 小欧 - 修: 去 as 强转(DRY/类型安全), 复用 formatTokenCompact 公用函数; 第一行=状态+时长+模型, 第二行=4组token
// 2026-09-11 小欧 - 修复: 删??null(与TokenLayer number|undefined对齐, TS2322归零); 模型顺序统一provider/model(站点惯例+StaticStatsBlock一致); cancelled归default(非error红语义) — 小欧-2026-09-11
// 2026-09-12 小欧 - 修复: 抽renderToken()消4组token包裹渲染重复(DRY); 原IIFE三连Typography.Text改4行直线调用 — 小欧-2026-09-12
// 2026-09-13 小欧 - 用CircleArrow/PillBadge可复用组件替换Tag和▲▼; 间距: pill↔time=12px time↔model=15px — 小欧-2026-09-13
// 2026-09-15 小欧 - 第一阶段: 标题13→14(FontSize.PRIMARY); 间距12/15→Spacing(LG/XL,15无档取XL16收敛);
//   S3字号11→常量; S4 pill三态色令牌化; ④时长/模型灰字改TEXT.PRIMARY+12px;
//   ⑤⑥非completed且provider/model不缺失才渲染模型段(completed隐藏模型,字段缺失不显示); H2累计组强调; A3容器title悬停提示 — 小欧-2026-09-15
// 2026-10-27 小欧 - 第二轮(doc[48] N1-N15):
//   N1 pill三态改 PILL_* 专用深档(白字对比度 2.27/3.27/1.84→5.59/7.75/7.00, 全达 WCAG AA 4.5:1);
//   N2 删 shine——终态静默(扫光是"进行中"语义, 用在静态终态属语义错位+持续动画噪音);
//   N3/N4 上行加 title-block-header 类补 hover+focus-visible(对齐系统内 4 处既有可点元素规范, 原整行 role=button 却两者皆无, 键盘焦点不可见);
//   N5 交互下沉上行, 下行 token 移出可点区可复制(原整行可点致选中耗时文本即误触折叠);
//   N6 主标题加 PRIMARY 色条(原 14px 纯文字反弱于五节 12px 带条子标题, 层级倒挂);
//   N7 token 三组 #8c8c8c→STRONG#333(3.36→12.63 达 AA); N9 底部 padding 补 MD(原 0 致文字贴容器底);
//   N10 耗时 <60s 保留 1 位小数(修 Math.round 精度损失 1.4s→"1s") ≥60s 转 "XmYs" 缺失整项隐藏;
//   N11 模型段仅 failed 显示(cancelled 是用户主动取消, 看模型无排查意义);
//   N13 下行间距 XS/2→SM + 累计组字重 500→600; N14 补 aria-label; N15 token 全缺显空态(原整行坍缩) — 小欧-2026-10-27
// 2026-10-27 小欧 - v1.4: token 显示改用中文标签(输入/输出/总计) + K/M 单位格式(复用 formatTokenK);
// 2026-10-27 小欧 - v1.5: 总计数字后加 [tok] 单位标识(token 缩写);
// 2026-10-27 小欧 - DRY: 提取 InlineText 组件消除 4 处重复的 Typography.Text 样式 — 小欧-2026-10-27
import React from 'react';
import { Typography } from 'antd';
import type { ExecutionStep } from '@/types/execution';
import {
  Colors,
  FontSize,
  FontWeight,
  Spacing,
} from '@/utils/stepStyles';
import { CircleArrow } from '@/components/CircleArrow';
import { PillBadge } from '@/components/PillBadge';
import { formatTokenK } from '../taskinfo/infoMaps';

interface TitleBlockProps {
  finalStep?: ExecutionStep | null;
  expanded: boolean;
  onToggle: () => void;
  // 2026-10-27 小欧 - 新增 startTimestamp: SSE start 帧时间戳, 用于计算开始/结束时间范围
  //   结束时间 = startTimestamp + duration * 1000; 缺失时整项隐藏 — 小欧-2026-10-27
  startTimestamp?: number;
}

// 2026-10-27 小欧 - 紧凑耗时格式(doc[48] N10): <60s 保留 1 位小数(修原 Math.round 精度损失 1.4s→"1s"),
//   ≥60s 转 "XmYs"。不复用 utils/time.ts 的 formatDurationHMS——其 HH:MM:SS 定长格式对紧凑标题栏过长,
//   且内部 Math.floor 同样丢精度, 语义是 TaskInfoBar 实时走表, 不适配终态摘要。
//   当前唯一消费方, YAGNI 不提取公用; 有第二消费方再提 — 小欧-2026-10-27
const formatDurationCompact = (sec: number): string => {
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const total = Math.round(sec);
  return `${Math.floor(total / 60)}m${total % 60}s`;
};

// 2026-10-27 小欧 - 时间范围格式：同日只显时分秒，跨日补 MM-DD
//   用于标题栏显示开始/结束时间，紧凑格式保持一行 — 小欧-2026-10-27
const formatTimeRange = (
  startMs: number,
  endMs: number
): string => {
  const start = new Date(startMs);
  const end = new Date(endMs);
  const pad = (n: number) => String(n).padStart(2, '0');
  const formatTime = (d: Date) =>
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  // 跨日时补 MM-DD 前缀
  const isSameDay = start.toDateString() === end.toDateString();
  if (isSameDay) {
    return `${formatTime(start)}→${formatTime(end)}`;
  }
  const formatDateTime = (d: Date) =>
    `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${formatTime(d)}`;
  return `${formatDateTime(start)}→${formatDateTime(end)}`;
};

// 2026-10-27 小欧 - DRY: 提取行内文本组件，消除 4 处重复的 Typography.Text 样式
//   原 4 处（时间范围/运行耗时/模型/token）都重复 fontSize+whiteSpace 样式，token 多 color+fontWeight
//   提取后调用方只传差异化属性，符合 SRP（组件只负责样式，不负责内容） — 小欧-2026-10-27
const InlineText: React.FC<{
  children: React.ReactNode;
  color?: string;
  fontWeight?: number;
}> = ({ children, color, fontWeight }) => (
  <Typography.Text
    style={{
      fontSize: FontSize.SECONDARY,
      whiteSpace: 'nowrap',
      color,
      fontWeight,
    }}
  >
    {children}
  </Typography.Text>
);

const TitleBlock: React.FC<TitleBlockProps> = ({
  finalStep,
  expanded,
  onToggle,
  startTimestamp,
}) => {
  if (!finalStep) return null;
  const outcome = finalStep.outcome;
  const duration = finalStep.duration;
  const model = finalStep.model;
  const provider = finalStep.provider;
  // 2026-09-11 小欧 修复: 删 ?? null——TokenLayer 字段类型 number|undefined, 传 null 违 TS2322；此处语义完全等价保留 — 小欧-2026-09-11
  const prompt =
    finalStep.prompt_tokens ?? finalStep.accumulated_usage?.prompt_tokens;
  const completion =
    finalStep.completion_tokens ??
    finalStep.accumulated_usage?.completion_tokens;
  const total =
    finalStep.total_tokens ?? finalStep.accumulated_usage?.total_tokens;
  // 2026-10-27 小欧 - N1: 三态色改 PILL_* 专用深档——原 SUCCESS/ERROR/BORDER.STRONG 配白字
  //   实测 2.27/3.27/1.84:1 全不达 WCAG AA 4.5:1(cancelled 灰底白字几乎不可读); 新值实测 5.59/7.75/7.00:1。
  //   新增令牌而非改 SUCCESS/ERROR 值——后者是全站功能色(状态点/边框/图标/警示条), 改值会波及其他引用 — 小欧-2026-10-27
  const pillColor =
    outcome === 'completed'
      ? Colors.PILL_SUCCESS
      : outcome === 'failed'
        ? Colors.PILL_ERROR
        : Colors.PILL_CANCELLED;
  return (
    <div
      style={{
        marginTop: Spacing.LG,
        borderTop: `1px solid ${Colors.BORDER.LIGHT}`,
      }}
    >
      {/* 上行：可点折叠开关
          2026-10-27 小欧 - N3/N4/N6/N9: 加 title-block-header 类补 hover+focus-visible(对齐系统内 4 处既有可点元素规范);
          主标题加 PRIMARY 色条(层级高于五节子标题); padding 在本行(确保 hover 背景覆盖整行 + 折叠态底部有留白)
          注: N5 原设计"下行 token 移出可点区"已废弃, 用户反馈要求 token 显示在上行, 故 token 与交互同在一行 — 小欧-2026-10-27 */}
      <div
        className="title-block-header"
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        aria-label={
          expanded ? '任务统计，点击收起详情' : '任务统计，点击展开详情'
        }
        title={expanded ? '点击收起统计详情' : '点击展开统计详情'}
        onClick={onToggle}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onToggle();
          }
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Spacing.MD,
          padding: `${Spacing.MD}px ${Spacing.LG}px`,
          cursor: 'pointer',
        }}
      >
        <Typography.Text
          strong
          style={{
            fontSize: FontSize.PRIMARY,
            borderLeft: `2px solid ${Colors.PRIMARY}`,
            paddingLeft: Spacing.SM,
          }}
        >
          任务统计
        </Typography.Text>
        <PillBadge text={outcome ?? '-'} color={pillColor} />
        {/* 2026-10-27 小欧 - 新增时间范围显示：startTimestamp + duration 计算结束时间，
            箭头式紧凑格式保持一行；缺失时整项隐藏 — 小欧-2026-10-27 */}
        {startTimestamp != null && duration != null && (
          <>
            <span style={{ display: 'inline-block', width: Spacing.LG }} />
            <InlineText>
              {formatTimeRange(startTimestamp, startTimestamp + duration * 1000)}
            </InlineText>
          </>
        )}
        {/* 2026-10-27 小欧 - N10: 缺失整项隐藏(含间距 span), 不渲染"运行耗时 -"(标签与占位符黏连) — 小欧-2026-10-27 */}
        {duration != null && (
          <>
            <span style={{ display: 'inline-block', width: Spacing.LG }} />
            <InlineText>
              运行耗时 {formatDurationCompact(duration)}
            </InlineText>
          </>
        )}
        {/* 2026-10-27 小欧 - N11: 条件由 outcome!=='completed' 收窄为 ==='failed'——
            cancelled 是用户主动取消, 看模型无排查意义; 真正需排查的是 failed — 小欧-2026-10-27 */}
        {outcome === 'failed' && (provider || model) && (
          <>
            <span style={{ display: 'inline-block', width: Spacing.XL }} />
            <InlineText>
              {/* 2026-09-11 小欧 修复: 统一 provider/model——与站点惯例(useChatPanels L191 provider (model))及 StaticStatsBlock 一致 — 小欧-2026-09-11 */}
              {provider ?? '-'} / {model ?? '-'}
            </InlineText>
          </>
        )}
        {/* 2026-10-27 小欧 - token 显示：显示任务级 P/C/T 三个数字，位置够用
            2026-10-27 小欧 - 用户反馈：上行显示 3 个数字 P/C/T，位置是够的
            2026-10-27 小欧 - 用户反馈：总计数字后加 [tok] 单位标识（token 缩写） — 小欧-2026-10-27 */}
        {total != null && (
          <>
            <span style={{ display: 'inline-block', width: Spacing.LG }} />
            <InlineText color={Colors.TEXT.PRIMARY} fontWeight={FontWeight.BOLD}>
              输入:{prompt != null ? formatTokenK(prompt) : '-'} 输出:{completion != null ? formatTokenK(completion) : '-'} 总计:{formatTokenK(total)}[tok]
            </InlineText>
          </>
        )}
        <CircleArrow
          size={24}
          expanded={expanded}
          glow
          style={{ marginLeft: 'auto' }}
        />
      </div>
    </div>
  );
};

export { TitleBlock };
