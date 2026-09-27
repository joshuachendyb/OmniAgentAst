// 编辑历史: 2026-09-20 小强 - 新建：设置2版类型层（分组/项/模型管理状态，见 6.2）
// 2026-09-21 小欧 - providerConfig 类型补 max_retries（对齐 ProviderConfig 表单 + 后端 GET /models 返回）
// 2026-09-21 小强 - 删死 TabKey 'chat'：后端注册表已整体删除 chat 组（GROUP_ORDER 6 组），前端与之对齐
// 2026-09-22 小强 - SettingsState 增 baseline（纯服务端值快照）：供 S6 改回原值撤销脏标记/S2 load 保留缓冲
// 2026-09-22 小欧 - 实施 ModelState 补 paramOptions: Record<string,string[]>（UI 层三选项表，
//   由 useSettings 四通道从 ModelEntry.param_options 透传，参数区枚举下拉数据源）
// 2026-09-22 小欧 - 实施：providerConfig 每条补 label: string（Provider 显示名，
//   后端 GET /models 已返回 p.label，前端无此类型声明则 ProviderConfig 表单/配置区读不到）
// 2026-09-22 小欧 - 实施：①providerConfig 每条加 [key:string]:unknown 动态索引
//   （rate_limit 等 param_types 驱动新参数收容，TS 不透传报 unknown）；②4.3(8) ModelState 补
//   paramOptionsModalOpen 弹窗控制（管理选项入口与重置默认同排）。
// 2026-09-23 小欧 - 实施：ModelState 补 capabilities/capabilitiesBaseline（模型能力编辑双字段，编辑副本+基线）- 小欧-2026-09-23
// 2026-09-23 小欧 - 实施：ModelState 补 addParamFormOpen（「+ 添加参数」内联表单开关）- 小欧-2026-09-23
// 2026-09-24 小欧 - 参数键级删除：ModelState 补 removedParams: string[]（②参数行 × 删除待落盘键名单，
//   saveModelGroup 经 remove_params 通道提交；仅 defaults 已有键才入名单，未保存新键删除直接丢弃）- 小欧-2026-09-24
// 2026-09-24 小欧 - 模型库：TabKey 补 'model_library'（设置页倒数第二 Tab，对齐后端 GROUP_ORDER）- 小欧-2026-09-24
// 2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}（masked 由后端一次生成，前端纯回显）：
//   本契约在项目内有 5 处声明：model.api.ts ProviderEntry / config.api.ts ProviderInfo /
//   ProviderConfig.config / SettingsPage 兜底值 / 本文件（另有 settings.api.ts getTokenStatus 的
//   masked 为同一形状）。缺任一处 tsc 即报 masked 缺失 — 小欧-2026-09-27
// 2026-09-27 小欧 - ③ Provider 配置改后底部保存栏亮起（北京老陈需求）：ModelState 补
//   providerDraft: Record<string, unknown> —— ③区表单字段的变更草稿（只含改过的键，空对象=干净），
//   由 ProviderConfig 经 onDraftChange 上报 diff，dirtyCount/isGroupDirty/saveGroup/saveAll/
//   ensureModelSaved/beforeunload/checkMtime 全链纳入；保存经 saveProviderDraft → PUT /providers 落盘 - 小欧-2026-09-27
import type { SessionModelOverride } from '@/types/chat';
import type {
  SettingSchemaItem,
  SettingSource,
} from '@/services/api/settings.api';
import type { ModelEntry, ProviderEntry } from '@/services/api/model.api';

export type { SettingSchemaItem, SettingSource, ModelEntry, ProviderEntry };

// 2026-09-22 小欧 - tuning Tab 类型补齐：TabKey 加 'tuning'
export type TabKey =
  | 'general'
  | 'model'
  | 'security'
  | 'appearance'
  | 'system'
  | 'sandbox'
  | 'tuning'
  | 'model_library';

export interface ModelState {
  providers: ProviderEntry[];
  selectedProvider: string;
  selectedModel: string;
  params: Record<string, unknown>;
  defaults: Record<string, unknown>;
  ranges: Record<string, { min: number; max: number }>;
  paramOptions: Record<string, string[]>;
  // 2026-09-23 小欧 - 实施：能力编辑副本与持久化基线（baseline 不注入，保脏）
  capabilities: string[];
  capabilitiesBaseline: string[];
  envOverride: Record<string, boolean>;
  providerConfig: Record<
    string,
    {
      // 2026-09-27 小欧 - 掩码契约 {configured, masked}（masked 由后端生成，前端纯回显；
      //   与 model.api.ts ProviderEntry / ProviderConfig.config / SettingsPage 兜底值同为一份契约）
      api_key: { configured: boolean; masked: string };
      base_url: string;
      label: string;
      timeout: number;
      max_retries: number;
      env: boolean;
      // 2026-09-22 小欧 - 实施：动态参数收容（rate_limit 等 param_types 元数据驱动），
      //   否则 TS 对 useSettings 透传动态键报 unknown；ProviderConfig 动态渲染/收集的前提
      [key: string]: unknown;
    }
  >;
  // 2026-09-27 小欧 - ③区字段变更草稿（只含改过的键；空=干净）——底部保存栏计数/落盘源 - 小欧-2026-09-27
  providerDraft: Record<string, unknown>;
  isDirty: boolean;
  editingProviderConfig: boolean;
  addModelModalOpen: boolean;
  addProviderModalOpen: boolean;
  // 2026-09-22 小欧 - 实施：paramOptionsModalOpen 弹窗控制（管理选项入口，与重置默认同排）
  paramOptionsModalOpen: boolean;
  // 2026-09-23 小欧 - 实施：「+ 添加参数」内联表单开关
  addParamFormOpen: boolean;
  // 2026-09-24 小欧 - 参数键级删除待提交名单（defaults 已有键被 × 删除时入列，保存时送 remove_params）- 小欧-2026-09-24
  removedParams: string[];
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
