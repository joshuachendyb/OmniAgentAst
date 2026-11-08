// 编辑历史: 2026-09-20 小强 - 新建：模型选择器（Provider/Model 双下拉联动 + 能力标签 + CRUD 入口）
// 2026-09-21 小欧 - 实施：下拉宽度→settingsControl 令牌
// 2026-09-21 小欧 - 全文核查：gap/marginTop 裸数字 → Spacing.MD/XS 令牌（设计文档 v1.12 铁规）
// 2026-09-21 小欧 - 删掉冗余"当前模型"行（该信息已移至模型Tab ①选择器上方独立显示）
// 2026-11-08 小欧 - 布局优化：添加模型/Provider 按钮上移至①标题行（SettingsPage grid 居中，与②同款）；
//   能力标签从独立行并入下拉行（原按钮位置），消除垂直冗余行
import React from 'react';
import { Select, Tag } from 'antd';
import { settingsControl } from '@/theme/settingsTokens';
import { Spacing } from '@/utils/stepStyles';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  providers: ProviderEntry[];
  selectedProvider: string;
  selectedModel: string;
  onSelectProvider: (name: string) => void;
  onSelectModel: (name: string) => void;
}

export const ModelSelector: React.FC<Props> = ({
  providers,
  selectedProvider,
  selectedModel,
  onSelectProvider,
  onSelectModel,
}) => {
  const provider = providers.find((p) => p.name === selectedProvider);
  const current = provider?.models.find((m) => m.name === selectedModel);
  return (
    <div style={{ display: 'flex', gap: Spacing.MD, alignItems: 'center' }}>
      <Select
        value={selectedProvider}
        style={{ width: settingsControl.modelSelectWidth }}
        onChange={onSelectProvider}
      >
        {providers.map((p) => (
          <Select.Option key={p.name} value={p.name}>
            {p.label || p.name}
          </Select.Option>
        ))}
      </Select>
      <Select
        value={selectedModel}
        style={{ width: settingsControl.modelNameWidth }}
        onChange={onSelectModel}
      >
        {(provider?.models ?? []).map((m) => (
          <Select.Option key={m.name} value={m.name}>
            {m.label || m.name}
          </Select.Option>
        ))}
      </Select>
      {/* 2026-11-08 小欧 [14] F4: 输入能力 tags → input_modalities；有生图/生视频补"生成"徽标 */}
      {(current?.input_modalities ?? []).map((c) => (
        <Tag key={c}>{c}</Tag>
      ))}
      {(current?.output_modalities ?? []).map((c) => (
        <Tag key={`out-${c}`} color="orange">
          {c === 'image' ? '图片生成' : c === 'video' ? '视频生成' : c}
        </Tag>
      ))}
    </div>
  );
};
