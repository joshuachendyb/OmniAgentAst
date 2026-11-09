// 编辑历史: 2026-11-09 小欧 - 新建：模型参数与输入模态的内存编辑域（增删改/放弃修改），原 useSettings 逻辑原样搬迁 — 小欧-2026-11-09
import { useCallback, type Dispatch, type SetStateAction } from 'react';
import {
  isDirty,
  clampToRange,
  isCapsDirty,
  KNOWN_CAPABILITY_VALUES,
  normalizeCaps,
} from '../utils/modelUtils';
import { findGroupOfKey } from '../utils/settingsShape';
import { ErrorType, showMessage } from '@/services/error/handler';
import type { PatchModel, SettingsState, TabKey } from '../types';

interface ParamEditingDeps {
  state: SettingsState;
  setState: Dispatch<SetStateAction<SettingsState>>;
  patchModel: PatchModel;
}

export function useParamEditing({
  state,
  setState,
  patchModel,
}: ParamEditingDeps) {
  // env 接管键禁止修改：原 setParam 照写 params，isDirty 排除后永不提交且无提示，造成「改假值/静默丢失」；
  //   越界输入静默截断亦补提示
  const setParam = useCallback(
    (key: string, value: unknown) => {
      if (state.model.envOverride[key]) return;
      const range = state.model.ranges[key];
      // param_options 枚举拦截：字符串参数有选项表时，值必须在表内，否则拒绝并提示
      const opts = state.model.paramOptions[key];
      if (opts && !opts.includes(value as string)) {
        showMessage(
          ErrorType.WARNING,
          `参数 ${key} 为非法选项，允许：${opts.join('/')}`
        );
        return;
      }
      const clamped =
        typeof value === 'number' && range ? clampToRange(value, range) : value;
      if (typeof value === 'number' && range && clamped !== value) {
        showMessage(
          ErrorType.WARNING,
          `参数 ${key} 超出范围 [${range.min}, ${range.max}]，已自动校正为 ${clamped}`
        );
      }
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
              isDirty(params, s.model.baseline, s.model.envOverride)
            ).some(Boolean),
          },
        };
      });
    },
    [
      state.model.envOverride,
      state.model.ranges,
      state.model.paramOptions,
      setState,
    ]
  );

  // 2026-09-23 小欧 - setCapabilities：未知值合并（onChange 只含已渲染 5 枚举，
  //   uiValues ∪ state 未知原值 → state 恒含未知值，提交直接送无二次合并）+ isCapsDirty 联合置脏（baseline 不动）
  // 2026-09-23 小欧 - 已知值集合改用 modelUtils 单源常量（原每次调用重建 Set）
  // 2026-09-24 小欧 - ②归一：next 过 normalizeCaps（恒含 text——antd Checkbox disabled 项 onChange 可能不带，
  //   归一兜底；未知值仍保留）；isDirty 联合 removedParams — 小欧-2026-09-24
  // 2026-11-08 小欧: setCapabilities → setInputModalities（输入模态），新增 setOutputModalities
  const setInputModalities = useCallback(
    (uiValues: string[]) => {
      setState((s) => {
        const unknown = s.model.inputModalities.filter(
          (v) => !KNOWN_CAPABILITY_VALUES.has(v)
        );
        const next = normalizeCaps([...uiValues, ...unknown]);
        const paramsDirty = Object.values(
          isDirty(s.model.params, s.model.baseline, s.model.envOverride)
        ).some(Boolean);
        return {
          ...s,
          model: {
            ...s.model,
            inputModalities: next,
            // 2026-11-09 小欧: 输出模态改只读, 输入脏判定不再联合 output 检查 — 小欧-2026-11-09
            isDirty:
              paramsDirty ||
              isCapsDirty(next, s.model.inputModalitiesBaseline) ||
              s.model.removedParams.length > 0,
          },
        };
      });
    },
    [setState]
  );

  // 2026-09-23 小欧 - addParam：新键注入 params+ranges+paramOptions，baseline 不同步（立即判脏）
  const addParam = useCallback(
    (
      key: string,
      value: unknown,
      meta?: { range?: { min: number; max: number }; options?: string[] }
    ) => {
      // 2026-09-24 小欧：env 接管 Provider 禁添加参数（后端 _raise_if_env_takeover 拒保存；
      //   providerConfig.env 单源判定，与能力行/UI 入口禁用同源，hook 再守一道防绕过）
      if (state.model.providerConfig[state.model.selectedProvider]?.env) {
        showMessage(
          ErrorType.WARNING,
          '当前 Provider 由环境变量接管，不可添加参数'
        );
        return;
      }
      if (key in state.model.params) {
        showMessage(ErrorType.WARNING, `参数 ${key} 已存在`);
        return;
      }
      if (meta?.options && !meta.options.includes(value as string)) {
        showMessage(
          ErrorType.WARNING,
          `参数 ${key} 的值 ${value} 不在选项 ${meta.options.join('/')} 中`
        );
        return;
      }
      setState((s) => {
        const params = { ...s.model.params, [key]: value };
        const ranges = meta?.range
          ? { ...s.model.ranges, [key]: meta.range }
          : s.model.ranges;
        const paramOptions = meta?.options
          ? { ...s.model.paramOptions, [key]: meta.options }
          : s.model.paramOptions;
        // 2026-09-24 小欧 - ①重新加入已删键时从 removedParams 摘除（净效果：删后又加回同名键 = 无需后端删除）；
        //   仅该键从名单移除，isDirty 仍为 true（新键不在 baseline，注入即脏）- 小欧-2026-09-24
        const removedParams = s.model.removedParams.filter((k) => k !== key);
        return {
          ...s,
          model: {
            ...s.model,
            params,
            ranges,
            paramOptions,
            removedParams,
            isDirty: true,
          },
        };
      });
      // deps 只留判重闭包用的 params（ranges/paramOptions 在 setState 内经 s 读取，lint unnecessary 修正；
      //   env 接管守卫需 providerConfig/selectedProvider）
    },
    [
      state.model.params,
      state.model.providerConfig,
      state.model.selectedProvider,
      setState,
    ]
  );

  // 2026-09-24 小欧 - ①removeParam：参数行 × 删除（A 方案，点即删无确认）——四处同步删键
  //   （params/baseline/ranges/paramOptions；baseline 必须删否则 params⊔baseline 并集仍渲染、「重置为默认」复活）；
  //   仅 key∈baseline（已落盘）记入 removedParams 待后端 remove_params；未保存新键直接丢弃不送后端。
  //   env 接管键 UI 已禁用，此处再守一道（防绕过）；isDirty 联合 caps/removedParams/paramsDirty - 小欧-2026-09-24
  // 2026-11-01 小欧 - 删已落盘键时补记 removedDrafts 快照（已保存值/范围/选项，delete 前取值）：
  //   支撑「放弃修改」按快照回显删除行——baseline 四路全删设计不变（并集渲染复活防线不动），
  //   快照解决的是放弃修改的回显值来源 - 小欧-2026-11-01
  const removeParam = useCallback(
    (key: string) => {
      if (state.model.envOverride[key]) {
        showMessage(ErrorType.WARNING, `参数 ${key} 由环境变量接管，不可删除`);
        return;
      }
      setState((s) => {
        if (!(key in s.model.params) && !(key in s.model.baseline)) return s;
        const params = { ...s.model.params };
        const baseline = { ...s.model.baseline };
        const ranges = { ...s.model.ranges };
        const paramOptions = { ...s.model.paramOptions };
        const wasPersisted = key in baseline;
        delete params[key];
        // 2026-11-01 小欧 - 删除键的快照必须在 delete baseline[key] 之前取值——baseline[key]
        //   此刻就是该键的已保存值（load 装载 / 保存成功回写基准，两者都=后端已保存态） - 小欧-2026-11-01
        const savedValue = baseline[key];
        delete baseline[key];
        delete ranges[key];
        delete paramOptions[key];
        const removedDrafts = { ...s.model.removedDrafts };
        if (wasPersisted) {
          // 2026-11-01 小欧 - 已落盘键删除 → 快照已保存值（放弃修改按此回填，savedValue/ranges/
          //   paramOptions 此后即被上面三行删失）；每键覆盖式记录，同一键反复删存不会串 - 小欧-2026-11-01
          removedDrafts[key] = {
            value: savedValue,
            range: s.model.ranges[key],
            options: s.model.paramOptions[key],
          };
        }
        const removedParams = wasPersisted
          ? s.model.removedParams.includes(key)
            ? s.model.removedParams
            : [...s.model.removedParams, key]
          : s.model.removedParams.filter((k) => k !== key);
        const paramsDirty = Object.values(
          isDirty(params, baseline, s.model.envOverride)
        ).some(Boolean);
        // 2026-11-09 小欧: 输出模态改只读, 脏判定只看输入模态 — 小欧-2026-11-09
        const capsDirty = isCapsDirty(
          s.model.inputModalities,
          s.model.inputModalitiesBaseline
        );
        return {
          ...s,
          model: {
            ...s.model,
            params,
            baseline,
            ranges,
            paramOptions,
            removedDrafts,
            removedParams,
            isDirty: paramsDirty || capsDirty || removedParams.length > 0,
          },
        };
      });
    },
    // 2026-09-24 小欧 - deps 只留 envOverride（state.model.capabilities* 在 setState 回调内经 s 读取，lint unnecessary 修正）
    // 2026-11-01 小欧 - removedDrafts 草稿经 setState 回调内 s 读取（同 capabilities 惯例），不进 deps - 小欧-2026-11-01
    [state.model.envOverride, setState]
  );

  // 「放弃修改」：一拍全撤三类未保存修改，纯内存撤销不碰后端；函数式更新读最新 model。
  //   ①参数值还原 baseline；②removedParams 清空并按 removedDrafts 快照逐键回填（四路删键后键名单回不出已保存值）；
  //   ③能力勾选还原基线（值与脏同拍还原，铲掉历史上只清脏不还原显示值的静默丢失）；isDirty 同拍归零 - 小欧-2026-11-01
  const resetParams = useCallback(() => {
    patchModel((m) => {
      const params = { ...m.baseline };
      const baseline = { ...m.baseline };
      const ranges = { ...m.ranges };
      const paramOptions = { ...m.paramOptions };
      // ②回填：removedParams 里的每个已落盘键，把快照的已保存值/范围/选项原样放回
      //   （baseline 也回填——并集渲染与 isDirty 基线都依赖它；未快照键=未保存新键，本就不该复活）
      for (const key of m.removedParams) {
        const d = m.removedDrafts[key];
        if (!d) continue;
        params[key] = d.value;
        baseline[key] = d.value;
        if (d.range) ranges[key] = d.range;
        if (d.options) paramOptions[key] = d.options;
      }
      return {
        params,
        baseline,
        ranges,
        paramOptions,
        removedParams: [],
        removedDrafts: {},
        // 2026-11-09 小欧: 撤销删除回填输入模态基线（输出模态只读，无编辑可撤）— 小欧-2026-11-09
        inputModalities: normalizeCaps([...m.inputModalitiesBaseline]),
        isDirty: false,
      };
    });
  }, [patchModel]);

  /**
   * 放弃指定组的内存修改：model 组走 resetParams（参数/删键/能力）+ 清 ③ 草稿；
   * 其它组按基线还原 values 并清本组脏键（原「放弃并切换」用 load({reset:true}) 会连
   * 其它组与模型区一起丢，与弹窗「当前组」文案不符）— 小欧-2026-11-09
   */
  const discardGroup = useCallback(
    (tab: TabKey) => {
      if (tab === 'model') {
        resetParams();
        patchModel({ providerDraft: {} });
        return;
      }
      setState((st) => {
        const dirtyKeys = Object.fromEntries(
          Object.entries(st.dirtyKeys).filter(
            ([k]) => findGroupOfKey(st.schema, k) !== tab
          )
        );
        return {
          ...st,
          values: { ...st.values, [tab]: { ...(st.baseline[tab] ?? {}) } },
          dirtyKeys,
        };
      });
    },
    [resetParams, patchModel, setState]
  );

  return {
    setParam,
    setInputModalities,
    addParam,
    removeParam,
    resetParams,
    discardGroup,
  };
}
