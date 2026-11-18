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
// 2026-11-18 商量 - 行距归一到一处 + 新增自绘图标按钮:
//   ① PanelRow 行高改由自身上下内距独占(XS 4+4 = 相邻两条 8), 调用方一律不再叠 gap/SECTION ——
//      此前信任清单"组 gap 4 + 行内距 4+4"两处各算一半, 改一处另一处不动(违 theme/spacing.ts 铁律一);
//   ② 行内二次操作(撤销 ✕)改绝对定位: 它的 24px 盒高原先把 12px 文字行从 25px 撑到 32px,
//      行距看起来比实际刻度大 7px —— 行高不该被行内一个图标按钮决定;
//   ③ 新增 PanelIconButton: antd 按钮的高/内距/圆角/焦点环都是库缺省派生(控 theme/controlScale.ts 铁律),
//      这里自绘 button, 盒高只取本项目控件小档, 且不参与行高计算 — 商量-2026-11-18
import { forwardRef } from 'react';
import type {
  CSSProperties,
  MouseEvent as ReactMouseEvent,
  ReactNode,
} from 'react';

import {
  CONTROL_HEIGHT_SM,
  CONTROL_PADDING,
  CONTROL_RADIUS,
} from '@/theme/controlScale';
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

export type ChipTone = 'default' | 'primary' | 'success' | 'warning' | 'danger';

const CHIP_TONE: Record<ChipTone, { bg: string; color: string }> = {
  default: { bg: Colors.BG.TERTIARY, color: Colors.TEXT.MUTED },
  primary: { bg: Colors.BG.SELECTED, color: Colors.PRIMARY },
  success: { bg: '#f6ffed', color: Colors.PILL_SUCCESS },
  warning: { bg: Colors.WARNING_BG, color: Colors.WARNING },
  // 2026-11-18 商量 - danger 档: 危险级(删除/拦截)用浅红底 + 深红字。字色取 ERROR_TEXT 而非 ERROR ——
  //   11px 小字用亮红 #ff4d4f 在白底仅 3.0:1 会糊, ERROR_TEXT 在浅红底上仍达 AA。
  //   与 warning 档一起构成"危险 / 警示 / 中性"三级严重度, 供 HITL 授权弹窗的等级胶囊使用。
  danger: { bg: Colors.ERROR_BG, color: Colors.ERROR_TEXT },
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
        // 纵向内距是本组件**唯一**的行距归属: 相邻两行看着是 8px, 调用方不得再叠 gap。
        padding: `${Spacing.XS}px 0`,
        // 行内二次操作(信任撤销 ✕)走绝对定位, 自身盒高不参与本行高度计算
        position: 'relative',
        borderRadius: CONTROL_RADIUS.sm,
        lineHeight: LineHeight.DENSE,
        ...style,
      }}
    >
      {children}
    </div>
  );
}

/** 图标按钮色调: default = 中性(关/收), danger = 危险动作(放弃问询) */
type IconTone = 'default' | 'danger';

/** 图标按钮文案色 —— 只取既有语义色, 不新开色值 */
const ICON_TONE_COLOR: Record<IconTone, string> = {
  default: Colors.TEXT.SECONDARY,
  danger: Colors.ERROR,
};

interface PanelIconButtonProps {
  icon: ReactNode;
  ariaLabel: string;
  testId?: string;
  onClick?: (e: ReactMouseEvent<HTMLButtonElement>) => void;
  tone?: IconTone;
  /** 图标字号: 行密度高时降到 SECONDARY(12), 免得图标大过同行文字 */
  fontSize?: number;
  /** 追加类名(如 .panel-del 的渐进披露) */
  className?: string;
  style?: CSSProperties;
}

/**
 * 纯图标按钮 —— 自绘 button, 不走 antd Button。
 *
 * WHY 自绘: antd 按钮的控件高/内距/圆角/焦点环一律按库缺省派生(0.75×/1.25× 之类),
 * 拿它当本项目标准违 theme/controlScale.ts 的铁律。这里三项全部取本项目令牌,
 * 且盒高恒等于控件小档 24 —— 行内放它不会把所在行撑高(信任清单行距曾被撑大 7px)。
 *
 * forwardRef: 纯图标按钮几乎都要挂 Tooltip 做说明, antd 的 Tooltip 给子元素下发 ref 取锚点,
 * 函数组件不转发则拿不到锚点(且 React 报 "Function components cannot be given refs")。
 */
export const PanelIconButton = forwardRef<
  HTMLButtonElement,
  PanelIconButtonProps
>(function PanelIconButton(
  {
    icon,
    ariaLabel,
    testId,
    onClick,
    tone = 'default',
    fontSize = FontSize.PRIMARY,
    className,
    style,
  },
  ref
) {
  return (
    <button
      ref={ref}
      type="button"
      className={className ? `panel-icon-btn ${className}` : 'panel-icon-btn'}
      data-testid={testId}
      aria-label={ariaLabel}
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: CONTROL_HEIGHT_SM,
        height: CONTROL_HEIGHT_SM,
        flexShrink: 0,
        padding: 0,
        border: 'none',
        borderRadius: CONTROL_RADIUS.sm,
        background: 'transparent',
        color: ICON_TONE_COLOR[tone],
        fontSize,
        lineHeight: 1,
        cursor: 'pointer',
        ...style,
      }}
    >
      {icon}
    </button>
  );
});

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
