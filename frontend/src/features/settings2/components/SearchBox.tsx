// 编辑历史: 2026-09-20 小强 - 新建：搜索框（key/显示名跨分组过滤，高亮并定位到对应 Tab）
// 2026-09-21 小欧 - P0-6：搜索框宽度→settingsControl.searchWidth（[58] P0-6）
// 2026-09-21 小欧 - P1-1：搜索无命中时给出 INFO 提示（[58] P1-1）
import React, { useState } from 'react';
import { Input } from 'antd';
import { settingsControl } from '@/theme/settingsTokens';
import {
  ErrorType,
  showMessage,
} from '@/services/error/handler';
import type { SettingSchemaItem } from '@/services/api/settings.api';
import type { TabKey } from '../types';

interface Props {
  schema: Record<string, { label: string; items: SettingSchemaItem[] }>;
  onJump: (tab: TabKey, key: string) => void;
}

export const SearchBox: React.FC<Props> = ({ schema, onJump }) => {
  const [query, setQuery] = useState('');
  // v4.19(P2-11 修正)：onChange 只记录关键词不做跳转（否则逐字输入即切 Tab 打断输入）；
  // 命中定位只在 onSearch（回车/搜索按钮）触发一次
  const jump = (q: string) => {
    const text = q.trim().toLowerCase();
    if (!text) return;
    for (const [g, grp] of Object.entries(schema)) {
      const hit = grp.items.find(
        (i) => i.key.toLowerCase().includes(text) || i.label.includes(q.trim())
      );
      if (hit) {
        onJump(g as TabKey, hit.key);
        return;
      }
    }
    showMessage(ErrorType.INFO, '未找到匹配的设置项');
  };
  return (
    <Input.Search
      placeholder="搜索设置项 / key..."
      style={{ width: settingsControl.searchWidth }}
      value={query}
      onChange={(e) => setQuery(e.target.value)}
      onSearch={(v) => {
        setQuery(v);
        jump(v);
      }}
    />
  );
};
