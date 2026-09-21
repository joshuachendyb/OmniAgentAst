// 编辑历史: 2026-09-20 小强 - 新建：设置2版类型层（分组/项/模型管理状态，见 6.2）
import type { SessionModelOverride } from '@/types/chat';
import type {
  SettingSchemaItem,
  SettingSource,
} from '@/services/api/settings.api';
import type { ModelEntry, ProviderEntry } from '@/services/api/model.api';

export type { SettingSchemaItem, SettingSource, ModelEntry, ProviderEntry };

export type TabKey =
  | 'general'
  | 'model'
  | 'security'
  | 'chat'
  | 'appearance'
  | 'system';

export interface ModelState {
  providers: ProviderEntry[];
  selectedProvider: string;
  selectedModel: string;
  params: Record<string, unknown>;
  defaults: Record<string, unknown>;
  ranges: Record<string, { min: number; max: number }>;
  envOverride: Record<string, boolean>;
  providerConfig: Record<
    string,
    {
      api_key: { configured: boolean; suffix: string };
      base_url: string;
      timeout: number;
      env: boolean;
    }
  >;
  isDirty: boolean;
  editingProviderConfig: boolean;
  addModelModalOpen: boolean;
  addProviderModalOpen: boolean;
  deleteConfirmOpen: boolean;
  deleteTarget: string | null;
}

export interface SettingsState {
  schema: Record<string, { label: string; items: SettingSchemaItem[] }>;
  values: Record<string, Record<string, unknown>>;
  sources: Record<string, Record<string, SettingSource>>;
  dirtyKeys: Record<string, boolean>;
  mtime: number;
  loading: boolean;
  loadError: string | null;
  activeTab: TabKey;
  model: ModelState;
  currentRef: SessionModelOverride | null;
}
