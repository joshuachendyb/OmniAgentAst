/**
 * PillShell - 顶栏胶囊外壳: Tooltip 白卡片 + 悬停底色 + 容器 span(role/aria-label/光标)。
 * 三胶囊(配置/服务/流状态)只传内容与外层语义, 浮层版式与悬停交互在此一处定义。
 *
 * @author 小欧
 * @date 2026-11-03
 */
// 编辑历史: 2026-11-03 小欧 - 新建: 三胶囊各自复制 Tooltip 颜色/styles、容器栅格与 hover 事件(DRY),
//   抽出外壳后三处只留内容 — 小欧-2026-11-03
// 编辑历史: 2026-11-03 小欧 - 容器收口字号12/行高16px/nowrap: 原继承顶栏 64px 行高致色块高 72px(字的6倍);
//   16+pad8=24 与顶栏 Button/Select 同高, 三胶囊不再各自声明字号 — 小欧-2026-11-03
import React, { type CSSProperties, type ReactNode } from 'react';
import { Tooltip } from 'antd';
import type { TooltipProps } from 'antd';
import {
  Colors,
  Radius,
  Spacing,
  BorderWidth,
  FontSize,
} from '../../utils/stepStyles';
import { PILL_TIP_ROOT_MAX_W } from './PillTip';

/** 浮层白卡片: 根宽上限/内边距/描边/圆角, 三胶囊同一份 — 小欧-2026-11-03 */
const TOOLTIP_PROPS: Pick<TooltipProps, 'color' | 'styles'> = {
  color: Colors.BG.PRIMARY,
  styles: {
    root: { maxWidth: PILL_TIP_ROOT_MAX_W },
    body: {
      padding: `${Spacing.MD}px ${Spacing.LG}px`,
      border: `${BorderWidth.THIN}px solid ${Colors.BORDER.VERTICAL}`,
      borderRadius: Radius.LG,
    },
  },
};

/** 顶栏白底上的悬停浅灰(与侧栏底条 hover 同令牌) — 小欧-2026-11-03 */
const HOVER_BG = Colors.BG.HOVER;

/** 容器栅格: pad 4/8=Spacing.XS/MD, 圆角4=Radius.SM, 字12 — 小欧-2026-11-03
 *  行高钉死16px(保留裸值: 字号令牌12/14无同值可替): 顶栏 .ant-layout-header 默认 64px 行高会被继承,
 *  色块高 72px=12px 字的 6 倍; 16+上下 pad 8=24 与顶栏 Button/Select/Avatar 同高。nowrap 防挤压逐字换行 — 小欧-2026-11-03 */
const SHELL_STYLE: CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  padding: `${Spacing.XS}px ${Spacing.MD}px`,
  borderRadius: Radius.SM,
  fontSize: FontSize.SECONDARY,
  lineHeight: '16px',
  whiteSpace: 'nowrap',
  transition: 'background 0.2s',
};

interface PillShellProps {
  role: 'button' | 'img';
  ariaLabel: string;
  /** 浮层内容(PillTip) */
  tooltip: ReactNode;
  /** 点击行为; 缺省=纯展示胶囊, 光标 help */
  onClick?: () => void;
  /** 忙态(检测中): 不显示悬停底色, 光标回落默认 */
  busy?: boolean;
  className?: string;
  /** 浮层开合回调(服务胶囊打开即静默重检) */
  onTooltipOpenChange?: (open: boolean) => void;
  children: ReactNode;
}

export const PillShell: React.FC<PillShellProps> = ({
  role,
  ariaLabel,
  tooltip,
  onClick,
  busy,
  className,
  onTooltipOpenChange,
  children,
}) => (
  <Tooltip
    {...TOOLTIP_PROPS}
    onOpenChange={onTooltipOpenChange}
    title={tooltip}
  >
    <span
      role={role}
      aria-label={ariaLabel}
      className={className}
      onClick={onClick}
      style={{
        ...SHELL_STYLE,
        cursor: busy ? 'default' : onClick ? 'pointer' : 'help',
      }}
      onMouseEnter={(e) => {
        if (!busy) e.currentTarget.style.background = HOVER_BG;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.background = 'transparent';
      }}
    >
      {children}
    </span>
  </Tooltip>
);
