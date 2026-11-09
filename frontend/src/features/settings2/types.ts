// 编辑历史: 2026-09-20 小强 - 新建：设置2版类型层（分组/项/模型管理状态）。
// 2026-09-22 小欧 - ModelState 补 paramOptions（下拉数据源）与 providerConfig.label；SettingsState 补 baseline 快照。
// 2026-09-24 小欧 - ModelState 补 removedParams/removedDrafts（键级删除待提交名单与回显快照）。
// 2026-09-27 小欧 - 掩码契约收敛为 {configured, masked}；ModelState 补 providerDraft（③区变更草稿）。
// 2026-10/11 - 键名统一 defaults → baseline、base_url → api_base；能力字段拆 input/output 双维度。
// 2026-11-09 小欧 - 输出模态基线退役（只读展示）；弹窗开关与删除目标属视图态，移交页面本地 state — 小欧-2026-11-09
// 2026-11-09 小欧 - 补 PatchState/PatchModel：拆分后各 hook 共用同一补丁签名 — 小欧-2026-11-09
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
  | 'media'
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
  /**
   * 已保存参数基线（服务端 GET /models 回来的 model_params 副本），供脏判定与「放弃修改」回填；
   * 语义是"已保存值"而非"默认值"，原名 defaults 与 llm.context_length_default 撞名故改名。
   */
  baseline: Record<string, unknown>;
  ranges: Record<string, { min: number; max: number }>;
  paramOptions: Record<string, string[]>;
  // 能力编辑副本与持久化基线（基线不注入，保脏）：输入可编辑，输出只读
  inputModalities: string[];
  inputModalitiesBaseline: string[];
  // 2026-11-09 小欧 - 输出模态只读展示，编辑基线退役（无编辑入口即无脏判定）— 小欧-2026-11-09
  outputModalities: string[];
  envOverride: Record<string, boolean>;
  providerConfig: Record<
    string,
    {
      // 2026-09-27 小欧 - 掩码契约 {configured, masked}（masked 由后端生成，前端纯回显；
      //   与 model.api.ts ProviderEntry / ProviderConfig.config / SettingsPage 兜底值同为一份契约）
      api_key: { configured: boolean; masked: string };
      // 2026-11-01 小欧 - base_url → api_base(与后端 yaml 真源同名) - 小欧-2026-11-01
      api_base: string;
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
  // 弹窗开关与删除目标属视图态，由 SettingsPage 本地 useState 持有（不进领域 state）
  // 参数键级删除待提交名单（baseline 已有键被 × 删除时入列，保存时送 remove_params）
  removedParams: string[];
  // 放弃修改回显快照：× 删除已落盘键时存该键的已保存值/范围/选项，供「放弃修改」逐键回填；
  // 纯内存草稿，放弃/保存/重载任一路即失效
  removedDrafts: Record<
    string,
    { value: unknown; range?: { min: number; max: number }; options?: string[] }
  >;
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

/** 设置区局部补丁（state 浅合并）。 */
export type PatchState = (p: Partial<SettingsState>) => void;

/** 模型区局部补丁，支持函数式更新（保存回写按最新 model 重算脏态）。 */
export type PatchModel = (
  p: Partial<ModelState> | ((m: ModelState) => Partial<ModelState>)
) => void;

/** 保存链统一结果：firstError 为设置项校验失败时的首个出错键。 */
export type SaveResult = { ok: true } | { ok: false; firstError?: string };
