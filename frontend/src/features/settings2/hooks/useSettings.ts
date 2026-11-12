// 编辑历史: 2026-09-20 小强 - 新建：全局单层 state（分组/脏态/sources/模型管理/mtime 感知/外观本地预应用）。
// 2026-09-21 小欧 - 提示走 errorHandler；高亮 TTL；分组顺序由后端注册表派生；ghost 键清脏不假保存。
// 2026-09-22 小强 - 脏态以 baseline 对比撤销；load 默认保留未保存修改；保存前 mtime 守卫；env 接管禁改。
// 2026-09-22 小欧 - param_options 透传与枚举拦截；providerConfig 补 label/动态参数；providerConfig 与 envOverride 构建收口。
// 2026-09-23 小欧 - 参数与能力落码：addParam / setCapabilities；四通道回填能力基线；saveModelGroup 双通道
//   （参数无变不带 model_params，新键捎带自身 range/param_options，成功同步 providers 缓存）。
// 2026-09-24 小欧 - 键级删除 removeParam（四路删键 + removedParams 名单，重新 addParam 同名键即摘除）与能力默认值语义
//   （normalizeCaps 恒含 text 防假脏、capsForSave 无增强送 []、缓存存保存态）；saveModelGroup 回写 params/range/param_options。
// 2026-09-24 小欧 - addParam 加 env 接管守卫（UI 禁用之外再守一道）；暴露 ensureModelSaved 供删除确认前强制落库。
// 2026-09-27 小欧 - ③区草稿 providerDraft：initialModel 补空对象（load 非 keepModel 清、keepModel 保留）；
//   dirtyCount/isGroupDirty/beforeunload/checkMtime 四处纳入草稿；setProviderDraft 签名去重（防上报 effect 循环）。
// 2026-09-27 小欧 - saveProviderDraft 走 PUT /providers → syncMtime → reloadProviderCache → 清草稿；抽 reloadProviderCache
//   供 refreshModels 共用（不内联 refreshModels 以避循环依赖）；saveGroup('model') 串行保存。
// 2026-09-27 小欧 - saveAll 改串行且守卫只由第一路执行（并发两路拿同一旧 mtime 必误判外部更新并清空改动，
//   共享 saving 布尔还会提前解锁）；saveProviderDraft 补 api_base 空值守卫；patchModel 函数式更新并按最新 params 重算 isDirty。
// 2026-09-27 小欧 - ghost 键连 values 一并复位 baseline（原只删 dirtyKeys，界面仍显示改后值却不算未保存）。
// 2026-10-05 小欧 - saveKeys 成功后派发设置保存事件，事件名在 constants/settingsEvents（解除 settings2→chat 反向依赖）。
// 2026-11-01 小欧 - resetParams 改造为「放弃修改」：参数值/×删键/能力勾选三类未保存修改一拍全撤、值与脏同拍还原。
// 2026-11-01 小欧 - removedDrafts 快照：removeParam 四路删键后已保存值随之丢失，放弃时按快照逐键回填再清空；
//   保存链不碰快照（isDirty 只遍历 params 键，删键走 remove_params 独立通道）。
// 2026-11-01 小欧 - saveModelGroup 形态信封收口：只新键挂自身 range/param_options，空 map 不挂字段
//   （全量信封会把已放弃键的形态落进 model_meta，空块触发后端整块替换误清其他键）。
// 2026-11-01 小欧 - saveProviderDraft 补 mtime 外改守卫（与 saveKeys/saveModelGroup 同机制）；mtimeRef 实时镜像：
//   异步编排链捕获旧 render 闭包，新守卫一律读 ref，syncMtime/load 双写点同拍刷新。
// 2026-11-01 小欧 - 键名统一 default_params → model_params、defaults → baseline；四通道基线过
//   withDeclaredMeta（用户值优先、厂商声明窗口兜底，context_length 行恒可编辑）。
// 2026-11-08 小欧 - 能力字段拆 input/output 双维度；setOutputModalities 保留非可选项。
// 2026-11-09 小欧 - 输出模态改只读徽标：撤 setter 与保存通道，脏判定只看输入模态，加载链保留供徽标显示。
// 2026-11-09 小欧 - dirtyCount 走 modelDirtyCount 单源；新增 discardGroup（只撤当前组）— 小欧-2026-11-09
// 2026-11-11 小欧 - 撤 saveProbeImageUrl 导出(Image_URL 即存链已移除, 三个验证素材地址回媒体页走组保存) — 小欧-2026-11-11
// 2026-11-09 小欧 - 编排壳化：加载链/保存链/模型域拆至 useSettingsLoad、useSettingsPersist、useModelDomain — 小欧-2026-11-09
// 2026-11-11 小欧 - 注释勘误: 文件名纠错——useSettingsPersist/useModelDomain 实为 useSettingsWrites/useModelSaveChain — 小欧-2026-11-11
import { useCallback, useMemo, useRef, useState } from 'react';
import { modelDirtyCount } from '../utils/modelUtils';
import { initialModel } from '../utils/modelState';
import { findGroupOfKey } from '../utils/settingsShape';
import { PREF_KEY, readLocalPrefs, APPEARANCE_PREFS_CHANGED_EVT } from '@/constants/appearancePrefs';
import { useSettingsHighlight } from './useSettingsHighlight';
import { useSettingsLoad } from './useSettingsLoad';
import { useSettingsWrites } from './useSettingsWrites';
import { useModelSaveChain } from './useModelSaveChain';
import { useBatchSave } from './useBatchSave';
import { useModelSelection } from './useModelSelection';
import { useParamEditing } from './useParamEditing';
import { useProviderDraft } from './useProviderDraft';
import { useBeforeUnloadGuard } from './useBeforeUnloadGuard';
import type { SettingsState, TabKey } from '../types';

