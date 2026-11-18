// 2026-11-18 商量 - 新建: 浮层卡片视觉壳(计划/信任/问询三处共用)
//   WHY: 三块浮层此前各写各的 padding/分割线/空态/列表行, 结果同一页出现三种卡片语言
//   (Drawer+Table / 自绘 div / antd 缺省)。这里只收敛**视觉**, 不收业务:
//   壳(头部+内容区+脚注) + 三个原子(胶囊/列表行/空态), 内容由调用方注入。
//   两种形态:
//     raised —— 直接绝对定位的浮层(问询面板), 由本组件画边框/圆角/投影, 分割线通栏;
//     plain  —— 挂在 antd Popover 里的卡片(计划/信任), 边框阴影与内距由 Popover 承担,
//               本组件只排头部/内容/脚注与缩进分割线, 不再叠一层框(叠框是"贴纸感"的来源)。
// 2026-11-18 商量 - PanelRow 两处调整: ①横向内距归零, 行文字与卡片标题同一条左轴线;
//   ②新增 hoverable(不可点但行内有悬停才现身的操作时给浅一档底色) — 商量-2026-11-18
import type { CSSProperties, ReactNode } from 'react';

import { CONTROL_PADDING, CONTROL_RADIUS } from '@/theme/controlScale';
import { Gap, LineHeight } from '@/theme/spacing';
import {
  Colors,
  FontSize,
  FontWeight,
  Radius,
  Spacing,
} from '@/utils/stepStyles';

/** 卡片浮起投影(两级投影: 近处接地 + 远处扩散, 单级投影是"贴纸感"的根源) */
const RAISED_SHADOW =
  '0 8px 24px rgba(0, 0, 0, 0.1), 0 2px 6px rgba(0, 0, 0, 0.04)';

interface PanelCardProps {
  title: ReactNode;
  /** 标题右侧状态胶囊(计数/进度/题号) */
  meta?: ReactNode;
  /** 头部最右操作按钮组 */
  actions?: ReactNode;
  /** 头部正下方的通栏细条(进度条等), 自身不带内距 */
  subheader?: ReactNode;
  /** 内容区(列表/正文); 省略则不渲染内容区(最小化态只留头部) */
  children?: ReactNode;
  /** 脚注行(口径说明, 一句话) */
  footer?: ReactNode;
  /** 内容区子元素间距, 默认同列堆叠档 */
  gap?: number;
  variant?: 'plain' | 'raised';
  bodyStyle?: CSSProperties;
  /** 卡片整体样式: 浮层场景传 width/maxHeight */
  style?: CSSProperties;
}

/**
 * 浮层卡片壳 —— 头部(标题+胶囊+操作) / 内容区 / 脚注三段。
 * 所有间距走 Spacing/Gap 刻度, 行高显式下发, 不依赖 antd 缺省值。
 */
export function PanelCard({
  title,
  meta,
  actions,
  subheader,
  children,
  footer,
  gap = Gap.STACK,
  variant = 'plain',
  bodyStyle,
  style,
}: PanelCardProps) {
  const raised = variant === 'raised';
  const divider = `1px solid ${Colors.BORDER.LIGHT}`;

  const root: CSSProperties = raised
    ? {
        background: Colors.BG.PRIMARY,
        border: divider,
        borderRadius: Radius.CONTAINER,
        boxShadow: RAISED_SHADOW,
        overflow: 'hidden',
      }
    : { background: 'transparent' };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minWidth: 0,
        textAlign: 'left',
        lineHeight: LineHeight.BODY,
        ...root,
        ...style,
      }}
    >
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: Gap.INLINE,
          // raised 自带内距并让分割线通栏; plain 的内距由 Popover 提供, 这里只留分割线前的呼吸
          ...(raised
            ? { padding: `${Spacing.MD}px ${Spacing.LG}px` }
            : { paddingBottom: Spacing.MD }),
          // 有 subheader 细条(进度/分段)时不再画头部下边框: 两条线紧贴会读成"重线"
          borderBottom: subheader ? undefined : divider,
        }}
      >
        <span
          style={{
            fontSize: FontSize.PRIMARY,
            fontWeight: FontWeight.BOLD,
            color: Colors.TEXT.STRONG,
            whiteSpace: 'nowrap',
          }}
        >
          {title}
        </span>
        {meta}
        {actions ? (
          <span
            style={{
              marginLeft: 'auto',
              display: 'flex',
              alignItems: 'center',
              gap: Gap.INLINE,
            }}
          >
            {actions}
          </span>
        ) : null}
      </div>
      {subheader}
      {children === undefined ? null : (
        <div
          // panel-scroll: 内容区限高时用细滚动条(index.css), 不套 antd 缺省滚动条样式;
          // 不限高时该类的规则不生效, 故无条件挂载
          className="panel-scroll"
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap,
            ...(raised
              ? { padding: `${Spacing.LG}px` }
              : { padding: `${Spacing.LG}px 0` }),
            minWidth: 0,
            ...bodyStyle,
          }}
        >
          {children}
        </div>
      )}
      {footer ? (
        <div
          style={{
            ...(raised
              ? {
                  padding: `${Spacing.MD}px ${Spacing.LG}px`,
                  background: Colors.BG.SECONDARY,
                }
              : { paddingTop: Spacing.MD }),
            borderTop: divider,
            fontSize: FontSize.SECONDARY,
            color: Colors.TEXT.TERTIARY,
          }}
        >
          {footer}
        </div>
      ) : null}
    </div>
  );
}

