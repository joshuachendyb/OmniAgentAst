// 编辑历史: 2026-09-20 小强 - 新建：小节头（4.6 系统三小节分隔）
import React from 'react';
import { FontSize, FontWeight } from '@/utils/stepStyles';

export const SectionTitle: React.FC<{ title: string }> = ({ title }) => (
  <div
    style={{
      fontSize: FontSize.PRIMARY,
      fontWeight: FontWeight.BOLD,
      margin: '12px 0 4px',
    }}
  >
    {title}
  </div>
);
