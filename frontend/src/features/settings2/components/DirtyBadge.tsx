// 编辑历史: 2026-09-20 小强 - 新建：全局脏角标"有 N 项未保存"
import React from 'react';
import { Tag } from 'antd';

export const DirtyBadge: React.FC<{ count: number }> = ({ count }) => {
  if (count <= 0) return null;
  return <Tag color="orange">有 {count} 项未保存</Tag>;
};
