// 编辑历史: 2026-11-09 小欧 - 新建：③ Provider 配置区（缺省值兜底 + 放弃修改后重挂载 key）自 SettingsPage 拆出 — 小欧-2026-11-09
import React from 'react';
import type { ModelState } from '../types';
import { ProviderConfig } from './ProviderConfig';

interface Props {
  name: string;
  config?: ModelState['providerConfig'][string];
  /** 放弃修改自增序号：合入 key 令 ProviderConfig 重挂载，按已保存配置重新回显本地输入 */
  resetSeq: number;
  onSave: (patch: {
    api_key?: string;
    api_base?: string;
    label?: string;
    timeout?: number;
    max_retries?: number;
    clear?: boolean;
    [key: string]: unknown;
  }) => Promise<void>;
  onDraftChange: (diff: Record<string, unknown>) => void;
}

export const ModelTabProviderConfig: React.FC<Props> = ({
  name,
  config,
  resetSeq,
  onSave,
  onDraftChange,
}) => (
  <div data-section="provider-config">
    <ProviderConfig
      key={`${name}#${resetSeq}`}
      name={name}
      config={
        config ?? {
          // 掩码契约 {configured, masked}，与 ProviderEntry / ProviderConfig.config / types.ts 同形
          api_key: { configured: false, masked: '' },
          api_base: '',
          label: '',
          timeout: 150, // 缺省 fallback 与后端常量对齐
          max_retries: 3,
          env: false,
        }
      }
      onSave={onSave}
      // 字段 diff 上报：底部保存栏计数/亮起的数据源（空 diff=干净）
      onDraftChange={onDraftChange}
    />
  </div>
);
