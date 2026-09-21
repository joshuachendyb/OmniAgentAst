// 编辑历史: 2026-09-20 小强 - 新建：全局单层 state（6 组+脏态+sources+模型管理+mtime 感知+外观本地预应用，见 6.2/6.3/7.0.5）
// 2026-09-21 小强 - 对齐统一提示规范(no-restricted-syntax)：message.* 改走 errorHandler(showMessage/showSuccess)，移除未用 ModelEntry 导入
// 2026-09-21 小欧 - ensureModelSaved 保存失败提示由 ERROR 对齐为 MODEL_CONFIG_ERROR（域名级错误码，信息更精确）
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  settingsApi,
  type SettingSchemaItem,
} from '@/services/api/settings.api';
import { modelApi } from '@/services/api/model.api';
import { isDirty, clampToRange, validate } from '../utils/modelUtils';
import type { SettingsState, TabKey } from '../types';
import {
  ErrorType,
  handleApiError,
  showMessage,
  showSuccess,
} from '@/services/error/handler';

const PREF_KEY = 'omni.prefs.v1';
const GROUP_ORDER: TabKey[] = [
  'general',
  'model',
  'security',
  'chat',
  'appearance',
  'system',
];

// 2026-09-21 BUG-C 修复：secret 值归一（保存成功后 state 里不能再留明文/clear 标记，
// 否则 SettingRow 会误显"未配置"且再次保存重复提交）：
// 明文非空 -> {configured:true, suffix}; 空明文/clear 标记 -> {configured:false}
function normalizeSecret(raw: unknown): unknown {
  if (typeof raw === 'string') {
    return raw === ''
      ? { configured: false, suffix: '' }
      : { configured: true, suffix: raw.slice(-4) };
  }
  if (
    raw &&
    typeof raw === 'object' &&
    (raw as { clear?: boolean }).clear === true
  ) {
    return { configured: false, suffix: '' };
  }
  return raw;
}

const initialModel = () => ({
  providers: [],
  selectedProvider: '',
  selectedModel: '',
  params: {},
  defaults: {},
  ranges: {},
  envOverride: {},
  providerConfig: {},
  isDirty: false,
  editingProviderConfig: false,
  addModelModalOpen: false,
  addProviderModalOpen: false,
  deleteConfirmOpen: false,
  deleteTarget: null as string | null,
});

function readLocalPrefs(): Record<string, unknown> {
  try {
    return JSON.parse(localStorage.getItem(PREF_KEY) || '{}') as Record<
      string,
      unknown
    >;
  } catch {
    return {};
  }
}