export function useSettings() {
  const [state, setState] = useState<SettingsState>({
    schema: {},
    values: {},
    baseline: {},
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

  const patchState = useCallback((p: Partial<SettingsState>) => {
    setState((s) => ({ ...s, ...p }));
  }, []);

  // 支持函数式更新：保存成功回写需按最新 model 重算脏态（请求在飞期间用户又改了参数，
  //   硬置 isDirty:false 会让那次编辑变成不可保存的隐形脏）；对象入参行为不变，合并逻辑此一处（DRY）。
  const patchModel = useCallback(
    (
      p:
        | Partial<SettingsState['model']>
        | ((m: SettingsState['model']) => Partial<SettingsState['model']>)
    ) => {
      setState((s) => ({
        ...s,
        model: { ...s.model, ...(typeof p === 'function' ? p(s.model) : p) },
      }));
    },
    []
  );

  // mtime 实时镜像 ref：saveAll/saveGroup/ensureModelSaved 异步编排链捕获的是旧 render 闭包，读 state.mtime 必得旧值
  //   ——前一路自写落盘 bump mtime 后，后一路守卫必误判「外部更新」→ load reset 清空草稿；新守卫一律读 mtimeRef - 小欧-2026-11-01
  const mtimeRef = useRef(0);
  /** 保存/模型 CRUD 后同步落盘后 mtime，防假后门刷新误判（与 mtimeRef 同拍）。 */
  const syncMtime = useCallback((mtime: number | undefined | null) => {
    if (mtime) {
      mtimeRef.current = mtime;
      setState((s) => ({ ...s, mtime }));
    }
  }, []);

  const { highlightKey, setHighlightKeyTtl } = useSettingsHighlight();

  const { load, checkMtime } = useSettingsLoad({
    state,
    setState,
    patchState,
    mtimeRef,
  });

  useBeforeUnloadGuard(
    state.dirtyKeys,
    state.model.isDirty,
    state.model.providerDraft
  );

  /** 改控件：与持久化基线对比记脏；外观两项同步 localStorage 预览。 */
  const setValue = useCallback((group: string, key: string, value: unknown) => {
    // 2026-11-12 小欧 - 外观两项(阅读区字号/界面密度)写本地预应用后广播变更事件:
    //   读取侧 hook(useAppearancePrefs)据此即时生效(不必等保存往返), 跨标签页由 storage 事件同步。
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
        window.dispatchEvent(new Event(APPEARANCE_PREFS_CHANGED_EVT));
      } catch {
        /* 本地预览失败不阻断 */
      }
    }
    setState((s) => {
      const values = {
        ...s.values,
        [group]: { ...(s.values[group] ?? {}), [key]: value },
      };
      // 与持久化/服务端基线一致则撤销脏标记，否则置脏——原无条件置脏，改回原值仍脏（迫使多存一次）
      const dirtyKeys = { ...s.dirtyKeys };
      if (s.baseline[group]?.[key] === value) delete dirtyKeys[key];
      else dirtyKeys[key] = true;
      return { ...s, values, dirtyKeys };
    });
  }, []);

  const groupOfKey = useCallback(
    (key: string): string | null => findGroupOfKey(state.schema, key),
    [state.schema]
  );

  // 2026-09-21 小强 - Tab 顺序唯一源=后端注册表：load 后 state.schema 键序即后端 GROUP_ORDER，
  //   前端不再硬编码分组顺序（原常量含已删 chat 组）；Tab 标题 label 由 SettingsPage 取 state.schema[g].label
  const GROUP_ORDER = useMemo(
    () => Object.keys(state.schema) as TabKey[],
    [state.schema]
  );

  // 修正(2026-09-21 小强)：脏计数模型按实际脏参数数计（原固定 +1，「保存全部(N 项)」对参数组恒 1 项误导）
  // 2026-11-09 小欧 - 与页面「保存本组」计数同源，算式收口到 modelDirtyCount — 小欧-2026-11-09
  const dirtyCount = useMemo(
    () => Object.keys(state.dirtyKeys).length + modelDirtyCount(state.model),
    [state.dirtyKeys, state.model]
  );

  const isGroupDirty = useCallback(
    (tab: TabKey) => {
      if (tab === 'model')
        return (
          state.model.isDirty ||
          // 2026-09-27 小欧 - ③区草稿纳入模型组脏判定（否则仅改③字段时「保存本组」灰着不可点）- 小欧-2026-09-27
          Object.keys(state.model.providerDraft).length > 0
        );
      return Object.keys(state.dirtyKeys).some((k) => groupOfKey(k) === tab);
    },
    [
      groupOfKey,
      state.dirtyKeys,
      state.model.isDirty,
      state.model.providerDraft,
    ]
  );

  const { saveKeys } = useSettingsWrites({
    state,
    setState,
    setSaving,
    setRestartKeys,
    mtimeRef,
    syncMtime,
    load,
    setHighlightKeyTtl,
  });

  const {
    reloadProviderCache,
    saveModelGroup,
    saveProviderDraft,
    ensureModelSaved,
  } = useModelSaveChain({
    state,
    patchModel,
    setSaving,
    mtimeRef,
    syncMtime,
    load,
  });

  const { saveGroup, saveAll } = useBatchSave({
    state,
    groupOfKey,
    saveKeys,
    saveModelGroup,
    saveProviderDraft,
  });

  const { selectProvider, selectModel, refreshModels } = useModelSelection({
    state,
    patchModel,
    ensureModelSaved,
    reloadProviderCache,
  });

  const {
    setParam,
    setInputModalities,
    addParam,
    removeParam,
    resetParams,
    discardGroup,
  } = useParamEditing({
    state,
    setState,
    patchModel,
  });

  const { setProviderDraft } = useProviderDraft({ setState });

  return {
    state,
    saving,
    restartKeys,
    setRestartKeys,
    highlightKey,
    setHighlightKey: setHighlightKeyTtl,
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
    // 2026-09-23 小欧 - 暴露 addParam 与 setCapabilities
    addParam,
    // 2026-09-24 小欧 - ①暴露 removeParam（参数行 × 删除，A 方案）- 小欧-2026-09-24
    removeParam,
    // 2026-11-08 小欧: 暴露 setInputModalities + setOutputModalities（能力双维度 setter）
    // 2026-11-09 小欧: 撤 setOutputModalities 暴露(输出模态改只读徽标, 无编辑入口) — 小欧-2026-11-09
    setInputModalities,
    resetParams,
    discardGroup,
    saveModelGroup,
    // 2026-09-24 小欧 - 暴露切换前强制保存（SettingsPage 删除确认前置调用，防删除后 load() 丢未存改动）
    ensureModelSaved,
    refreshModels,
    syncMtime,
    patchModel,
    patchState,
    // 2026-09-27 小欧 - ③区草稿：setProviderDraft 供 ProviderConfig 上报 diff，saveProviderDraft 供
    //   SettingsPage 的③自带保存按钮/底部保存栏共用一条落盘链 - 小欧-2026-09-27
    setProviderDraft,
    saveProviderDraft,
    setActiveTab: (t: TabKey) => patchState({ activeTab: t }),
  };
}

export type UseSettings = ReturnType<typeof useSettings>;
