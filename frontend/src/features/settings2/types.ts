// 编辑历史: 2026-09-20 小强 - 新建：设置2版类型层（分组/项/模型管理状态，见 6.2）
// 2026-09-21 小欧 - providerConfig 类型补 max_retries（对齐 ProviderConfig 表单 + 后端 GET /models 返回）
// 2026-09-21 小强 - 删死 TabKey 'chat'：后端注册表已整体删除 chat 组（GROUP_ORDER 6 组），前端与之对齐
// 2026-09-22 小强 - SettingsState 增 baseline（纯服务端值快照）：供 S6 改回原值撤销脏标记/S2 load 保留缓冲
import type { SessionModelOverride } from '@/types/chat';
import type {
  SettingSchemaItem,
  SettingSource,
} from '@/services/api/settings.api';
import type { ModelEntry, ProviderEntry } from '@/services/api/model.api';

export type { SettingSchemaItem, SettingSource, ModelEntry, ProviderEntry };

// 2026-09-22 小欧 - [61] tuning Tab 类型补齐：TabKey 加 'tuning'
export type TabKey =
  | 'general'
  | 'model'
  | 'security'
  | 'appearance'
  | 'system'
  | 'sandbox'
  | 'tuning';

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
      max_retries: number;
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
  baseline: Record<string, Record<string, unknown>>;
  sources: Record<string, Record<string, SettingSource>>;
  dirtyKeys: Record<string, boolean>;
  mtime: number;
  loading: boolean;
  loadError: string | null;
  activeTab: TabKey;
  model: ModelState;
  currentRef: SessionModelOverride | null;
}
