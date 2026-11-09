// 编辑历史: 2026-11-09 小欧 - 新建：首次加载与 mtime 外改检查（原 useSettings 内联 load/checkMtime 原样搬迁）— 小欧-2026-11-09
import {
  useCallback,
  useEffect,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import { settingsApi } from '@/services/api/settings.api';
import { modelApi } from '@/services/api/model.api';
import { normalizeCaps, withDeclaredMeta } from '../utils/modelUtils';
import {
  buildProviderConfig,
  getEnvOverride,
  initialModel,
} from '../utils/modelState';
import {
  ErrorType,
  handleApiError,
  showMessage,
} from '@/services/error/handler';
import type { PatchState, SettingsState } from '../types';

interface LoadDeps {
  state: SettingsState;
  setState: Dispatch<SetStateAction<SettingsState>>;
  patchState: PatchState;
  mtimeRef: MutableRefObject<number>;
}

export function useSettingsLoad({
  state,
  setState,
  patchState,
  mtimeRef,
}: LoadDeps) {
  /** 首次加载：schema + 全量值 + 模型列表一次拉取。 */
  // 默认（非 reset）且存在未保存修改时保留 dirtyKeys 与脏键缓冲值，杜绝 onModelSwitched（切全局模型 → load）静默丢脏；
  //   checkMtime 守卫显式传 {reset:true} 才全量重置；同时回填 baseline 快照与模型区 envOverride。
  const load = useCallback(
    // keepModel：只刷新设置区（schema/values/sources/baseline/mtime），原样保留模型区
    //   （secret 行落盘后需重拉刷新掩码，无条件重建模型区会静默丢弃未保存的参数/能力/provider 编辑）。
    async (opts?: { reset?: boolean; keepModel?: boolean }) => {
      patchState({ loading: true, loadError: null });
      try {
        const [schema, all, models] = await Promise.all([
          settingsApi.getSchema(),
          settingsApi.getAll(),
          modelApi.getModels(),
        ]);
        const serverValues = all.groups
          ? Object.fromEntries(
              Object.entries(all.groups).map(([g, v]) => [g, { ...v.data }])
            )
          : {};
        const serverSources = all.groups
          ? Object.fromEntries(
              Object.entries(all.groups).map(([g, v]) => [g, { ...v.sources }])
            )
          : {};
        const keyToGroup = new Map<string, string>();
        for (const [g, grp] of Object.entries(schema.groups ?? {})) {
          for (const it of grp.items ?? []) keyToGroup.set(it.key, g);
        }
        // v4.19 修正：正常加载不再用 localStorage prefs 覆盖 values——后端 YAML 是唯一真相源，
        // local prefs 只承载"后端不可达时的本地试玩草稿"（7.6③），若潜伏自定义值遮蔽 YAML 会误导保存；
        // 后端不可达（本 try 已抛错走到 catch）时 values 保持未初始化，外观 Tab 本地模式另行消费 prefs。
        const ref = models.current_model_ref ?? null;
        const provider =
          models.providers.find((p) => p.name === ref?.provider) ??
          models.providers[0];
        const current =
          provider?.models.find((m) => m.name === (ref?.model ?? '')) ??
          provider?.models[0];
        // 2026-11-01 小欧 - withDeclaredMeta: 基线补厂商声明窗口与输出上限(用户值优先, 只缺才补) — 小欧-2026-11-01
        const baseline = withDeclaredMeta(
          (current?.model_params ?? {}) as Record<string, unknown>,
          current?.context_length,
          current?.max_output_length
        );
        const providerConfig = buildProviderConfig(models.providers);
        // provider 由 {NAME}_API_KEY 环境变量接管时（后端 update_model/update_provider_config
        //   均 _raise_if_env_takeover 拒绝），其模型参数保存必败 → 参数区整体标记 envOverride 禁用。
        // 2026-11-01 小欧 - 键集与另三通道同源改取 baseline：基线含厂商声明窗口注入行，
        //   若仍按 model_params 取键，env 接管时注入行不会标禁改（四通道口径不一） — 小欧-2026-11-01
        const envOverride = getEnvOverride(
          provider?.env,
          Object.keys(baseline)
        );
        setState((s) => {
          const resetAll = opts?.reset ?? false;
          const preserve = !resetAll && Object.keys(s.dirtyKeys).length > 0;
          const values = preserve
            ? (() => {
                const merged: Record<string, Record<string, unknown>> = {};
                for (const [g, data] of Object.entries(serverValues)) {
                  merged[g] = { ...data };
                }
                for (const key of Object.keys(s.dirtyKeys)) {
                  const g = keyToGroup.get(key);
                  if (!g) continue;
                  const buffered = s.values[g]?.[key];
                  if (buffered !== undefined) {
                    merged[g] = { ...(merged[g] ?? {}), [key]: buffered };
                  }
                }
                return merged;
              })()
            : serverValues;
          return {
            ...s,
            schema: schema.groups,
            values,
            sources: serverSources,
            baseline: serverValues,
            dirtyKeys: preserve ? { ...s.dirtyKeys } : {},
            mtime: all.mtime,
            loading: false,
            currentRef: ref,
            // keepModel 时保留模型区全部未保存编辑（详见 load 的 docstring）
            model: opts?.keepModel
              ? s.model
              : {
                  ...initialModel(),
                  providers: models.providers,
                  selectedProvider: provider?.name ?? '',
                  selectedModel: current?.name ?? '',
                  params: { ...baseline },
                  baseline,
                  ranges: {
                    ...((current?.range ?? {}) as Record<
                      string,
                      { min: number; max: number }
                    >),
                  },
                  paramOptions: {
                    ...((current?.param_options ?? {}) as Record<
                      string,
                      string[]
                    >),
                  },
                  // 2026-09-24 小欧 - ②load 通道：normalizeCaps 归一（恒含 text 防假脏；未知值原样保留）- 小欧-2026-09-24
                  // 2026-11-08 小欧: capabilities→inputModalities + 增 outputModalities 双维度
                  inputModalities: normalizeCaps([
                    ...(current?.input_modalities ?? []),
                  ]),
                  inputModalitiesBaseline: normalizeCaps([
                    ...(current?.input_modalities ?? []),
                  ]),
                  outputModalities: [...(current?.output_modalities ?? [])],
                  envOverride,
                  providerConfig,
                },
          };
        });
        // 2026-11-01 小欧 - load 直写 mtime 同拍镜像 ref（守卫实时比对单源） - 小欧-2026-11-01
        if (all.mtime) mtimeRef.current = all.mtime;
      } catch {
        // load 失败只保留全页 Result（loadError 由 SettingsPage 整屏渲染），不再叠加 handleApiError toast，
        //   原双提示重复噪询；Result 自带重试入口
        patchState({ loading: false, loadError: '设置加载失败' });
      }
    },
    [patchState, setState, mtimeRef]
  );

  useEffect(() => {
    void load();
  }, [load]);

  /** 切 Tab/刷新 mtime 检查。 */
  // 修复：后台配置被外部修改导致整体刷新时，若存在未保存的本地修改（脏 keys/模型参数），
  // 明确提示「已丢失」，不再只报「已刷新」让用户误以为本地改动还在
  const checkMtime = useCallback(async () => {
    try {
      const mtime = await settingsApi.getMtime();
      if (mtime !== state.mtime) {
        // 2026-09-27 小欧 - ③区草稿纳入"本地未保存修改"判定（load(reset) 会连草稿一起清，须先报丢失）- 小欧-2026-09-27
        const hasLocalDirty =
          Object.keys(state.dirtyKeys).length > 0 ||
          state.model.isDirty ||
          Object.keys(state.model.providerDraft).length > 0;
        // 外部更新 → 显式全量重置（load 默认会保留脏态，这里必须 reset 以对齐「已丢失」提示）
        await load({ reset: true });
        showMessage(
          hasLocalDirty ? ErrorType.WARNING : ErrorType.INFO,
          hasLocalDirty
            ? '后端配置已更新并刷新，本次未保存的修改已丢失'
            : '配置已更新，已刷新'
        );
      }
    } catch (e) {
      handleApiError(e);
    }
  }, [
    state.mtime,
    state.dirtyKeys,
    state.model.isDirty,
    state.model.providerDraft,
    load,
  ]);

  return { load, checkMtime };
}
