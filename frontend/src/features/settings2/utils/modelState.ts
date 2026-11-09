// 编辑历史: 2026-11-09 小欧 - 新建：模型区默认态与 providerConfig/envOverride 构建单点（原 useSettings 内联逻辑原样搬迁）— 小欧-2026-11-09
import type { ProviderEntry } from '@/services/api/model.api';
import type { ModelState } from '../types';

// 2026-09-22 小欧 - DRY 收口：load()/refreshModels() 两处 providerConfig 构建完全重复 → 抽公共构建函数
//   api_key/api_base/label/timeout/max_retries/env + 动态参数值（rate_limit 等 param_types 元数据驱动新键，
//   跳过具名键/元数据/列表类，其余标量照抄）；只此一处维护，杜绝改一处漏一处
const DYNAMIC_PROVIDER_SKIP_KEYS = [
  'name',
  'label',
  'api_base',
  'api_key',
  'timeout',
  'max_retries',
  'env',
  'models',
  'param_types',
];

export function buildProviderConfig(
  providers: ProviderEntry[]
): ModelState['providerConfig'] {
  return Object.fromEntries(
    providers.map((p) => [
      p.name,
      {
        api_key: p.api_key,
        api_base: p.api_base,
        label: p.label,
        timeout: p.timeout,
        max_retries: p.max_retries,
        env: p.env, // v4.19：provider 级 env 接管标记（对应 ProviderConfig isEnv），与模型参数 envOverride 分离
        // 2026-09-22 小欧 修遗漏：param_types 元数据未透传 → ProviderConfig 动态渲染区
        //   永远为空（rate_limit 无「速率限制」行）。补透传，E2E-02 实测复现（E2E 浏览器验证）。
        param_types: p.param_types,
        // 动态参数值透传（rate_limit 等）——跳过已具名键 + 元数据 + 列表类，其余标量照抄
        ...Object.fromEntries(
          Object.entries(p as unknown as Record<string, unknown>).filter(
            ([k]) => !DYNAMIC_PROVIDER_SKIP_KEYS.includes(k)
          )
        ),
      },
    ])
  );
}

// 2026-09-22 小欧 - DRY 收口：load/selectProvider/selectModel/refreshModels 四处「env 接管 → 参数键全置禁改」重复 → 单函数
export function getEnvOverride(
  env: boolean | undefined,
  keys: string[]
): Record<string, boolean> {
  return env ? Object.fromEntries(keys.map((k) => [k, true])) : {};
}

export const initialModel = () => ({
  providers: [],
  selectedProvider: '',
  selectedModel: '',
  params: {},
  baseline: {},
  ranges: {},
  paramOptions: {},
  // 2026-09-23 小欧 - 能力编辑副本+基线（load 四通道回填覆盖）
  // 2026-11-08 小欧: capabilities → inputModalities(输入) + outputModalities(输出) 双维度
  inputModalities: [] as string[],
  inputModalitiesBaseline: [] as string[],
  outputModalities: [] as string[],
  envOverride: {},
  providerConfig: {},
  // 2026-09-27 小欧 - ③区草稿初始干净（load 非 keepModel 重建即清；keepModel 由调用方保留）- 小欧-2026-09-27
  providerDraft: {} as Record<string, unknown>,
  isDirty: false,
  // 2026-11-09 小欧 - 弹窗/表单开关等视图态移出领域 state（SettingsPage 本地 useState 持有）— 小欧-2026-11-09
  // 2026-09-24 小欧 - ①参数键级删除待提交名单初始空 — 小欧-2026-09-24
  removedParams: [] as string[],
  // 2026-11-01 小欧 - 放弃修改回显快照初始空（load 非 keepModel 重建即清；类型见 types.ts ModelState）— 小欧-2026-11-01
  removedDrafts: {} as Record<
    string,
    { value: unknown; range?: { min: number; max: number }; options?: string[] }
  >,
});
