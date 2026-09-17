// 编辑历史: 2026-09-08 小欧 - 六章6.5: 抽"标签灰 + 数值加粗 + 可选分项/图标"两段式通用组件(DRY, G5/G6 ≥4 处复用)
//   支持 detail(P/C 中灰)、tone、icon、maxWidth 截断态、tooltip、data-state(测试钩子) — 小欧-2026-09-08
import React from 'react';
import { Tooltip } from 'antd';
import { Colors, FontSize, FontWeight, Spacing } from '@/utils/stepStyles';
import { EllipsisTip } from './EllipsisTip';

export type MetricTone = 'primary' | 'secondary' | 'warning' | 'tertiary';

export interface MetricItemProps {
  label: string; // 标签（灰 11px）
  value: string; // 数值（加粗 12px 或 warning）
  detail?: string; // 可选分项（P/C 等，中灰 12px 500）
  tone?: MetricTone;
  icon?: React.ReactNode;
  maxWidth?: number; // >0 时数值区 ellipsis + Tooltip 全文
  tooltip?: string;
  dataState?: string; // aria/data 钩子（P1-8 测试断言）
}

const TONE_COLOR: Record<MetricTone, string> = {
  primary: Colors.TEXT.PRIMARY,
  secondary: Colors.TEXT.SECONDARY,
  tertiary: Colors.TEXT.TERTIARY, // 3.3: summary-only/empty 标签级弱文字
  warning: Colors.WARNING,
};

export const MetricItem: React.FC<MetricItemProps> = ({
  label,
  value,
  detail,
  tone = 'primary',
  icon,
  maxWidth,
  tooltip,
  dataState,
}) => {
  const body = (
    <React.Fragment>
      {icon && (
        <span
          style={{ color: `var(--taskinfo-entry-active, ${TONE_COLOR[tone]})` }}
        >
          {icon}
        </span>
      )}
      <span
        style={{
          fontSize: FontSize.SECONDARY,
          fontWeight: FontWeight.BOLD,
          // 编辑历史: 2026-09-09 小欧 - [16]v4.4 修复#1(3.1.3 G6 数值 hover 变 PRIMARY):
          //   数值色唯一机制 = CSS 变量 --taskinfo-entry-active(回退 tone 色);
          //   .taskinfo-entry:hover 注入蓝值即可覆盖任意 tone, 无分支无 !important。 — 小欧-2026-09-09
          color: `var(--taskinfo-entry-active, ${TONE_COLOR[tone]})`,
        }}
      >
        {value}
      </span>
      {detail && (
        <span
          style={{
            fontSize: FontSize.SECONDARY,
            fontWeight: FontWeight.MEDIUM,
            color: Colors.TEXT.SECONDARY,
          }}
        >
          {detail}
        </span>
      )}
    </React.Fragment>
  );
  const wrapped = maxWidth ? (
    <EllipsisTip text={value} tooltip={tooltip} maxWidth={maxWidth}>
      {body}
    </EllipsisTip>
  ) : tooltip ? (
    <Tooltip title={tooltip}>{body}</Tooltip>
  ) : (
    body
  );
  return (
    <span
      role="status"
      aria-live="polite"
      data-state={dataState}
      // 小欧 2026-09-09 #1: tone 钩子(data-tone 为测试承载点; 视觉色由 CSS 变量 --taskinfo-entry-active 统一,
      //   .taskinfo-entry:hover 注入 PRIMARY(3.1.3 G6)) — 小欧-2026-09-09
      data-tone={tone}
      title={tooltip}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: Spacing.XS,
        fontSize: FontSize.SMALL,
        color: Colors.TEXT.TERTIARY,
      }}
    >
      <span style={{ fontSize: FontSize.SMALL, color: Colors.TEXT.TERTIARY }}>
        {label}
      </span>
      {wrapped}
    </span>
  );
};
