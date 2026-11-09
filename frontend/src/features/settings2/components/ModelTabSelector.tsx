// 编辑历史: 2026-11-09 小欧 - 新建：① 选择器区块（标题行 + 添加入口 + 双下拉）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import { Button } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { Spacing } from '@/utils/stepStyles';
import { settingsControl } from '@/theme/settingsTokens';
import type { ProviderEntry } from '@/services/api/model.api';
import { SectionTitle } from './SectionTitle';
import { ModelSelector } from './ModelSelector';

interface Props {
  providers: ProviderEntry[];
  selectedProvider: string;
  selectedModel: string;
  onSelectProvider: (name: string) => void;
  onSelectModel: (name: string) => void;
  onAddModel: () => void;
  onAddProvider: () => void;
}

export const ModelTabSelector: React.FC<Props> = ({
  providers,
  selectedProvider,
  selectedModel,
  onSelectProvider,
  onSelectModel,
  onAddModel,
  onAddProvider,
}) => (
  <div data-section="selector">
    {/* ①标题行 = 三列 grid：标题左列 | 按钮组中列左对齐 | 右列空 — ①②③统一布局 */}
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr',
        alignItems: 'center',
      }}
    >
      <SectionTitle title="── ① 选择器 ──" />
      <div style={{ display: 'flex', gap: Spacing.SM, justifySelf: 'start' }}>
        <Button
          icon={<PlusOutlined />}
          style={{ width: settingsControl.actionBtnWidth }}
          onClick={onAddModel}
        >
          添加模型
        </Button>
        <Button
          icon={<PlusOutlined />}
          style={{ width: settingsControl.actionBtnWidth }}
          onClick={onAddProvider}
        >
          添加 Provider
        </Button>
      </div>
    </div>
    <ModelSelector
      providers={providers}
      selectedProvider={selectedProvider}
      selectedModel={selectedModel}
      onSelectProvider={onSelectProvider}
      onSelectModel={onSelectModel}
    />
  </div>
);
