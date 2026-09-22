// 编辑历史: 2026-09-20 小强 - 新建：全局单层 state（6 组+脏态+sources+模型管理+mtime 感知+外观本地预应用，见 6.2/6.3/7.0.5）
// 2026-09-21 小强 - 对齐统一提示规范(no-restricted-syntax)：message.* 改走 errorHandler(showMessage/showSuccess)，移除未用 ModelEntry 导入
// 2026-09-21 小欧 - ensureModelSaved 保存失败提示由 ERROR 对齐为 MODEL_CONFIG_ERROR（域名级错误码，信息更精确）
// 2026-09-21 小欧 - P1-2：搜索高亮加 TTL 自动消退（[58] P1-2）
// 2026-09-21 小欧 - 补 max_retries：providerConfig 两处构建映射补齐 max_retries（load + refreshModels），对齐后端 GET /models 返回字段
// 2026-09-21 小欧 - 解耦：模型Tab①选择器改为纯前端焦点切换（selectedProvider/selectedModel/参数区联动，不写 ai.model_ref）——
//   全局生效模型唯一入口=通用Tab CurrentModelRefCard→ModelSwitchModal；原 v4.19(P1-6)「双下拉即时落盘 model_ref」设计废弃（[54] v4.20 修正）
// 2026-09-21 小强 - Tab 标题/分组对齐后端注册表：GROUP_ORDER 由模块级硬编码（含死 chat）改为从 state.schema 键序动态派生，
//   分组顺序与 Tab 标题 label 唯一源=后端 settings_registry；前端不再维护任何分组名常量（下方 TAB_TITLES 已删）
// 2026-09-21 小欧 - [59]F-3/F-15/F-16/F-14 修复：①checkMtime 后台配置变化且存在未保存修改时，刷新前明确提示
//   「本地修改已丢失」，不再静默覆盖脏态；②saveKeys 将「schema 已删键/值为 undefined/env 接管键」归 ghost 清脏并提示，
//   杜绝 {key:undefined} 被 JSON 序列化丢键的假保存(F-15)与 env 接管键假保存(F-16)；③有效键为空直接返回不调 API；
//   ④后端 warnings 全为空文案时给固定兜底提示(F-14)
// 2026-09-21 小强 - 设置页17问题复核修复：高亮TTL 2000→4000+新跳转清旧timer；dirtyCount 模型按实际脏参数量计数；
//   setParam ①env 接管键禁改（杜绝改假值静默丢失）②越界输入补校正提示（[设置页UI审计] 问题1/13/2/15）
// 2026-09-22 小强 - 编辑/保存 12 项可测缺陷批次2 修复（settings2-edsave-red）：
//   S6 setValue 与持久化基线(baseline)对比，改回原值撤销脏标记（原无条件置脏）；
//   S2 load() 遇未保存修改默认保留脏态+缓冲值（onModelSwitched 切全局模型不再静默丢脏），checkMtime 改显式 reset；
//   S11 saveKeys/saveModelGroup 保存前校验 mtime，外部已更新则刷新+提示并中止（防静默覆盖）；
//   S5 env provider 选中/切模型/刷新时回填 envOverride（load/selectProvider/selectModel/refreshModels），
//      参数区禁用+setParam 拒改（后端 _raise_if_env_takeover 保存必败，杜绝假操作）；
//   S12 selectProvider 无模型 Provider 补提示（原静默 return 无反馈）；
// 2026-09-22 小强 - 31候选 #22/#17/#15 修复：①load catch 去重（全页 Result 唯一通道，不再叠 toast）；
//   ②saveKeys 后端 errors 首 token 命中 schema 键 → setHighlightKeyTtl 红框定位；③beforeunload 离开守卫
//   （脏态下拦截刷新/关闭，对齐 chat useBeforeUnload 语义）
// 2026-09-22 小欧 - [62]P3 param_options 读链：initialModel 加 paramOptions:{}；
//   load/selectProvider/selectModel/refreshModels 四处通道补 paramOptions 透传（源 current/first/entry/m.param_options）；
//   setParam 加枚举拦截（opts.includes(value) 不中 → WARNING+return，禁非法枚举写 state）。P4 将消费渲染 Select。
// 2026-09-22 小欧 - [62]P6 4.3(6)：load() 与 refreshModels() 两处 providerConfig 构建补 label: p.label
//   （与后端 GET /models 返回 p.label 对齐；load 缺则 ProviderConfig 表单无显示名初值，refreshModels
//   缺则保存 label 后刷新即丢）。前后端写链路 label 编辑闭环。
// 2026-09-22 小欧 - [62]P8：①4.3(9)-2-d load()/refreshModels() 两处 providerConfig 构建补动态参数值透传
//   （跳过已具名键，其余标量照抄——rate_limit 保存后重拉不丢）；②4.3(8) 初始态补 paramOptionsModalOpen
// 2026-09-22 小欧 - DRY 收口（三堂会审 10 大规范）：①load/refreshModels 两处 providerConfig 构建重复 →
//   buildProviderConfig 公共函数；②load/selectProvider/selectModel/refreshModels 四处 envOverride 构建模式重复 →
//   getEnvOverride 公共函数；③saveKeys 内两处手写「查 schema 键归属组」循环与 groupOfKey 重复 → findGroupOfKey 单纯函数
//   （groupOfKey 改薄封装，setState 回调内传最新 s.schema）；三处均删重复回归单点维护 - 小欧-2026-09-22
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  settingsApi,
  type SettingSchemaItem,
} from '@/services/api/settings.api';
import { modelApi, type ProviderEntry } from '@/services/api/model.api';
import { isDirty, clampToRange, validate } from '../utils/modelUtils';
import type { ModelState, SettingsState, TabKey } from '../types';
import {
  ErrorType,
  handleApiError,
  showMessage,
  showSuccess,
} from '@/services/error/handler';

