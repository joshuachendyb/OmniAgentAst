// 编辑历史: 2026-09-20 小强 - 新建：SettingIcon 唯一图标出口 + DirtyDot + EnvTag；全部 antd SVG，禁止 emoji（7.9.4）
// 2026-09-21 小欧 - P2-4：Tab 图标去掉内联色，随 antd Tabs 选中态继承主色（[58] P2-4）
// 2026-09-21 小欧 - 全文逐章核查：gap/marginLeft/fontSize 裸数字 → Spacing.XS/MD、FontSize.PRIMARY 令牌；DirtyDot 6px 圆点为 P2-2 文档明确规格保留（[58] v1.12 第七章 铁规）
import React from 'react';
import {
  ApiOutlined,
  BgColorsOutlined,
  CodeOutlined,
  CopyOutlined,
  DesktopOutlined,
  GlobalOutlined,
  MessageOutlined,
  SafetyOutlined,
} from '@ant-design/icons';
import { Tag } from 'antd';
import { Colors, FontSize, Spacing } from '@/utils/stepStyles';
import type { TabKey } from '../types';

// 2026-09-21 小欧 - P2-4 定案：Tab 图标 fontSize=14（文档明确规格，不随 Tabs 主题缩放，7.9.x Tabs 集成）
const TAB_ICON_STYLE: React.CSSProperties = {
  fontSize: 14,
};

export const SettingIcon: Record<TabKey, React.ReactNode> = {
  general: <GlobalOutlined style={TAB_ICON_STYLE} />,
  model: <ApiOutlined style={TAB_ICON_STYLE} />,
  security: <SafetyOutlined style={TAB_ICON_STYLE} />,
  chat: <MessageOutlined style={TAB_ICON_STYLE} />,
  appearance: <BgColorsOutlined style={TAB_ICON_STYLE} />,
  system: <DesktopOutlined style={TAB_ICON_STYLE} />,
  sandbox: <CodeOutlined style={TAB_ICON_STYLE} />,
};

/** 已修改角标：6px 实心圆点 + 12px 次文（7.9.2，不用 emoji）。 */
export const DirtyDot: React.FC = () => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: Spacing.XS }}>
    <span
      style={{
        width: 6,
        height: 6,
        borderRadius: '50%',
        background: Colors.PRIMARY,
        display: 'inline-block',
      }}
    />
    <span
      style={{ fontSize: FontSize.SECONDARY, color: Colors.TEXT.SECONDARY }}
    >
      已修改
    </span>
  </span>
);

/** env 接管标注（9.2.3）。 */
export const EnvTag: React.FC = () => (
  <Tag color="orange" style={{ marginLeft: Spacing.MD }}>
    来自环境变量
  </Tag>
);

/** 只读复制按钮图标（7.7/7.9.4）。 */
export const CopyIcon: React.FC = () => (
  <CopyOutlined style={{ fontSize: FontSize.PRIMARY }} />
);
