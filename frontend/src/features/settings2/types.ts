// 编辑历史: 2026-09-20 小强 - 新建：设置2版类型层（分组/项/模型管理状态，见 6.2）
// 2026-09-21 小欧 - providerConfig 类型补 max_retries（对齐 ProviderConfig 表单 + 后端 GET /models 返回）
// 2026-09-21 小强 - 删死 TabKey 'chat'：后端注册表已整体删除 chat 组（GROUP_ORDER 6 组），前端与之对齐
// 2026-09-22 小强 - SettingsState 增 baseline（纯服务端值快照）：供 S6 改回原值撤销脏标记/S2 load 保留缓冲
// 2026-09-22 小欧 - [62]P3 ModelState 补 paramOptions: Record<string,string[]>（UI 层三选项表，
//   由 useSettings 四通道从 ModelEntry.param_options 透传，参数区枚举下拉数据源）
// 2026-09-22 小欧 - [62]P6 4.3(6)：providerConfig 每条补 label: string（Provider 显示名，
//   后端 GET /models 已返回 p.label，前端无此类型声明则 ProviderConfig 表单/配置区读不到）
// 2026-09-22 小欧 - [62]P8：①4.3(9)-2-c providerConfig 每条加 [key:string]:unknown 动态索引
//   （rate_limit 等 param_types 驱动新参数收容，TS 不透传报 unknown）；②4.3(8) ModelState 补
//   paramOptionsModalOpen 弹窗控制（管理选项入口与重置默认同排）。
// 2026-09-23 小欧 - [65]§七：ModelState 补 capabilities/capabilitiesBaseline（模型能力编辑双字段，编辑副本+基线）- 小欧-2026-09-23
// 2026-09-23 小欧 - [65]§4.1：ModelState 补 addParamFormOpen（「+ 添加参数」内联表单开关）- 小欧-2026-09-23
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
  paramOptions: Record<string, string[]>;
  // 2026-09-23 小欧 - [65]§七：能力编辑副本与持久化基线（baseline 不注入，保脏；[65]7.3.1/7.3.3）
  capabilities: string[];
  capabilitiesBaseline: string[];
  envOverride: Record<string, boolean>;
  providerConfig: Record<
    string,
    {
      api_key: { configured: boolean; suffix: string };
      base_url: string;
      label: string;
      timeout: number;
      max_retries: number;
      env: boolean;
      // 2026-09-22 小欧 - [62]P8 4.3(9)-2-c：动态参数收容（rate_limit 等 param_types 元数据驱动），
      //   否则 TS 对 useSettings 透传动态键报 unknown；ProviderConfig 动态渲染/收集的前提
      [key: string]: unknown;
    }
  >;
  isDirty: boolean;
  editingProviderConfig: boolean;
  addModelModalOpen: boolean;
  addProviderModalOpen: boolean;
  // 2026-09-22 小欧 - [62]P8 4.3(8)：paramOptionsModalOpen 弹窗控制（管理选项入口，与重置默认同排）
  paramOptionsModalOpen: boolean;
  // 2026-09-23 小欧 - [65]§4.1：「+ 添加参数」内联表单开关
  addParamFormOpen: boolean;
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