// ==================== 原子 ====================

type ChipTone = 'default' | 'primary' | 'success' | 'warning';

const CHIP_TONE: Record<ChipTone, { bg: string; color: string }> = {
  default: { bg: Colors.BG.TERTIARY, color: Colors.TEXT.MUTED },
  primary: { bg: Colors.BG.SELECTED, color: Colors.PRIMARY },
  success: { bg: '#f6ffed', color: Colors.PILL_SUCCESS },
  warning: { bg: Colors.WARNING_BG, color: Colors.WARNING },
};

/** 胶囊标签 —— 计数/进度/状态/题号, 11px 恒定, 不撑高所在行 */
export function PanelChip({
  children,
  tone = 'default',
  style,
}: {
  children: ReactNode;
  tone?: ChipTone;
  style?: CSSProperties;
}) {
  const { bg, color } = CHIP_TONE[tone];
  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: `${CONTROL_PADDING.CHIP_Y}px ${CONTROL_PADDING.CHIP_X}px`,
        borderRadius: Radius.SM,
        background: bg,
        color,
        fontSize: FontSize.SMALL,
        fontWeight: FontWeight.MEDIUM,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {children}
    </span>
  );
}

/** 列表行 —— 卡片内一条记录(悬停底色由 index.css 的 .panel-row / .panel-row-hover 承担, 零重渲染) */
export function PanelRow({
  children,
  style,
  onClick,
  ariaLabel,
  testId,
  hoverable,
}: {
  children: ReactNode;
  style?: CSSProperties;
  /** 传了才是可点行(role=button + Tab 序 + Enter/Space); 不传则是纯展示行, 无悬停底色 */
  onClick?: () => void;
  ariaLabel?: string;
  testId?: string;
  /**
   * 行不可点、但行内有"悬停才现身"的操作(如信任清单的撤销 ✕)时传 true:
   * 给出**较弱**的悬停底色(BG.SECONDARY), 让用户确认自己指在哪一行。
   * 与可点行的 #f0f0f0 分两档 —— 底色深浅即"能不能点"的信号, 两档不做混用。
   */
  hoverable?: boolean;
}) {
  return (
    <div
      className={`panel-row${hoverable ? ' panel-row-hover' : ''}`}
      data-testid={testId}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      aria-label={ariaLabel}
      onClick={onClick}
      onKeyDown={
        onClick
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClick();
              }
            }
          : undefined
      }
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: Gap.INLINE,
        // 横向不留内距: 行文字与卡片标题同一条左轴线(标题在卡片内容区左缘), 悬停底色通栏。
        // 原 8px 让列表比标题右移一格, 一卡之内两条左轴线 = 手写版面的典型痕迹。
        padding: `${Spacing.SM}px 0`,
        borderRadius: CONTROL_RADIUS.sm,
        lineHeight: LineHeight.DENSE,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** 空态 —— 一句话 + 一句引导, 不用插图(插图在密集浮层里是噪声) */
export function PanelEmpty({ text, hint }: { text: string; hint?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: Gap.STACK,
        alignItems: 'center',
        padding: `${Spacing.XL}px ${Spacing.SM}px`,
        textAlign: 'center',
      }}
    >
      <span style={{ fontSize: FontSize.PRIMARY, color: Colors.TEXT.WEAK }}>
        {text}
      </span>
      {hint ? (
        <span
          style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.TERTIARY }}
        >
          {hint}
        </span>
      ) : null}
    </div>
  );
}
