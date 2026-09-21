// 编辑历史: 2026-09-20 小强 - 新建：模型选择器（Provider/Model 双下拉联动 + 能力标签 + CRUD 入口）
// 2026-09-21 小欧 - P0-6：下拉宽度→settingsControl 令牌（[58] P0-6）
// 2026-09-21 小欧 - 全文逐章核查：gap/marginTop 裸数字 → Spacing.MD/XS 令牌（[58] v1.12 第七章 铁规）
// 2026-09-21 小欧 - 删掉冗余"当前模型"行（该信息已移至模型Tab ①选择器上方独立显示）
import React from 'react';
import { Button, Select, Tag } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { settingsControl } from '@/theme/settingsTokens';
import { Spacing } from '@/utils/stepStyles';
import type { ProviderEntry } from '@/services/api/model.api';

interface Props {
  providers: ProviderEntry[];
  selectedProvider: string;
  selectedModel: string;
  onSelectProvider: (name: string) => void;
  onSelectModel: (name: string) => void;
  onAddModel: () => void;
  onAddProvider: () => void;
}

export const ModelSelector: React.FC<Props> = ({
  providers,
  selectedProvider,
  selectedModel,
  onSelectProvider,
  onSelectModel,
  onAddModel,
  onAddProvider,
}) => {
  const provider = providers.find((p) => p.name === selectedProvider);
  const current = provider?.models.find((m) => m.name === selectedModel);
  return (
    <div>
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
        <Button icon={<PlusOutlined />} onClick={onAddModel}>
          添加模型
        </Button>
        <Button icon={<PlusOutlined />} onClick={onAddProvider}>
          添加 Provider
        </Button>
      </div>
      <div style={{ marginTop: Spacing.XS }}>
        {(current?.capabilities ?? []).map((c) => (
          <Tag key={c}>{c}</Tag>
        ))}
      </div>
    </div>
  );
};