const PREF_KEY = 'omni.prefs.v1';

// 2026-09-22 小欧 - DRY 收口：load()/refreshModels() 两处 providerConfig 构建完全重复 → 抽公共构建函数
//   api_key/base_url/label/timeout/max_retries/env + 动态参数值（rate_limit 等 param_types 元数据驱动新键，
//   跳过具名键/元数据/列表类，其余标量照抄 [62]P8 4.3(9)-2-d）；只此一处维护，杜绝改一处漏一处
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

function buildProviderConfig(
  providers: ProviderEntry[]
): ModelState['providerConfig'] {
  return Object.fromEntries(
    providers.map((p) => [
      p.name,
      {
        api_key: p.api_key,
        base_url: p.api_base,
        label: p.label,
        timeout: p.timeout,
        max_retries: p.max_retries,
        env: p.env, // v4.19：provider 级 env 接管标记（对应 ProviderConfig isEnv），与模型参数 envOverride 分离
        // 2026-09-22 小欧 修 [62]P8 遗漏：param_types 元数据未透传 → ProviderConfig 动态渲染区
        //   永远为空（rate_limit 无「速率限制」行）。补透传，E2E-02 实测复现（E2E 浏览器验证）。
        param_types: p.param_types,
        // [62]P8 4.3(9)-2-d：动态参数值透传（rate_limit 等）——跳过已具名键 + 元数据 + 列表类，其余标量照抄
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
function getEnvOverride(
  env: boolean | undefined,
  keys: string[]
): Record<string, boolean> {
  return env ? Object.fromEntries(keys.map((k) => [k, true])) : {};
}

// 2026-09-22 小欧 - DRY 收口：saveKeys 内两处手写「查 schema 键归属组」循环与 groupOfKey 重复 → 单纯函数（setState 回调内传最新 s.schema）
function findGroupOfKey(
  schema: SettingsState['schema'],
  key: string
): string | null {
  for (const [g, grp] of Object.entries(schema)) {
    if (grp.items.some((i) => i.key === key)) return g;
  }
  return null;
}

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
  paramOptions: {},
  envOverride: {},
  providerConfig: {},
  isDirty: false,
  editingProviderConfig: false,
  addModelModalOpen: false,
  addProviderModalOpen: false,
  // 2026-09-22 小欧 - [62]P8 4.3(8)：初始态补 paramOptionsModalOpen（ModelState 已要求，缺则 tsc 报错）
  paramOptionsModalOpen: false,
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
  const [highlightKey, setHighlightKey] = useState<string | null>(null);

  // P1-2 修正(2026-09-21 小强)：高亮 TTL(4s) + 新跳转生效前清旧 timer，
  // 原 2s 且不清理 timer，连续搜索时旧 timer 提前熄灭新高亮（[设置页UI审计] 问题1）
  const HIGHLIGHT_TTL = 4000;
  const highlightTimer = useRef<number | null>(null);
  const setHighlightKeyTtl = useCallback((key: string | null) => {
    if (highlightTimer.current) window.clearTimeout(highlightTimer.current);
    setHighlightKey(key);
    if (key) {
      highlightTimer.current = window.setTimeout(
        () => setHighlightKey(null),
        HIGHLIGHT_TTL
      );
    }
  }, []);

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
  // 2026-09-22 小强 - S2 修复：默认（非 reset）且存在未保存修改时，保留 dirtyKeys 与脏键缓冲值（values 脏键不上抛），
  //   杜绝 onModelSwitched（切全局模型 → load）静默丢脏；checkMtime/S11 守卫显式传 {reset:true} 才全量重置。
  //   同时新增 baseline（纯服务端值快照）供 S6 回滚判定；模型区按选中 provider.env 回填 envOverride（S5）。
  const load = useCallback(
    async (opts?: { reset?: boolean }) => {
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
        const providerConfig = buildProviderConfig(models.providers);
        // S5：provider 由 {NAME}_API_KEY 环境变量接管时（后端 update_model/update_provider_config
        // 均 _raise_if_env_takeover 拒绝），其模型参数保存必败 → 参数区整体标记 envOverride 禁用。
        const envOverride = getEnvOverride(
          provider?.env,
          Object.keys(current?.default_params ?? {})
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
              paramOptions: {
                ...((current?.param_options ?? {}) as Record<string, string[]>),
              },
              envOverride,
              providerConfig,
            },
          };
        });
      } catch {
        // 31候选 #22：load 失败只保留全页 Result（loadError 由 SettingsPage 整屏渲染），
        //   不再叠加 handleApiError 系统 toast——原双提示重复噪询；Result 自带重试入口
        patchState({ loading: false, loadError: '设置加载失败' });
      }
    },
    [patchState]
  );

  useEffect(() => {
    void load();
  }, [load]);

  // 31候选 #15：离开守卫——存在未保存修改（设置项脏键/模型参数）时拦截刷新与关闭，
  //   对齐 chat 侧 useBeforeUnload 语义（设置页原无守卫，改完点关闭静默丢改动）；
  //   监听在 useEffect 内注册，dirtyKeys/model.isDirty 变化时自动重绑，无脏态时不拦截
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (!Object.keys(state.dirtyKeys).length && !state.model.isDirty) return;
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [state.dirtyKeys, state.model.isDirty]);

  /** 切 Tab/刷新 mtime 检查（3.1/9.11）。 */
  // [59]F-3 修复：后台配置被外部修改导致整体刷新时，若存在未保存的本地修改（脏 keys/模型参数），
  // 明确提示「已丢失」，不再只报「已刷新」让用户误以为本地改动还在
  const checkMtime = useCallback(async () => {
    try {
      const mtime = await settingsApi.getMtime();
      if (mtime !== state.mtime) {
        const hasLocalDirty =
          Object.keys(state.dirtyKeys).length > 0 || state.model.isDirty;
        // S2：外部更新 → 显式全量重置（load 默认会保留脏态，这里必须 reset 以对齐"已丢失"提示）
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
  }, [state.mtime, state.dirtyKeys, state.model.isDirty, load]);

  /** 改控件：与持久化基线对比记脏（S6）；外观两项同步 localStorage 预览（7.6）。 */
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
      // S6：与原（持久化/服务端基线）一致则撤销脏标记，否则置脏——原无条件置脏，改回原值仍脏（迫使多存一次）
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

  // 修正(2026-09-21 小强)：脏计数模型按实际脏参数数计（原固定 +1，「保存全部(N 项)」对参数组恒 1 项误导）([设置页UI审计] 问题13)
  const dirtyCount = useMemo(() => {
    const modelDirty = Object.values(
      isDirty(state.model.params, state.model.defaults, state.model.envOverride)
    ).filter(Boolean).length;
    return Object.keys(state.dirtyKeys).length + modelDirty;
  }, [
    state.dirtyKeys,
    state.model.params,
    state.model.defaults,
    state.model.envOverride,
  ]);

  const isGroupDirty = useCallback(
    (tab: TabKey) => {
      if (tab === 'model') return state.model.isDirty;
      return Object.keys(state.dirtyKeys).some((k) => groupOfKey(k) === tab);
    },
    [groupOfKey, state.dirtyKeys, state.model.isDirty]
  );

  /** 写（参数配置）：schema 校验 → PUT /settings（6.3/7.5）。 */
  // [59]F-15/F-16 修复：①schema 已删键/值为 undefined/env 接管键一律归 ghost —— 不提交、清脏、提示，
  //   杜绝 {key:undefined} 被 JSON 序列化丢键的假保存 与 env 接管键被后端跳过后的假保存；
  //   ②有效键(found)为空则直接返回，不再调 API 制造空 patch 假成功
  const saveKeys = useCallback(
    async (keys: string[]) => {
      const items: SettingSchemaItem[] = [];
      const values: Record<string, unknown> = {};
      const found: string[] = [];
      const ghost: string[] = [];
      keys.forEach((ck) => {
        for (const g of Object.keys(state.schema)) {
          const item = state.schema[g]?.items.find((i) => i.key === ck);
          if (!item) continue;
          const v = state.values[g]?.[ck];
          const src = state.sources[g]?.[ck];
          if (v !== undefined && src !== 'env') {
            items.push(item);
            values[ck] = v;
            found.push(ck);
          } else {
            ghost.push(ck);
          }
          return;
        }
        ghost.push(ck);
      });
      if (ghost.length) {
        setState((s) => {
          const dirtyKeys = { ...s.dirtyKeys };
          ghost.forEach((k) => delete dirtyKeys[k]);
          return { ...s, dirtyKeys };
        });
        showMessage(
          ErrorType.INFO,
          `已忽略不存在或环境变量接管的配置项：${ghost.join(', ')}`
        );
      }
      const bad = validate(items, values);
      if (bad) {
        setHighlightKeyTtl(bad.key);
        showMessage(ErrorType.WARNING, bad.message);
        return { ok: false as const, firstError: bad.key };
      }
      if (!found.length) return { ok: true as const };
      setSaving(true);
      try {
        // S11：保存前校验 mtime——后端已被外部更新则刷新并中止，杜绝本地静默覆盖且用户无感知
        const curMtime = await settingsApi.getMtime();
        if (curMtime !== state.mtime) {
          await load({ reset: true });
          showMessage(
            ErrorType.WARNING,
            '配置已被外部更新，已重新加载，请核对后重新保存'
          );
          return { ok: false as const };
        }
        const patch = Object.fromEntries(
          found.map((ck) => [
            ck,
            state.values[findGroupOfKey(state.schema, ck) ?? '']?.[ck],
          ])
        );
        const result = await settingsApi.updateSettings(patch);
        if (!result.ok) {
          result.errors.forEach((m) =>
            showMessage(ErrorType.VALIDATE_CONFIG_FAILED, m)
          );
          // 31候选 #17：后端校验错误高亮定位——错误文案首 token 形如 "agent.max_rounds 应为整数"的
          //   key 前缀，命中 schema 键则 setHighlightKeyTtl（原只弹 toast 无红框定位，用户找不到错项）
          const firstTok = result.errors[0]?.split(/\s+/)[0] ?? '';
          if (
            firstTok &&
            Object.values(state.schema).some((g) =>
              g.items.some((i) => i.key === firstTok)
            )
          ) {
            setHighlightKeyTtl(firstTok);
          }
          return { ok: false as const };
        }
        // [59]F-14 修复：后端 warnings 全为空文案时给固定兜底提示，避免空文案被 showMessage 静默吞掉后用户误以为干净保存
        const warnMsgs = result.warnings.filter((m) => (m ?? '').trim());
        if (result.warnings.length && !warnMsgs.length) {
          showMessage(
            ErrorType.WARNING,
            '部分配置项由环境变量接管，已跳过保存'
          );
        } else {
          warnMsgs.forEach((m) => showMessage(ErrorType.WARNING, m));
        }
        if (result.need_restart.length) setRestartKeys(result.need_restart);
        else showSuccess('保存成功');
        setState((s) => {
          const dirtyKeys = { ...s.dirtyKeys };
          found.forEach((k) => {
            delete dirtyKeys[k];
          });
          // 2026-09-21 BUG-C 修复：secret 项保存成功后把明文/clear 归一回 {configured,suffix}，
          // 保证再渲染正确显示且再次保存不重复提交明文
          const values = { ...s.values };
          const baseline = { ...s.baseline };
          items.forEach((it) => {
            if (!it.secret) return;
            const g = findGroupOfKey(s.schema, it.key);
            if (!g) return;
            values[g] = {
              ...(values[g] ?? {}),
              [it.key]: normalizeSecret(values[g]?.[it.key]),
            };
          });
          // S6：成功保存后把已保存键的基线同步为落盘值（含 secret 归一），回滚判定才有正确参照
          items.forEach((it) => {
            const g = findGroupOfKey(s.schema, it.key);
            if (!g || values[g] == null) return;
            baseline[g] = {
              ...(baseline[g] ?? {}),
              [it.key]: values[g][it.key],
            };
          });
          return { ...s, dirtyKeys, values, baseline };
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
    [
      state.schema,
      state.values,
      state.sources,
      state.mtime,
      load,
      syncMtime,
      setHighlightKeyTtl,
    ]
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
      // S11：保存前校验 mtime（模型参数与设置同落 YAML），外部已更新则刷新并中止
      const curMtime = await settingsApi.getMtime();
      if (curMtime !== state.mtime) {
        await load({ reset: true });
        showMessage(
          ErrorType.WARNING,
          '配置已被外部更新，已重新加载，请核对后重新保存'
        );
        return { ok: false as const };
      }
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
  }, [patchModel, syncMtime, state.model, state.mtime, load]);

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
      // S12：无此 Provider / 无模型的 Provider 给明确提示（原静默 return 无任何反馈）
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
      // BUG-D 修复：先保存未落库参数，再改焦点，防切换后参数静默丢失/数据不一致
      if (!(await ensureModelSaved())) return;
      // v4.20(小欧 2026-09-21 解耦)：①选择器 = 参数编辑焦点（纯前端），只切 selectedProvider/selectedModel
      //   + 参数区联动；不再写 ai.model_ref——全局生效模型唯一入口=通用Tab CurrentModelRefCard→ModelSwitchModal
      const defaults = {
        ...((first?.default_params ?? {}) as Record<string, unknown>),
      };
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
        paramOptions: {
          ...((first?.param_options ?? {}) as Record<string, string[]>),
        },
        // S5：切到 env 接管 provider 时参数区整体禁用（后端拒保存）
        envOverride: getEnvOverride(
          p.env,
          Object.keys(first?.default_params ?? {})
        ),
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
      // BUG-D 修复：先保存未落库参数，再改焦点，防切换时参数静默丢失
      if (!(await ensureModelSaved())) return;
      // v4.20(小欧 2026-09-21 解耦)：同 selectProvider，只切前端焦点，不再写 ai.model_ref
      const nextDefaults = { ...entry.default_params } as Record<
        string,
        unknown
      >;
      const nextRanges = { ...(entry.range ?? {}) } as Record<
        string,
        { min: number; max: number }
      >;
      const nextOptions = { ...(entry.param_options ?? {}) } as Record<
        string,
        string[]
      >;
      // 参数已随 ensureModelSaved 落库，新模型按默认值展示，无残留脏态/幽灵参数
      const providerEntry = state.model.providers.find(
        (x) => x.name === state.model.selectedProvider
      );
      patchModel({
        selectedModel: name,
        params: { ...nextDefaults },
        defaults: nextDefaults,
        ranges: nextRanges,
        paramOptions: nextOptions,
        // S5：选中 provider 为 env 接管时同步禁用其参数区
        envOverride: getEnvOverride(
          providerEntry?.env,
          Object.keys(nextDefaults)
        ),
        isDirty: Object.values(
          isDirty({ ...nextDefaults }, nextDefaults, state.model.envOverride)
        ).some(Boolean),
      });
    },
    [patchModel, state.model, ensureModelSaved]
  );

  // 修正(2026-09-21 小强)：①env 接管键禁止修改——原 setParam 照写 params，isDirty 排除后
  //   永不提交且无提示，造成「改了假值/静默丢失」（[设置页UI审计] 问题2）；②越界输入静默截断补提示（问题15）
  const setParam = useCallback(
    (key: string, value: unknown) => {
      if (state.model.envOverride[key]) return;
      const range = state.model.ranges[key];
      // [62]P3 param_options 枚举拦截：字符串参数有选项表时，值必须在表内，否则拒绝并提示
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
              isDirty(params, s.model.defaults, s.model.envOverride)
            ).some(Boolean),
          },
        };
      });
    },
    [state.model.envOverride, state.model.ranges, state.model.paramOptions]
  );

  const resetParams = useCallback(() => {
    patchModel({ params: { ...state.model.defaults }, isDirty: false });
  }, [patchModel, state.model.defaults]);

  const refreshModels = useCallback(
    async (select?: { provider: string; model: string }) => {
      // S3：带 select 的刷新（添加模型后定位）若当前参数未落库，先强制保存——与 selectProvider/selectModel
      //   同一 BUG-D 防线，杜绝切到新模型时旧模型未保存参数静默丢失
      if (select && !(await ensureModelSaved())) return null;
      try {
        const models = await modelApi.getModels();
        // v4.19(P2-10 修正)：与 load() 同构重建 providerConfig（含 env），防保存/增删后 env 状态过期
        patchModel({
          providers: models.providers,
          providerConfig: buildProviderConfig(models.providers),
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
              paramOptions: {
                ...((m.param_options ?? {}) as Record<string, string[]>),
              },
              // S5：目标 provider env 接管时禁用其参数区
              envOverride: getEnvOverride(p.env, Object.keys(defaults)),
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
    [patchModel, ensureModelSaved]
  );

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
