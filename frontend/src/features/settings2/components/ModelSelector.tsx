// 编辑历史: 2026-09-20 小强 - 新建：模型选择器（Provider/Model 双下拉联动 + 能力标签 + CRUD 入口）
import React from 'react';
import { Button, Select, Tag } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
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
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <Select
          value={selectedProvider}
          style={{ width: 200 }}
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
          style={{ width: 240 }}
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
      <div style={{ marginTop: 8 }}>
        当前模型：{selectedModel}（{selectedProvider}）
      </div>
      <div style={{ marginTop: 4 }}>
        {(current?.capabilities ?? []).map((c) => (
          <Tag key={c}>{c}</Tag>
        ))}
      </div>
    </div>
  );
};
