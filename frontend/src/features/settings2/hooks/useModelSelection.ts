// 编辑历史: 2026-11-09 小欧 - 新建：Provider/模型切换与刷新定位（切换前强制落库），原 useSettings 逻辑原样搬迁 — 小欧-2026-11-09
import { useCallback } from 'react';
import type { ModelsResponse } from '@/services/api/model.api';
import { normalizeCaps, withDeclaredMeta } from '../utils/modelUtils';
import { getEnvOverride } from '../utils/modelState';
import { ErrorType, showMessage } from '@/services/error/handler';
import type { PatchModel, SettingsState } from '../types';

interface ModelSelectionDeps {
  state: SettingsState;
  patchModel: PatchModel;
  ensureModelSaved: () => Promise<boolean>;
  reloadProviderCache: () => Promise<ModelsResponse | null>;
}

export function useModelSelection({
  state,
  patchModel,
  ensureModelSaved,
  reloadProviderCache,
}: ModelSelectionDeps) {
  const selectProvider = useCallback(
    async (name: string) => {
      // 无此 Provider / 无模型的 Provider 给明确提示（原静默 return 无任何反馈）
      const p = state.model.providers.find((x) => x.name === name);
      if (!p) {
        showMessage(ErrorType.WARNING, `Provider「${name}」不存在`);
        return;
      }
      const first = p.models[0];
      if (!first) {
        showMessage(
          ErrorType.WARNING,
          `Provider「${name}」暂无模型，请先在①选择器添加模型`
        );
        return;
      }
      // 修复：先保存未落库参数，再改焦点，防切换后参数静默丢失/数据不一致
      if (!(await ensureModelSaved())) return;
      // 2026-09-21 小欧 解耦：①选择器 = 参数编辑焦点（纯前端），只切 selectedProvider/selectedModel
      //   + 参数区联动；不再写 ai.model_ref——全局生效模型唯一入口=通用Tab CurrentModelRefCard→ModelSwitchModal
      // 2026-11-01 小欧 - withDeclaredMeta: 基线补厂商声明窗口与输出上限(用户值优先, 只缺才补) — 小欧-2026-11-01
      const baseline = withDeclaredMeta(
        (first?.model_params ?? {}) as Record<string, unknown>,
        first?.context_length,
        first?.max_output_length
      );
      patchModel({
        selectedProvider: name,
        selectedModel: first?.name ?? '',
        params: baseline,
        baseline,
        ranges: {
          ...((first?.range ?? {}) as Record<
            string,
            { min: number; max: number }
          >),
        },
        paramOptions: {
          ...((first?.param_options ?? {}) as Record<string, string[]>),
        },
        // selectProvider 通道：normalizeCaps 归一（恒含 text 防假脏）；能力拆 input/output 双维度
        inputModalities: normalizeCaps([...(first?.input_modalities ?? [])]),
        inputModalitiesBaseline: normalizeCaps([
          ...(first?.input_modalities ?? []),
        ]),
        outputModalities: [...(first?.output_modalities ?? [])],
        // 切到 env 接管 provider 时参数区整体禁用（后端拒保存）；键集取 baseline（含厂商声明窗口注入行），四通道同源
        envOverride: getEnvOverride(p.env, Object.keys(baseline)),
        // 2026-09-24 小欧 - ①切 Provider 重置删除名单（已随 ensureModelSaved 落库）- 小欧-2026-09-24
        removedParams: [],
        isDirty: false,
      });
    },
    [patchModel, state.model.providers, ensureModelSaved]
  );

  const selectModel = useCallback(
    async (name: string) => {
      const entry = state.model.providers
        .find((x) => x.name === state.model.selectedProvider)
        ?.models.find((m) => m.name === name);
      if (!entry) return;
      // 修复：先保存未落库参数，再改焦点，防切换时参数静默丢失
      if (!(await ensureModelSaved())) return;
      // 2026-09-21 小欧 解耦：同 selectProvider，只切前端焦点，不再写 ai.model_ref
      // 2026-11-01 小欧 - withDeclaredMeta: 基线补厂商声明窗口与输出上限(用户值优先, 只缺才补) — 小欧-2026-11-01
      const nextBaseline = withDeclaredMeta(
        { ...entry.model_params } as Record<string, unknown>,
        entry.context_length,
        entry.max_output_length
      );
      const nextRanges = { ...(entry.range ?? {}) } as Record<
        string,
        { min: number; max: number }
      >;
      const nextOptions = { ...(entry.param_options ?? {}) } as Record<
        string,
        string[]
      >;
      // 参数已随 ensureModelSaved 落库，新模型按已保存值展示，无残留脏态/幽灵参数
      const providerEntry = state.model.providers.find(
        (x) => x.name === state.model.selectedProvider
      );
      patchModel({
        selectedModel: name,
        params: { ...nextBaseline },
        baseline: nextBaseline,
        ranges: nextRanges,
        paramOptions: nextOptions,
        // 2026-09-24 小欧 - ②selectModel 通道：normalizeCaps 归一（恒含 text 防假脏）- 小欧-2026-09-24
        // 2026-11-08 小欧: capabilities→input/output 双维度
        inputModalities: normalizeCaps([...(entry.input_modalities ?? [])]),
        inputModalitiesBaseline: normalizeCaps([
          ...(entry.input_modalities ?? []),
        ]),
        outputModalities: [...(entry.output_modalities ?? [])],
        // 选中 provider 为 env 接管时同步禁用其参数区
        envOverride: getEnvOverride(
          providerEntry?.env,
          Object.keys(nextBaseline)
        ),
        // 切模型重置删除名单与回显快照（前者已随 ensureModelSaved 落库，后者是 A 模型的死亡数据）- 小欧-2026-11-01
        removedParams: [],
        removedDrafts: {},
        // 2026-11-01 小欧 - 原 isDirty({...baseline}, baseline, ...) 恒为 false（比的就是同一份基线），
        //   死计算删除；切模型后无未保存编辑，与 selectProvider/refreshModels 通道同值 — 小欧-2026-11-01
        isDirty: false,
      });
    },
    [patchModel, state.model, ensureModelSaved]
  );

  const refreshModels = useCallback(
    async (select?: { provider: string; model: string }) => {
      // 带 select 的刷新（添加模型后定位）若当前参数未落库，先强制保存——与 selectProvider/selectModel
      //   同一防线，杜绝切到新模型时旧模型未保存参数静默丢失
      if (select && !(await ensureModelSaved())) return null;
      // 2026-09-27 小欧 - 缓存刷新段收口到 reloadProviderCache（DRY，与 saveProviderDraft 共用；失败已在内
      //   handleApiError 并返回 null）- 小欧-2026-09-27
      const models = await reloadProviderCache();
      if (!models) return null;
      if (select) {
        const p = models.providers.find((x) => x.name === select.provider);
        const m = p?.models.find((x) => x.name === select.model);
        if (p && m) {
          // 2026-11-01 小欧 - 键名统一 default_params → model_params；withDeclaredMeta 补声明窗口与输出上限 — 小欧-2026-11-01
          const baseline = withDeclaredMeta(
            (m.model_params ?? {}) as Record<string, unknown>,
            m.context_length,
            m.max_output_length
          );
          patchModel({
            selectedProvider: p.name,
            selectedModel: m.name,
            params: { ...baseline },
            baseline,
            ranges: {
              ...(m.range as Record<string, { min: number; max: number }>),
            },
            paramOptions: {
              ...((m.param_options ?? {}) as Record<string, string[]>),
            },
            // 2026-09-24 小欧 - ②refreshModels(select) 通道：normalizeCaps 归一（恒含 text 防假脏）- 小欧-2026-09-24
            // 2026-11-08 小欧: capabilities→input/output 双维度
            inputModalities: normalizeCaps([...(m.input_modalities ?? [])]),
            inputModalitiesBaseline: normalizeCaps([
              ...(m.input_modalities ?? []),
            ]),
            outputModalities: [...(m.output_modalities ?? [])],
            // 目标 provider env 接管时禁用其参数区
            envOverride: getEnvOverride(p.env, Object.keys(baseline)),
            // 定位重置删除名单（已随 ensureModelSaved 落库）
            removedParams: [],
            isDirty: false,
          });
        }
      }
      return models;
    },
    [patchModel, ensureModelSaved, reloadProviderCache]
  );

  return { selectProvider, selectModel, refreshModels };
}
