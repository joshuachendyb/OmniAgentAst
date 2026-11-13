// 编辑历史: 2026-11-09 小欧 - 新建：设置页提示呈现层（HelpLabel 虚线可点标签 + TipContent 多行提示容器），消除页面内 4 份同款内联样式 — 小欧-2026-11-09
import React from 'react';
import { Tooltip } from 'antd';
import { Colors, FontSize, FontWeight } from '@/utils/stepStyles';
import { settingsLabelStyle } from '@/theme/settingsTokens';

/** 带说明的行名：虚线下划线 + 问号光标，悬停出说明 */
export const HelpLabel: React.FC<{
  title: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, children }) => (
  <Tooltip title={title}>
    <span
      style={{
        ...settingsLabelStyle,
        cursor: 'help',
        borderBottom: `1px dashed ${Colors.TEXT.WEAK}`,
      }}
    >
      {children}
    </span>
  </Tooltip>
);

/** 多行说明容器：统一字号/行高/最大宽度，传了 title 则加粗首行 */
export const TipContent: React.FC<{
  title?: string;
  maxWidth?: number;
  children: React.ReactNode;
}> = ({ title, maxWidth = 440, children }) => (
  <div style={{ fontSize: FontSize.SECONDARY, lineHeight: 1.8, maxWidth }}>
    {title && <div style={{ fontWeight: FontWeight.BOLD }}>{title}</div>}
    {children}
  </div>
);