export function useSettings() {
  const [state, setState] = useState<SettingsState>({
    schema: {},
    values: {},
    sources: {},
    dirtyKeys: {},
    mtime: 0,
    loading: true,
    loadError: null,
    activeTab: 'general',
    model: initialModel(),
    currentRef: null,
  });
  const [saving, setSaving] = useState(false);
  const [restartKeys, setRestartKeys] = useState<string[]>([]);
  const [highlightKey, setHighlightKey] = useState<string | null>(null);

  const patchState = useCallback((p: Partial<SettingsState>) => {
    setState((s) => ({ ...s, ...p }));
  }, []);

  const patchModel = useCallback((p: Partial<SettingsState['model']>) => {
    setState((s) => ({ ...s, model: { ...s.model, ...p } }));
  }, []);

  /** A7：保存/模型 CRUD 后同步落盘后 mtime，防假后门刷新误判（9.2.8/9.2.9 共用）。 */
  const syncMtime = useCallback((mtime: number | undefined | null) => {
    if (mtime) setState((s) => ({ ...s, mtime }));
  }, []);

  /** 首次加载：schema + 全量值 + 模型列表一次拉取（6.3/7.0.5）。 */
  const load = useCallback(async () => {
    patchState({ loading: true, loadError: null });
    try {
      const [schema, all, models] = await Promise.all([
        settingsApi.getSchema(),
        settingsApi.getAll(),
        modelApi.getModels(),
      ]);
      const values = all.groups
        ? Object.fromEntries(
            Object.entries(all.groups).map(([g, v]) => [g, { ...v.data }])
          )
        : {};
      const sources = all.groups
        ? Object.fromEntries(
            Object.entries(all.groups).map(([g, v]) => [g, { ...v.sources }])
          )
        : {};
      // v4.19(P2-4 修正)：正常加载不再用 localStorage prefs 覆盖 values——后端 YAML 是唯一真相源，
      // local prefs 只承载"后端不可达时的本地试玩草稿"（7.6③），若潜伏自定义值遮蔽 YAML 会误导保存；
      // 后端不可达（本 try 已抛错走到 catch）时 values 保持未初始化，外观 Tab 本地模式另行消费 prefs。
      const ref = models.current_model_ref ?? null;
      const provider =
        models.providers.find((p) => p.name === ref?.provider) ??
        models.providers[0];
      const current =
        provider?.models.find((m) => m.name === (ref?.model ?? '')) ??
        provider?.models[0];
      const defaults = Object.fromEntries(
        Object.entries(
          (current?.default_params ?? {}) as Record<string, unknown>
        )
      );
      patchState({
        schema: schema.groups,
        values,
        sources,
        dirtyKeys: {},
        mtime: all.mtime,
        loading: false,
        currentRef: ref,
        model: {
          ...initialModel(),
          providers: models.providers,
          selectedProvider: provider?.name ?? '',
          selectedModel: current?.name ?? '',
          params: { ...defaults },
          defaults,
          ranges: {
            ...((current?.range ?? {}) as Record<
              string,
              { min: number; max: number }
            >),
          },
          providerConfig: Object.fromEntries(
            models.providers.map((p) => [
              p.name,
              {
                api_key: p.api_key,
                base_url: p.api_base,
                timeout: p.timeout,
                env: p.env, // v4.19：provider 级 env 接管标记（对应 ProviderConfig isEnv），与模型参数 envOverride 分离
              },
            ])
          ),
        },
      });
    } catch (e) {
      handleApiError(e);
      patchState({ loading: false, loadError: '设置加载失败' });
    }
  }, [patchState]);

  useEffect(() => {
    void load();
  }, [load]);

  /** 切 Tab/刷新 mtime 检查（3.1/9.11）。 */
  const checkMtime = useCallback(async () => {
    try {
      const mtime = await settingsApi.getMtime();
      if (mtime !== state.mtime) {
        await load();
        showMessage(ErrorType.INFO, '配置已更新，已刷新');
      }
    } catch (e) {
      handleApiError(e);
    }
  }, [state.mtime, load]);

  /** 改控件：记脏态；外观两项同步 localStorage 预览（7.6）。 */
  const setValue = useCallback((group: string, key: string, value: unknown) => {
    setState((s) => {
      const values = {
        ...s.values,
        [group]: { ...(s.values[group] ?? {}), [key]: value },
      };
      if (
        group === 'appearance' &&
        (key === 'appearance.fontSize' || key === 'appearance.density')
      ) {
        try {
          localStorage.setItem(
            PREF_KEY,
            JSON.stringify({
              ...readLocalPrefs(),
              [key === 'appearance.fontSize' ? 'fontSize' : 'density']: value,
            })
          );
        } catch {
          /* 本地预览失败不阻断 */
        }
      }
      return { ...s, values, dirtyKeys: { ...s.dirtyKeys, [key]: true } };
    });
  }, []);

  const groupOfKey = useCallback(
    (key: string): string | null => {
      for (const [g, items] of Object.entries(state.schema)) {
        if (items.items.some((i) => i.key === key)) return g;
      }
      return null;
    },
    [state.schema]
  );

  const dirtyCount = useMemo(
    () => Object.keys(state.dirtyKeys).length + (state.model.isDirty ? 1 : 0),
    [state.dirtyKeys, state.model.isDirty]
  );

  const isGroupDirty = useCallback(
    (tab: TabKey) => {
      if (tab === 'model') return state.model.isDirty;
      return Object.keys(state.dirtyKeys).some((k) => groupOfKey(k) === tab);
    },
    [groupOfKey, state.dirtyKeys, state.model.isDirty]
  );

  /** 写（参数配置）：schema 校验 → PUT /settings（6.3/7.5）。 */
  const saveKeys = useCallback(
    async (keys: string[]) => {
      const items: SettingSchemaItem[] = [];
      const values: Record<string, unknown> = {};
      keys.forEach((ck) => {
        for (const g of Object.keys(state.schema)) {
          const item = state.schema[g]?.items.find((i) => i.key === ck);
          if (item) {
            items.push(item);
            values[ck] = state.values[g]?.[ck];
            break;
          }
        }
      });
      const bad = validate(items, values);
      if (bad) {
        setHighlightKey(bad.key);
        showMessage(ErrorType.WARNING, bad.message);
        return { ok: false as const, firstError: bad.key };
      }
      setSaving(true);
      try {
        const patch = Object.fromEntries(
          keys.map((ck) => {
            const g = Object.keys(state.schema).find((g) =>
              state.schema[g]?.items.some((i) => i.key === ck)
            );
            return [ck, state.values[g ?? '']?.[ck]];
          })
        );
        const result = await settingsApi.updateSettings(patch);
        if (!result.ok) {
          result.errors.forEach((m) =>
            showMessage(ErrorType.VALIDATE_CONFIG_FAILED, m)
          );
          return { ok: false as const };
        }
        result.warnings.forEach((m) => showMessage(ErrorType.WARNING, m));
        if (result.need_restart.length) setRestartKeys(result.need_restart);
        else showSuccess('保存成功');
        setState((s) => {
          const dirtyKeys = { ...s.dirtyKeys };
          keys.forEach((k) => {
            delete dirtyKeys[k];
          });
          // 2026-09-21 BUG-C 修复：secret 项保存成功后把明文/clear 归一回 {configured,suffix}，
          // 保证再渲染正确显示且再次保存不重复提交明文
          const values = { ...s.values };
          items.forEach((it) => {
            if (!it.secret) return;
            const g = Object.keys(s.schema).find((g) =>
              s.schema[g]?.items.some((i) => i.key === it.key)
            );
            if (!g) return;
            values[g] = {
              ...(values[g] ?? {}),
              [it.key]: normalizeSecret(values[g]?.[it.key]),
            };
          });
          return { ...s, dirtyKeys, values };
        });
        // A7：用落盘后 mtime 覆盖缓存，防假后门刷新误判
        syncMtime(result.mtime);
        return { ok: true as const };
      } catch (e) {
        handleApiError(e);
        return { ok: false as const };
      } finally {
        setSaving(false);
      }
    },
    [state.schema, state.values, syncMtime]
  );

  const saveModelGroup = useCallback(async () => {
    const dirty = isDirty(
      state.model.params,
      state.model.defaults,
      state.model.envOverride
    );
    const changed = Object.fromEntries(
      Object.keys(dirty)
        .filter((k) => dirty[k])
        .map((k) => [k, state.model.params[k]])
    );
    if (!Object.keys(changed).length) return { ok: true as const };
    setSaving(true);
    try {
      // A1：模型参数写 ai.{provider}.model_params.{model}.{key}（运行时 parse_model_params 消费），
      // 经 PUT /models/{provider}/{model} 的 default_params 通道，不再走 /settings 裸 key（registry 无此 key 会保存失败）
      const r = await modelApi.updateModel(
        state.model.selectedProvider,
        state.model.selectedModel,
        {
          default_params: changed,
        }
      );
      if (!r.ok) {
        showMessage(ErrorType.MODEL_CONFIG_ERROR, '模型参数保存失败');
        return { ok: false as const };
      }
      showSuccess('模型参数已保存');
      patchModel({ defaults: { ...state.model.params }, isDirty: false });
      // A7：同步落盘后 mtime，防假后门刷新误判
      syncMtime(r.mtime);
      return { ok: true as const };
    } catch (e) {
      handleApiError(e);
      return { ok: false as const };
    } finally {
      setSaving(false);
    }
  }, [patchModel, syncMtime, state.model]);

  // v4.25(2026-09-21 小强 修复 BUG-D)：跨模型/Provider 切换前强制保存未落库的模型参数，
  // 杜绝真实场景（agnes 空 dp <-> sensenova 有 dp）切换后参数静默丢失；保存失败则阻止切换。
  const ensureModelSaved = useCallback(async (): Promise<boolean> => {
    const dirtyMap = isDirty(
      state.model.params,
      state.model.defaults,
      state.model.envOverride
    );
    if (!Object.values(dirtyMap).some(Boolean)) return true;
    const r = await saveModelGroup();
    if (!r.ok) {
      showMessage(
        ErrorType.MODEL_CONFIG_ERROR,
        '模型参数保存失败，已阻止切换（防止数据丢失）'
      );
      return false;
    }
    showMessage(ErrorType.INFO, '已保存当前模型参数修改');
    return true;
  }, [saveModelGroup, state.model]);

  const saveGroup = useCallback(
    (tab: TabKey) => {
      if (tab === 'model') return saveModelGroup();
      const keys = Object.keys(state.dirtyKeys).filter(
        (k) => groupOfKey(k) === tab
      );
      return saveKeys(keys);
    },
    [groupOfKey, state.dirtyKeys, saveKeys, saveModelGroup]
  );

  // ---- 模型 Tab（8.2.10 脏态合并/截断；6.5 四区域） ----
  const saveAll = useCallback(async () => {
    const tasks: Array<Promise<{ ok: boolean }>> = [];
    const nonModelKeys = Object.keys(state.dirtyKeys).filter(
      (k) => !k.startsWith('model.')
    );
    if (nonModelKeys.length) tasks.push(saveKeys(nonModelKeys));
    if (state.model.isDirty) tasks.push(saveModelGroup());
    if (!tasks.length) return { ok: true as const };
    const results = await Promise.all(tasks);
    return { ok: results.every((r) => r.ok) };
  }, [state.dirtyKeys, state.model.isDirty, saveKeys, saveModelGroup]);

  const selectProvider = useCallback(
    async (name: string) => {
      const p = state.model.providers.find((x) => x.name === name);
      const first = p?.models[0];
      if (!p || !first) return;
      // BUG-D 修复：先保存未落库参数，再改 ai.model_ref，防切换后参数静默丢失/数据不一致
      if (!(await ensureModelSaved())) return;
      const defaults = {
        ...((first?.default_params ?? {}) as Record<string, unknown>),
      };
      // v4.19(P1-6 修正)：双下拉 ai.model_ref 即时落盘（4.2 表「双下拉 · YAML · 即时」），
      // 成功返回新 mtime 再同步内存，杜绝「页面切换成功、重启后失效」的假成功。
      const r = await settingsApi.updateSettings({
        'ai.model_ref': { provider: name, model: first.name },
      });
      syncMtime(r.mtime);
      patchModel({
        selectedProvider: name,
        selectedModel: first?.name ?? '',
        params: defaults,
        defaults,
        ranges: {
          ...((first?.range ?? {}) as Record<
            string,
            { min: number; max: number }
          >),
        },
        isDirty: false,
      });
    },
    [patchModel, state.model.providers, syncMtime, ensureModelSaved]
  );

  const selectModel = useCallback(
    async (name: string) => {
      const entry = state.model.providers
        .find((x) => x.name === state.model.selectedProvider)
        ?.models.find((m) => m.name === name);
      if (!entry) return;
      // BUG-D 修复：先保存未落库参数，再改 ai.model_ref，防切换同模型时参数静默丢失
      if (!(await ensureModelSaved())) return;
      // v4.19(P1-6 修正)：同 selectProvider，即刻落盘 ai.model_ref 再更新内存。
      const r = await settingsApi.updateSettings({
        'ai.model_ref': { provider: state.model.selectedProvider, model: name },
      });
      syncMtime(r.mtime);
      const nextDefaults = { ...entry.default_params } as Record<
        string,
        unknown
      >;
      const nextRanges = { ...(entry.range ?? {}) } as Record<
        string,
        { min: number; max: number }
      >;
      // 参数已随 ensureModelSaved 落库，新模型按默认值展示，无残留脏态/幽灵参数
      patchModel({
        selectedModel: name,
        params: { ...nextDefaults },
        defaults: nextDefaults,
        ranges: nextRanges,
        isDirty: Object.values(
          isDirty({ ...nextDefaults }, nextDefaults, state.model.envOverride)
        ).some(Boolean),
      });
    },
    [patchModel, state.model, syncMtime, ensureModelSaved]
  );

  const setParam = useCallback((key: string, value: unknown) => {
    setState((s) => {
      const params = {
        ...s.model.params,
        [key]: clampToRange(value, s.model.ranges[key]),
      };
      return {
        ...s,
        model: {
          ...s.model,
          params,
          isDirty: Object.values(
            isDirty(params, s.model.defaults, s.model.envOverride)
          ).some(Boolean),
        },
      };
    });
  }, []);

  const resetParams = useCallback(() => {
    patchModel({ params: { ...state.model.defaults }, isDirty: false });
  }, [patchModel, state.model.defaults]);

  const refreshModels = useCallback(
    async (select?: { provider: string; model: string }) => {
      try {
        const models = await modelApi.getModels();
        // v4.19(P2-10 修正)：与 load() 同构重建 providerConfig（含 env），防保存/增删后 env 状态过期
        patchModel({
          providers: models.providers,
          providerConfig: Object.fromEntries(
            models.providers.map((p) => [
              p.name,
              {
                api_key: p.api_key,
                base_url: p.api_base,
                timeout: p.timeout,
                env: p.env, // v4.19：provider 级 env 接管标记（对应 ProviderConfig isEnv）
              },
            ])
          ),
        });
        if (select) {
          const p = models.providers.find((x) => x.name === select.provider);
          const m = p?.models.find((x) => x.name === select.model);
          if (p && m) {
            const defaults = {
              ...(m.default_params as Record<string, unknown>),
            };
            patchModel({
              selectedProvider: p.name,
              selectedModel: m.name,
              params: { ...defaults },
              defaults,
              ranges: {
                ...(m.range as Record<string, { min: number; max: number }>),
              },
              isDirty: false,
            });
          }
        }
        return models;
      } catch (e) {
        handleApiError(e);
        return null;
      }
    },
    [patchModel]
  );

  return {
    state,
    saving,
    restartKeys,
    setRestartKeys,
    highlightKey,
    setHighlightKey,
    dirtyCount,
    isGroupDirty,
    groupOfKey,
    GROUP_ORDER,
    load,
    checkMtime,
    setValue,
    saveGroup,
    saveAll,
    selectProvider,
    selectModel,
    setParam,
    resetParams,
    saveModelGroup,
    refreshModels,
    syncMtime,
    patchModel,
    patchState,
    setActiveTab: (t: TabKey) => patchState({ activeTab: t }),
  };
}

export type UseSettings = ReturnType<typeof useSettings>;
