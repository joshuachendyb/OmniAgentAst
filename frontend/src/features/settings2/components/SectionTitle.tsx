// 编辑历史: 2026-09-20 小强 - 新建：小节头（4.6 系统三小节分隔）
// 2026-09-21 小欧 - P0-8：margin 间距→Spacing 令牌（[58] P0-8）
import React from 'react';
import { FontSize, FontWeight, Spacing } from '@/utils/stepStyles';

export const SectionTitle: React.FC<{ title: string }> = ({ title }) => (
  <div
    style={{
      fontSize: FontSize.PRIMARY,
      fontWeight: FontWeight.BOLD,
      margin: `${Spacing.LG}px 0 ${Spacing.XS}px`,
    }}
  >
    {title}
  </div>
);
