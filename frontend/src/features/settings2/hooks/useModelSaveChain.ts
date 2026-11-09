// 编辑历史: 2026-11-09 小欧 - 新建：模型参数/Provider 草稿保存链与切换前强制落库，原 useSettings 保存逻辑原样搬迁 — 小欧-2026-11-09
import {
  useCallback,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import { settingsApi } from '@/services/api/settings.api';
import { modelApi } from '@/services/api/model.api';
import {
  isDirty,
  isCapsDirty,
  normalizeCaps,
  capsForSave,
} from '../utils/modelUtils';
import { buildProviderConfig } from '../utils/modelState';
import {
  ErrorType,
  handleApiError,
  showMessage,
  showSuccess,
} from '@/services/error/handler';
import type { PatchModel, SaveResult, SettingsState } from '../types';

interface ModelSaveChainDeps {
  state: SettingsState;
  patchModel: PatchModel;
  setSaving: Dispatch<SetStateAction<boolean>>;
  mtimeRef: MutableRefObject<number>;
  syncMtime: (mtime: number | undefined | null) => void;
  load: (opts?: { reset?: boolean; keepModel?: boolean }) => Promise<void>;
}

export function useModelSaveChain({
  state,
  patchModel,
  setSaving,
  mtimeRef,
  syncMtime,
  load,
}: ModelSaveChainDeps) {
  // 2026-09-27 小欧 - DRY：getModels + 同步 providers/providerConfig 缓存（原内联在 refreshModels），
  //   saveProviderDraft/refreshModels 共用单点。saveProviderDraft 不直接调 refreshModels 是为避免
  //   循环依赖（refreshModels→ensureModelSaved→saveProviderDraft），只取其中的缓存刷新段 - 小欧-2026-09-27
  const reloadProviderCache = useCallback(async () => {
    try {
      const models = await modelApi.getModels();
      // v4.19 修正：与 load() 同构重建 providerConfig（含 env），防保存/增删后 env 状态过期
      patchModel({
        providers: models.providers,
        providerConfig: buildProviderConfig(models.providers),
      });
      return models;
    } catch (e) {
      handleApiError(e);
      return null;
    }
  }, [patchModel]);

  const saveModelGroup = useCallback(
    async (opts?: { skipMtimeCheck?: boolean }): Promise<SaveResult> => {
      const dirty = isDirty(
        state.model.params,
        state.model.baseline,
        state.model.envOverride
      );
      const changed = Object.fromEntries(
        Object.keys(dirty)
          .filter((k) => dirty[k])
          .map((k) => [k, state.model.params[k]])
      );
      // 2026-09-23 小欧 - 能力脏也算可保存；★空 changed 不带 model_params
      //   （后端 model_params:{} = 显式清空参数块，仅能力变更送 {} 会误清采样参数）
      const capsChanged = isCapsDirty(
        state.model.inputModalities,
        state.model.inputModalitiesBaseline
      );
      // 2026-09-24 小欧 - ①removedParams 也算可保存（仅删无改时 body 不带 model_params，只送 remove_params）
      const hasRemovals = state.model.removedParams.length > 0;
      if (!Object.keys(changed).length && !capsChanged && !hasRemovals)
        return { ok: true };
      // 2026-09-23 小欧 - 新增键形态持久化：新 key 才带全量 ranges/paramOptions 落 model_meta；
      //   无新键时 body 与原来完全一致（零行为变化）
      const prevBaseline = state.model.baseline;
      const newKeys = Object.keys(changed).filter((k) => !(k in prevBaseline));
      const body: {
        model_params?: Record<string, unknown>;
        range?: Record<string, { min: number; max: number }>;
        param_options?: Record<string, string[]>;
        // 2026-11-08 小欧: capabilities → input/output 双维度
        input_modalities?: string[];
        // 2026-09-24 小欧 - ①键级删除名单（与 model_params merge 叠加，后端先删再 merge）- 小欧-2026-09-24
        remove_params?: string[];
      } = {};
      if (hasRemovals) body.remove_params = [...state.model.removedParams];
      if (Object.keys(changed).length) {
        body.model_params = changed;
        if (newKeys.length) {
          // 2026-11-01 小欧 - 形态信封收口：只随新键捎带其自身 range/param_options。
          //   原全量 {...state.model.ranges}/{...paramOptions} 会把已放弃未保存键的形态
          //   押车落 model_meta（界面上不存在的键的元数据真落盘实证）。空 map 不挂字段：
          //   挂空块会触发后端整块替换语义，误清既有其他键的形态 - 小欧-2026-11-01
          const rangeNew: Record<string, { min: number; max: number }> = {};
          const optNew: Record<string, string[]> = {};
          for (const k of newKeys) {
            const r = state.model.ranges[k];
            if (r) rangeNew[k] = r;
            const o = state.model.paramOptions[k];
            if (o && o.length) optNew[k] = o;
          }
          if (Object.keys(rangeNew).length) body.range = rangeNew;
          if (Object.keys(optNew).length) body.param_options = optNew;
        }
      }
      // 2026-09-24 小欧 - ②capabilities 送保存态 capsForSave：无增强→[]、有增强→['text',...extras]
      //   （state 恒含 text，直接送会让纯文本模型落 ['text'] 而非隐含默认的空）- 小欧-2026-09-24
      // 2026-11-09 小欧: 输出模态改只读徽标, body 只送 input_modalities(撤 output 提交: 无编辑入口后
      //   回写=无意义写入), 后端对缺省键不整块替换, 既有 output_modalities 保真不动 — 小欧-2026-11-09
      if (capsChanged) {
        body.input_modalities = capsForSave(state.model.inputModalities);
      }
      setSaving(true);
      try {
        // 保存前校验 mtime（模型参数与设置同落 YAML），外部已更新则刷新并中止；skipMtimeCheck 语义同 saveKeys
        if (!opts?.skipMtimeCheck) {
          const curMtime = await settingsApi.getMtime();
          if (curMtime !== state.mtime) {
            await load({ reset: true });
            showMessage(
              ErrorType.WARNING,
              '配置已被外部更新，已重新加载，请核对后重新保存'
            );
            return { ok: false };
          }
        }
        // 模型参数写 ai.{provider}.model_params.{model}.{key}（运行时 parse_model_params 消费），
        //   经 PUT /models/{provider}/{model} 的 model_params 通道，不走 /settings 裸 key（registry 无此 key 会保存失败）
        const r = await modelApi.updateModel(
          state.model.selectedProvider,
          state.model.selectedModel,
          body
        );
        if (!r.ok) {
          showMessage(ErrorType.MODEL_CONFIG_ERROR, '模型参数保存失败');
          return { ok: false };
        }
        showSuccess('模型参数已保存');
        // providers 缓存同步回写 capabilities/model_params/range/param_options 与保存态基线
        //   （否则 selectModel 切回读 entry 得旧值，参数区与通用 Tab tags 两处不同源显示失真）。
        const capsSaved = capsForSave(state.model.inputModalities);
        // 函数式更新：baseline 存本次实际提交的那份 params（用新值当基线等于把未保存编辑当成已保存），
        //   但 isDirty 按最新 params 重算——请求在飞期间的新编辑不会被硬置 false 吞成隐形脏。
        patchModel((m) => ({
          baseline: { ...state.model.params },
          inputModalitiesBaseline: normalizeCaps([
            ...state.model.inputModalities,
          ]),
          removedParams: [],
          // 删除键已真落盘，放弃修改回显快照同步清空，不留死亡数据 - 小欧-2026-11-01
          removedDrafts: {},
          providers: state.model.providers.map((p) =>
            p.name !== state.model.selectedProvider
              ? p
              : {
                  ...p,
                  models: p.models.map((m) =>
                    m.name !== state.model.selectedModel
                      ? m
                      : {
                          ...m,
                          model_params: { ...state.model.params },
                          range: { ...state.model.ranges },
                          param_options: { ...state.model.paramOptions },
                          // 2026-11-09 小欧: 只回写 input(输出模态本页只读, 保存行为不改产物) — 小欧-2026-11-09
                          input_modalities: capsSaved,
                        }
                  ),
                }
          ),
          isDirty: Object.values(
            isDirty(m.params, { ...state.model.params }, m.envOverride)
          ).some(Boolean),
        }));
        // 同步落盘后 mtime，防假后门刷新误判
        syncMtime(r.mtime);
        return { ok: true };
      } catch (e) {
        handleApiError(e);
        return { ok: false };
      } finally {
        setSaving(false);
      }
    },
    [patchModel, syncMtime, state.model, state.mtime, load, setSaving]
  );

  // ③区草稿落盘（统一保存链）：patch=③自带按钮提交的全量表单值，缺省=底部保存栏提交的草稿 diff；
  //   两入口同一链，成功 → 同步 mtime + 刷新 provider 缓存 + 清草稿，失败保留草稿（保存栏仍亮，可改后重试） - 小欧-2026-09-27
  const saveProviderDraft = useCallback(
    async (patch?: Record<string, unknown>): Promise<SaveResult> => {
      const draft = patch ?? state.model.providerDraft;
      if (!Object.keys(draft).length) return { ok: true };
      // api_base 为空是错误态（组件内按钮已 disabled 并红字标注），但草稿会带 api_base:'' 走底部保存栏进来，
      //   无校验直接 PUT 会落盘空地址致该 Provider 全部调用失败；校验下沉到此处，组件按钮与底栏两处同源（DRY）。
      if ('api_base' in draft && !String(draft.api_base ?? '').trim()) {
        showMessage(
          ErrorType.VALIDATE_CONFIG_FAILED,
          'API 地址不能为空，请填写后再保存'
        );
        return { ok: false };
      }
      setSaving(true);
      try {
        // 2026-11-01 小欧 - mtime 外改守卫补齐：Provider 配置同落 config.yaml，与 saveKeys/
        //   saveModelGroup 同机制（同一次外部改动差分实证：模型路拦停+告警，本路静默覆写落盘）。
        //   外部已更新则刷新+提示并中止；比对读 mtimeRef（编排链旧闭包读 state.mtime 必得旧值）；
        //   同链前一路（saveKeys/saveModelGroup）成功已 syncMtime，自写不会自误判 - 小欧-2026-11-01
        const curMtime = await settingsApi.getMtime();
        if (curMtime !== mtimeRef.current) {
          await load({ reset: true });
          showMessage(
            ErrorType.WARNING,
            '配置已被外部更新，已重新加载，请核对后重新保存'
          );
          return { ok: false };
        }
        const r = await modelApi.updateProvider(
          state.model.selectedProvider,
          draft
        );
        if (!r.ok) {
          showMessage(ErrorType.MODEL_CONFIG_ERROR, 'Provider 配置保存失败');
          return { ok: false };
        }
        showSuccess('Provider 配置已保存（立即生效）');
        // 同步落盘后 mtime，防假后门刷新误判
        syncMtime(r.mtime);
        // 缓存刷新（掩码/label/timeout 回读）+ 草稿清空（保存栏计数归零）
        await reloadProviderCache();
        patchModel({ providerDraft: {} });
        return { ok: true };
      } catch (e) {
        handleApiError(e);
        return { ok: false };
      } finally {
        setSaving(false);
      }
    },
    [
      state.model.providerDraft,
      state.model.selectedProvider,
      syncMtime,
      reloadProviderCache,
      patchModel,
      load,
      setSaving,
      mtimeRef,
    ]
  );

  // 跨模型/Provider 切换前强制保存未落库的模型参数，
  // 杜绝真实场景（agnes 空 dp <-> sensenova 有 dp）切换后参数静默丢失；保存失败则阻止切换。
  const ensureModelSaved = useCallback(async (): Promise<boolean> => {
    const dirtyMap = isDirty(
      state.model.params,
      state.model.baseline,
      state.model.envOverride
    );
    // 放行条件覆盖能力脏/删键意图/providerDraft（各自未存就切换会静默丢失）；
    //   hadParams 单列是为了只在参数/能力真保存过时才弹参数保存提示，防误导文案。
    const hadParams =
      Object.values(dirtyMap).some(Boolean) ||
      // 2026-11-09 小欧: 输出模态改只读, 保存前脏判定只看输入模态 — 小欧-2026-11-09
      isCapsDirty(
        state.model.inputModalities,
        state.model.inputModalitiesBaseline
      ) ||
      state.model.removedParams.length > 0;
    const hasDraft = Object.keys(state.model.providerDraft).length > 0;
    if (!hadParams && !hasDraft) return true;
    const r = await saveModelGroup();
    if (!r.ok) {
      showMessage(
        ErrorType.MODEL_CONFIG_ERROR,
        '模型参数保存失败，已阻止切换（防止数据丢失）'
      );
      return false;
    }
    if (hasDraft) {
      const p = await saveProviderDraft();
      if (!p.ok) {
        showMessage(
          ErrorType.MODEL_CONFIG_ERROR,
          'Provider 配置保存失败，已阻止切换（防止数据丢失）'
        );
        return false;
      }
    }
    if (hadParams) showMessage(ErrorType.INFO, '已保存当前模型参数修改');
    return true;
  }, [saveModelGroup, saveProviderDraft, state.model]);

  return {
    reloadProviderCache,
    saveModelGroup,
    saveProviderDraft,
    ensureModelSaved,
  };
}
