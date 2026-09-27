// 编辑历史: 2026-09-20 小强 - 新建：全局单层 state（6 组+脏态+sources+模型管理+mtime 感知+外观本地预应用，见 6.2/6.3/7.0.5）
// 2026-09-21 小强 - 对齐统一提示规范(no-restricted-syntax)：message.* 改走 errorHandler(showMessage/showSuccess)，移除未用 ModelEntry 导入
// 2026-09-21 小欧 - ensureModelSaved 保存失败提示由 ERROR 对齐为 MODEL_CONFIG_ERROR（域名级错误码，信息更精确）
// 2026-09-21 小欧 - 搜索高亮加 TTL 自动消退
// 2026-09-21 小欧 - 补 max_retries：providerConfig 两处构建映射补齐 max_retries（load + refreshModels），对齐后端 GET /models 返回字段
// 2026-09-21 小欧 - 解耦：模型Tab①选择器改为纯前端焦点切换（selectedProvider/selectedModel/参数区联动，不写 ai.model_ref）——
//   全局生效模型唯一入口=通用Tab CurrentModelRefCard→ModelSwitchModal；原「双下拉即时落盘 model_ref」设计废弃
// 2026-09-21 小强 - Tab 标题/分组对齐后端注册表：GROUP_ORDER 由模块级硬编码（含死 chat）改为从 state.schema 键序动态派生，
//   分组顺序与 Tab 标题 label 唯一源=后端 settings_registry；前端不再维护任何分组名常量（下方 TAB_TITLES 已删）
// 2026-09-21 小欧 - 脏态与配置变更提示修复：①checkMtime 后台配置变化且存在未保存修改时，刷新前明确提示
//   「本地修改已丢失」，不再静默覆盖脏态；②saveKeys 将「schema 已删键/值为 undefined/env 接管键」归 ghost 清脏并提示，
//   杜绝 {key:undefined} 被 JSON 序列化丢键的假保存与 env 接管键假保存；③有效键为空直接返回不调 API；
//   ④后端 warnings 全为空文案时给固定兜底提示
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
// 2026-09-22 小欧 - param_options 读链：initialModel 加 paramOptions:{}；
//   load/selectProvider/selectModel/refreshModels 四处通道补 paramOptions 透传（源 current/first/entry/m.param_options）；
//   setParam 加枚举拦截（opts.includes(value) 不中 → WARNING+return，禁非法枚举写 state）。P4 将消费渲染 Select。
// 2026-09-22 小欧 - load() 与 refreshModels() 两处 providerConfig 构建补 label: p.label
//   （与后端 GET /models 返回 p.label 对齐；load 缺则 ProviderConfig 表单无显示名初值，refreshModels
//   缺则保存 label 后刷新即丢）。前后端写链路 label 编辑闭环。
// 2026-09-22 小欧 - ①load/refreshModels 两处 providerConfig 构建补动态参数值透传
//   （跳过已具名键，其余标量照抄——rate_limit 保存后重拉不丢）；②初始态补 paramOptionsModalOpen
// 2026-09-22 小欧 - DRY 收口（三堂会审 10 大规范）：①load/refreshModels 两处 providerConfig 构建重复 →
//   buildProviderConfig 公共函数；②load/selectProvider/selectModel/refreshModels 四处 envOverride 构建模式重复 →
//   getEnvOverride 公共函数；③saveKeys 内两处手写「查 schema 键归属组」循环与 groupOfKey 重复 → findGroupOfKey 单纯函数
//   （groupOfKey 改薄封装，setState 回调内传最新 s.schema）；三处均删重复回归单点维护 - 小欧-2026-09-22
// 2026-09-23 小欧 - 参数与能力落码：①新增 addParam（新键注入 defaults 不同步即脏）；②新增 setCapabilities（未知值合并+联合置脏）；
//   ③四通道回填 capabilities/capabilitiesBaseline；④dirtyCount 计能力脏 +1；⑤saveModelGroup 双通道
//   （参数无变不带 default_params；新键捎带全量 range/param_options；保存成功 providers 同步 patch 必修②）；
//   ⑥ensureModelSaved 放行补 isCapsDirty（必修①）—— import 并入既有 modelUtils 行 - 小欧-2026-09-23
// 2026-09-23 小欧 - 十遍会审：resetParams 联合置脏（重置只清参数脏，能力脏保留）+
//   已知能力值集改 modelUtils 单源常量（原每次调用重建 Set）- 小欧-2026-09-23
// 2026-09-24 小欧 - 修复：saveModelGroup 保存成功后 providers 条目同步补 default_params/range/param_options
//   （原仅同步 capabilities，default_params 停留在 load 时旧值）——selectModel 切回读 entry.default_params
//   得陈旧值致参数区显示旧值（big-pickle 保存362144、切走再切回显示10000）- 小欧-2026-09-24
// 2026-09-24 小欧 - ①参数键级删除 + ②能力默认值语义（北京老陈拍板）：
//   ①新增 removeParam（params/defaults/ranges/paramOptions 四处删键；仅 defaults 已有键记入 removedParams；
//     重新 addParam 同名键从 removedParams 摘除）；saveModelGroup/ensureModelSaved/dirtyCount/resetParams/
//     selectProvider/selectModel/refreshModels 全量纳入 removedParams；保存成功清空。
//   ②load/selectProvider/selectModel/refreshModels 四通道 capabilities/capabilitiesBaseline 过 normalizeCaps
//     （恒含 text 防假脏）；setCapabilities 归一并强制含 text；saveModelGroup 送 capsForSave（无增强→[]、
//     有增强→['text',...extras]）；providers 缓存 capabilities 存保存态（空→[] 防 tags 假显文本）。
//   initialModel 补 removedParams:[] 与 normalizeCaps 兼容初值 - 小欧-2026-09-24
// 2026-09-24 22:34:33 小欧 - 三堂会审修复：①addParam 加 env 接管守卫（与 removeParam 同款双防线——
//   UI 入口禁用外 hook 再守一道防绕过；env Provider 加参保存必被后端 _raise_if_env_takeover 拒，无用功+吃报错）；
//   ②暴露 ensureModelSaved 供 SettingsPage 删除确认前置调用（删除成功后 load() 全量重建 model 态，
//   不强制保存会静默丢弃模型 Tab 未落库改动，与 selectProvider/selectModel/refreshModels 同款防线复用）
//   - 小欧-2026-09-24
// 2026-09-27 小欧 - ③ Provider 配置改后底部保存栏亮起（北京老陈需求「3修改了, 出现保存的按钮」）：
//   ①initialModel 补 providerDraft:{}（非 keepModel 的 load 自动清、keepModel 保留）；
//   ②dirtyCount/isGroupDirty('model')/beforeunload/checkMtime 四处纳入 providerDraft 计数与判定；
//   ③新增 setProviderDraft（JSON 签名等价去重，防 ProviderConfig effect 重报造成渲染循环）；
//   ④新增 saveProviderDraft：updateProvider(PUT /providers) → syncMtime → reloadProviderCache → 清草稿；
//   ⑤抽 reloadProviderCache 公共函数（getModels+patch providers/providerConfig），saveProviderDraft/
//   refreshModels 共用（DRY）—— saveProviderDraft 不内联 refreshModels 是为避免
//   refreshModels→ensureModelSaved→saveProviderDraft 循环依赖；
//   ⑥saveGroup('model') = saveModelGroup 后串行 saveProviderDraft；saveAll 在 Promise.all 后串行 flush
//   （串行防 reloadProviderCache 与 saveModelGroup 的 providers patch 竞态）；
//   ⑦ensureModelSaved 放行条件补 providerDraft（切换前强制落库，同类防线）- 小欧-2026-09-27
// 2026-09-27 07:38 小欧 - ①saveAll 由 Promise.all 改串行（并发两路拿同一旧 mtime
//   做守卫，先落盘者 bump 服务端 mtime 使后一路必然误判"外部更新"→ load(reset) 清空用户全部未保存改动；
//   且两路共享单个 saving 布尔，先完成者提前解锁按钮可重复提交），守卫只由第一路执行（加 skipMtimeCheck
//   开关：守卫防的是外部更新，同一次 saveAll 内前一路自写不算）；②saveProviderDraft 补 base_url 空值守卫
//   （组件按钮已 disabled 并红字标注，但草稿走底栏可绕过 → 落盘空地址致该 Provider 全调用失败）；
//   ③patchModel 支持函数式更新，saveModelGroup 成功回写按最新 params 重算 isDirty（原先硬置 false，
//   请求在飞期间的新编辑变成保存按钮都点不亮的隐形脏）；④ghost 键连 values 一并复位到 baseline
//   （原先只删 dirtyKeys，值还留着改后内容，界面照显却已不算未保存）—— 小欧-2026-09-27
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  settingsApi,
  type SettingSchemaItem,
} from '@/services/api/settings.api';
import { modelApi, type ProviderEntry } from '@/services/api/model.api';
import {
  isDirty,
  clampToRange,
  validate,
  isCapsDirty,
  KNOWN_CAPABILITY_VALUES,
  // 2026-09-24 小欧 - ②能力归一/保存转换（modelUtils 单源，与 SettingsPage 共用词表）- 小欧-2026-09-24
  normalizeCaps,
  capsForSave,
} from '../utils/modelUtils';
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

// 2026-09-21 修复：secret 值归一（保存成功后 state 里不能再留明文/clear 标记，
// 否则 SettingRow 会误显"未配置"且再次保存重复提交）。
// 2026-09-27 - 小欧 - 契约收敛为 {configured, masked}：masked 一律由后端生成，
//   前端只把"未配置"归一成 {configured:false, masked:''}，不再自行 slice/拼星号。
function normalizeSecret(raw: unknown): unknown {
  if (typeof raw === 'string') {
    return { configured: false, masked: '' };
  }
  if (
    raw &&
    typeof raw === 'object' &&
    (raw as { clear?: boolean }).clear === true
  ) {
    return { configured: false, masked: '' };
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
  // 2026-09-23 小欧 - 能力编辑副本+基线（load 四通道回填覆盖）
  capabilities: [] as string[],
  capabilitiesBaseline: [] as string[],
  envOverride: {},
  providerConfig: {},
  // 2026-09-27 小欧 - ③区草稿初始干净（load 非 keepModel 重建即清；keepModel 由调用方保留）- 小欧-2026-09-27
  providerDraft: {} as Record<string, unknown>,
  isDirty: false,
  editingProviderConfig: false,
  addModelModalOpen: false,
  addProviderModalOpen: false,
  // 2026-09-22 小欧 - 初始态补 paramOptionsModalOpen（ModelState 已要求，缺则 tsc 报错）
  paramOptionsModalOpen: false,
  // 2026-09-23 小欧 - 「+ 添加参数」内联表单初始关
  addParamFormOpen: false,
  // 2026-09-24 小欧 - ①参数键级删除待提交名单初始空 — 小欧-2026-09-24
  removedParams: [] as string[],
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

  // 2026-09-27 小欧 - 支持函数式更新（修 F10）：保存成功回写时需要按**最新** model 重算脏态
  //   （请求在飞期间用户又改了参数，硬置 isDirty:false 会让那次编辑变成不可保存的隐形脏）。
  //   对象入参行为不变，合并逻辑仍此一处（DRY）。
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

  /** A7：保存/模型 CRUD 后同步落盘后 mtime，防假后门刷新误判（9.2.8/9.2.9 共用）。 */
  const syncMtime = useCallback((mtime: number | undefined | null) => {
    if (mtime) setState((s) => ({ ...s, mtime }));
  }, []);

  /** 首次加载：schema + 全量值 + 模型列表一次拉取（6.3/7.0.5）。 */
  // 2026-09-22 小强 - S2 修复：默认（非 reset）且存在未保存修改时，保留 dirtyKeys 与脏键缓冲值（values 脏键不上抛），
  //   杜绝 onModelSwitched（切全局模型 → load）静默丢脏；checkMtime/S11 守卫显式传 {reset:true} 才全量重置。
  //   同时新增 baseline（纯服务端值快照）供 S6 回滚判定；模型区按选中 provider.env 回填 envOverride（S5）。
  const load = useCallback(
    // 2026-09-26 - 小欧 - 修 C03「刷新 secret 掩码时静默清空模型区未保存修改」（三遍核实确认成立）：
    //   新增 `keepModel`：只刷新"设置区"(schema/values/sources/baseline/mtime)，**原样保留模型区**
    //   (selectedProvider/selectedModel/params/defaults/capabilities/envOverride/providerConfig)。
    //   起因：secret 行落盘后需重拉以刷新掩码，走的是 onRefresh → load()，而 load() 原实现
    //   **无条件重建整个 model 区**（见下方 setState 中 `model: {...initialModel(), ...}`）。
    //   `preserve` 逻辑只保护**设置区**的脏键缓冲，模型区的未保存编辑（改了参数/能力/勾了 env/
    //   换了 provider 或模型）在这次"只想刷新一行掩码"的操作里被**静默丢弃且无任何提示** ——
    //   用户视角：保存了一个 API Key，回到模型 Tab，刚才的参数全没了。
    //   调用方：SettingsGroup 的 onRefresh（secret 行专用通道落盘后）。 —— 编辑：小欧 2026-09-26
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
            // 2026-09-26 - 小欧 - 修 C03: keepModel 时保留模型区全部未保存编辑（详见 load 的 docstring）
            model: opts?.keepModel
              ? s.model
              : {
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
                    ...((current?.param_options ?? {}) as Record<
                      string,
                      string[]
                    >),
                  },
                  // 2026-09-24 小欧 - ②load 通道：normalizeCaps 归一（恒含 text 防假脏；未知值原样保留）- 小欧-2026-09-24
                  capabilities: normalizeCaps([
                    ...(current?.capabilities ?? []),
                  ]),
                  capabilitiesBaseline: normalizeCaps([
                    ...(current?.capabilities ?? []),
                  ]),
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

  // 31候选 #15：离开守卫——存在未保存修改（设置项脏键/模型参数/③区草稿）时拦截刷新与关闭，
  //   对齐 chat 侧 useBeforeUnload 语义（设置页原无守卫，改完点关闭静默丢改动）；
  //   监听在 useEffect 内注册，dirtyKeys/model.isDirty/providerDraft 变化时自动重绑，无脏态时不拦截
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (
        !Object.keys(state.dirtyKeys).length &&
        !state.model.isDirty &&
        // 2026-09-27 小欧 - ③区草稿也算未保存修改（否则改了 base_url 直接刷新静默丢）- 小欧-2026-09-27
        !Object.keys(state.model.providerDraft).length
      )
        return;
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [state.dirtyKeys, state.model.isDirty, state.model.providerDraft]);

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
  }, [
    state.mtime,
    state.dirtyKeys,
    state.model.isDirty,
    state.model.providerDraft,
    load,
  ]);

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
  // 2026-09-23 小欧 - 定案：能力脏计入 +1（isDirty 已联合判定，计数不跟上会「模型(0 项)却可保存」显示失真）
  const dirtyCount = useMemo(() => {
    const modelDirty = Object.values(
      isDirty(state.model.params, state.model.defaults, state.model.envOverride)
    ).filter(Boolean).length;
    const capsDirty = isCapsDirty(
      state.model.capabilities,
      state.model.capabilitiesBaseline
    )
      ? 1
      : 0;
    // 2026-09-24 小欧 - ①removedParams 每项计 1（删键是独立待存变更，计入「保存全部(N 项)」计数）- 小欧-2026-09-24
    const removedCount = state.model.removedParams.length;
    // 2026-09-27 小欧 - ③区草稿每键计 1（改了几个字段=几项，北京老陈需求的计数来源）- 小欧-2026-09-27
    const providerDraftCount = Object.keys(state.model.providerDraft).length;
    return (
      Object.keys(state.dirtyKeys).length +
      modelDirty +
      capsDirty +
      removedCount +
      providerDraftCount
    );
  }, [
    state.dirtyKeys,
    state.model.params,
    state.model.defaults,
    state.model.envOverride,
    state.model.capabilities,
    state.model.capabilitiesBaseline,
    state.model.removedParams,
    state.model.providerDraft,
  ]);

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

  /** 写（参数配置）：schema 校验 → PUT /settings。 */
  // 修复：①schema 已删键/值为 undefined/env 接管键一律归 ghost —— 不提交、清脏、提示，
  //   杜绝 {key:undefined} 被 JSON 序列化丢键的假保存 与 env 接管键被后端跳过后的假保存；
  //   ②有效键(found)为空则直接返回，不再调 API 制造空 patch 假成功
  const saveKeys = useCallback(
    async (keys: string[], opts?: { skipMtimeCheck?: boolean }) => {
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
          const values = { ...s.values };
          // 2026-09-27 小欧 - 修 F11：ghost 键要连 values 一起复位到 baseline。原实现只删 dirtyKeys，
          //   值还留着改后内容，界面照显却已不算未保存（脏标记与可见值脱节，用户以为改生效了）。
          ghost.forEach((k) => {
            const g = findGroupOfKey(s.schema, k);
            if (!g) return;
            delete dirtyKeys[k];
            values[g] = { ...values[g], [k]: s.baseline[g]?.[k] };
          });
          return { ...s, dirtyKeys, values };
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
        // 2026-09-27 小欧 - skipMtimeCheck：仅 saveAll 第二路用。守卫防的是**外部**更新，
        //   而同一次 saveAll 里前一路自己落盘 bump 的 mtime 不算外部更新（否则必然误判 → load 丢弃全部改动）。
        if (!opts?.skipMtimeCheck) {
          const curMtime = await settingsApi.getMtime();
          if (curMtime !== state.mtime) {
            await load({ reset: true });
            showMessage(
              ErrorType.WARNING,
              '配置已被外部更新，已重新加载，请核对后重新保存'
            );
            return { ok: false as const };
          }
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
        // 修复：后端 warnings 全为空文案时给固定兜底提示，避免空文案被 showMessage 静默吞掉后用户误以为干净保存
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
          // 2026-09-21 修复：secret 项保存成功后把明文/clear 归一回 {configured,suffix}，
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

  // 2026-09-27 小欧 - DRY：getModels + 同步 providers/providerConfig 缓存（原内联在 refreshModels），
  //   saveProviderDraft/refreshModels 共用单点。saveProviderDraft 不直接调 refreshModels 是为避免
  //   循环依赖（refreshModels→ensureModelSaved→saveProviderDraft），只取其中的缓存刷新段 - 小欧-2026-09-27
  const reloadProviderCache = useCallback(async () => {
    try {
      const models = await modelApi.getModels();
      // v4.19(P2-10 修正)：与 load() 同构重建 providerConfig（含 env），防保存/增删后 env 状态过期
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
    async (opts?: { skipMtimeCheck?: boolean }) => {
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
      // 2026-09-23 小欧 - 能力脏也算可保存；★空 changed 不带 default_params
      //   （后端 default_params:{} = 显式清空参数块，仅能力变更送 {} 会误清采样参数）
      const capsChanged = isCapsDirty(
        state.model.capabilities,
        state.model.capabilitiesBaseline
      );
      // 2026-09-24 小欧 - ①removedParams 也算可保存（仅删无改时 body 不带 default_params，只送 remove_params）
      const hasRemovals = state.model.removedParams.length > 0;
      if (!Object.keys(changed).length && !capsChanged && !hasRemovals)
        return { ok: true as const };
      // 2026-09-23 小欧 - 新增键形态持久化：新 key 才带全量 ranges/paramOptions 落 model_meta；
      //   无新键时 body 与原来完全一致（零行为变化）
      const prevDefaults = state.model.defaults;
      const newKeys = Object.keys(changed).filter((k) => !(k in prevDefaults));
      const body: {
        default_params?: Record<string, unknown>;
        range?: Record<string, { min: number; max: number }>;
        param_options?: Record<string, string[]>;
        capabilities?: string[];
        // 2026-09-24 小欧 - ①键级删除名单（与 default_params merge 叠加，后端先删再 merge）- 小欧-2026-09-24
        remove_params?: string[];
      } = {};
      if (hasRemovals) body.remove_params = [...state.model.removedParams];
      if (Object.keys(changed).length) {
        body.default_params = changed;
        if (newKeys.length) {
          body.range = { ...state.model.ranges };
          body.param_options = { ...state.model.paramOptions };
        }
      }
      // 2026-09-24 小欧 - ②capabilities 送保存态 capsForSave：无增强→[]、有增强→['text',...extras]
      //   （state 恒含 text，直接送会让纯文本模型落 ['text'] 而非隐含默认的空）- 小欧-2026-09-24
      if (capsChanged)
        body.capabilities = capsForSave(state.model.capabilities);
      setSaving(true);
      try {
        // S11：保存前校验 mtime（模型参数与设置同落 YAML），外部已更新则刷新并中止
        // 2026-09-27 小欧 - skipMtimeCheck 语义同 saveKeys
        if (!opts?.skipMtimeCheck) {
          const curMtime = await settingsApi.getMtime();
          if (curMtime !== state.mtime) {
            await load({ reset: true });
            showMessage(
              ErrorType.WARNING,
              '配置已被外部更新，已重新加载，请核对后重新保存'
            );
            return { ok: false as const };
          }
        }
        // A1：模型参数写 ai.{provider}.model_params.{model}.{key}（运行时 parse_model_params 消费），
        // 经 PUT /models/{provider}/{model} 的 default_params 通道，不再走 /settings 裸 key（registry 无此 key 会保存失败）
        const r = await modelApi.updateModel(
          state.model.selectedProvider,
          state.model.selectedModel,
          body
        );
        if (!r.ok) {
          showMessage(ErrorType.MODEL_CONFIG_ERROR, '模型参数保存失败');
          return { ok: false as const };
        }
        showSuccess('模型参数已保存');
        // 2026-09-23 小欧 - providers 内该模型 capabilities 同步 patch
        //   （否则参数区勾选已改、通用 Tab 卡片 tags 仍旧值直到 F5，同屏两处不同源=显示失真）
        // 2026-09-24 小欧 - 修复：同步补 default_params/range/param_options 回写 providers 缓存
        //   （原仅同步 capabilities——default_params 仍是 load 时旧值，selectModel 切回读 entry.default_params
        //   得旧值，参数区显示旧值而非刚保存的新值；range/param_options 新增键落盘同类隐患一并回写）- 小欧-2026-09-24
        // 2026-09-24 小欧 - ①保存成功后清空 removedParams；②capabilitiesBaseline 存归一态（与 state 一致防假脏）；
        //   providers 缓存存保存态 capsForSave（空→[] 防 tags 假显文本；有增强→['text',...extras]）- 小欧-2026-09-24
        const capsSaved = capsForSave(state.model.capabilities);
        // 2026-09-27 小欧 - 修 F10：函数式更新。defaults 仍存**本次实际提交的那份** params（落盘的就是
        //   它，用新值当基线等于把未保存的编辑当成已保存）；但 isDirty 按**最新** params 重算，
        //   请求在飞期间的新编辑不会被硬置的 false 吞掉（原先它变成保存按钮都点不亮的隐形脏）。
        patchModel((m) => ({
          defaults: { ...state.model.params },
          capabilitiesBaseline: normalizeCaps([...state.model.capabilities]),
          removedParams: [],
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
                          default_params: { ...state.model.params },
                          range: { ...state.model.ranges },
                          param_options: { ...state.model.paramOptions },
                          capabilities: capsSaved,
                        }
                  ),
                }
          ),
          isDirty: Object.values(
            isDirty(m.params, { ...state.model.params }, m.envOverride)
          ).some(Boolean),
        }));
        // A7：同步落盘后 mtime，防假后门刷新误判
        syncMtime(r.mtime);
        return { ok: true as const };
      } catch (e) {
        handleApiError(e);
        return { ok: false as const };
      } finally {
        setSaving(false);
      }
    },
    [patchModel, syncMtime, state.model, state.mtime, load]
  );

  // 2026-09-27 小欧 - ③区草稿写入：JSON 签名等价去重——这是防 ProviderConfig 上报 effect
  //   （每渲染无条件通知）造成 setState→渲染→effect 循环的**唯一防线**（同一 diff 重报时
  //   return 原 state 引用、不触发渲染，循环在此终止；三堂会审第6遍定案，组件侧不再去重）- 小欧-2026-09-27
  const setProviderDraft = useCallback((draft: Record<string, unknown>) => {
    setState((s) => {
      if (JSON.stringify(s.model.providerDraft) === JSON.stringify(draft))
        return s;
      return { ...s, model: { ...s.model, providerDraft: draft } };
    });
  }, []);

  // 2026-09-27 小欧 - ③区草稿落盘（北京老陈需求的统一保存链）：patch=③自带按钮提交的全量表单值，
  //   缺省=底部保存栏提交的草稿 diff；两入口同一链。成功 → 同步 mtime + 刷新 provider 缓存 + 清草稿；
  //   失败保留草稿（保存栏仍亮，可改后重试）- 小欧-2026-09-27
  const saveProviderDraft = useCallback(
    async (patch?: Record<string, unknown>) => {
      const draft = patch ?? state.model.providerDraft;
      if (!Object.keys(draft).length) return { ok: true as const };
      // 2026-09-27 小欧 - 修 F6：base_url 为空是错误态（组件内按钮已 disabled 并红字标注），
      //   但草稿里会带 base_url:'' 走底部保存栏进来，此前无校验直接 PUT → 落盘空地址、
      //   该 Provider 全部调用失败。校验下沉到此处，组件按钮与底栏两处同源（DRY）。
      if ('base_url' in draft && !String(draft.base_url ?? '').trim()) {
        showMessage(
          ErrorType.VALIDATE_CONFIG_FAILED,
          'API 地址不能为空，请填写后再保存'
        );
        return { ok: false as const };
      }
      setSaving(true);
      try {
        const r = await modelApi.updateProvider(
          state.model.selectedProvider,
          draft
        );
        if (!r.ok) {
          showMessage(ErrorType.MODEL_CONFIG_ERROR, 'Provider 配置保存失败');
          return { ok: false as const };
        }
        showSuccess('Provider 配置已保存（立即生效）');
        // A7：同步落盘后 mtime，防假后门刷新误判
        syncMtime(r.mtime);
        // 缓存刷新（掩码/label/timeout 回读）+ 草稿清空（保存栏计数归零）
        await reloadProviderCache();
        patchModel({ providerDraft: {} });
        return { ok: true as const };
      } catch (e) {
        handleApiError(e);
        return { ok: false as const };
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
    ]
  );

  // 跨模型/Provider 切换前强制保存未落库的模型参数，
  // 杜绝真实场景（agnes 空 dp <-> sensenova 有 dp）切换后参数静默丢失；保存失败则阻止切换。
  const ensureModelSaved = useCallback(async (): Promise<boolean> => {
    const dirtyMap = isDirty(
      state.model.params,
      state.model.defaults,
      state.model.envOverride
    );
    // 2026-09-23 小欧 - 放行条件补能力脏（否则"能力改了没存就切模型"静默丢失）
    // 2026-09-24 小欧 - ①放行条件补 removedParams（删键未存就切模型会静默丢失删除意图）- 小欧-2026-09-24
    // 2026-09-27 小欧 - 放行条件补 providerDraft（③区字段改了没存就切 Provider 会随组件重挂静默丢失；
    //   hadParams 拆出是为了只在参数/能力真保存过时才弹参数保存提示，防误导文案）- 小欧-2026-09-27
    const hadParams =
      Object.values(dirtyMap).some(Boolean) ||
      isCapsDirty(state.model.capabilities, state.model.capabilitiesBaseline) ||
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

  const saveGroup = useCallback(
    async (tab: TabKey) => {
      // 2026-09-27 小欧 - 模型组 = 参数/能力/删键 落库后串行 flush ③区草稿（参数保存失败时
      //   load(reset) 可能已清草稿，此时直接返回不重复提交，对齐"已丢失"提示语义）- 小欧-2026-09-27
      if (tab === 'model') {
        const a = await saveModelGroup();
        if (!a.ok) return a;
        return saveProviderDraft();
      }
      const keys = Object.keys(state.dirtyKeys).filter(
        (k) => groupOfKey(k) === tab
      );
      return saveKeys(keys);
    },
    [groupOfKey, state.dirtyKeys, saveKeys, saveModelGroup, saveProviderDraft]
  );

  // ---- 模型 Tab（8.2.10 脏态合并/截断；6.5 四区域） ----
  const saveAll = useCallback(async () => {
    const nonModelKeys = Object.keys(state.dirtyKeys).filter(
      (k) => !k.startsWith('model.')
    );
    const hasDraft = Object.keys(state.model.providerDraft).length > 0;
    if (!nonModelKeys.length && !state.model.isDirty && !hasDraft)
      return { ok: true as const };

    // 2026-09-27 小欧 - 修 F4/F5：改串行。原 Promise.all 并发时两路拿同一个旧 mtime 做守卫，
    //   先落盘的一路 bump 服务端 mtime，后一路必然误判"外部更新"→ load(reset) 清空用户全部未保存改动；
    //   且两路共享单个 saving 布尔，先完成者提前解锁按钮可重复提交。串行后守卫只由第一路执行。
    if (nonModelKeys.length) {
      const r = await saveKeys(nonModelKeys);
      if (!r.ok) return { ok: false as const };
    }
    if (state.model.isDirty) {
      const r = await saveModelGroup({ skipMtimeCheck: true });
      if (!r.ok) return { ok: false as const };
    }
    const d = await saveProviderDraft();
    return { ok: d.ok };
  }, [
    state.dirtyKeys,
    state.model.isDirty,
    state.model.providerDraft,
    saveKeys,
    saveModelGroup,
    saveProviderDraft,
  ]);

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
      // 修复：先保存未落库参数，再改焦点，防切换后参数静默丢失/数据不一致
      if (!(await ensureModelSaved())) return;
      // 2026-09-21 小欧 解耦：①选择器 = 参数编辑焦点（纯前端），只切 selectedProvider/selectedModel
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
        // 2026-09-24 小欧 - ②selectProvider 通道：normalizeCaps 归一（恒含 text 防假脏）- 小欧-2026-09-24
        capabilities: normalizeCaps([...(first?.capabilities ?? [])]),
        capabilitiesBaseline: normalizeCaps([...(first?.capabilities ?? [])]),
        // S5：切到 env 接管 provider 时参数区整体禁用（后端拒保存）
        envOverride: getEnvOverride(
          p.env,
          Object.keys(first?.default_params ?? {})
        ),
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
        // 2026-09-24 小欧 - ②selectModel 通道：normalizeCaps 归一（恒含 text 防假脏）- 小欧-2026-09-24
        capabilities: normalizeCaps([...(entry.capabilities ?? [])]),
        capabilitiesBaseline: normalizeCaps([...(entry.capabilities ?? [])]),
        // S5：选中 provider 为 env 接管时同步禁用其参数区
        envOverride: getEnvOverride(
          providerEntry?.env,
          Object.keys(nextDefaults)
        ),
        // 2026-09-24 小欧 - ①切模型重置删除名单（已随 ensureModelSaved 落库）- 小欧-2026-09-24
        removedParams: [],
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
              isDirty(params, s.model.defaults, s.model.envOverride)
            ).some(Boolean),
          },
        };
      });
    },
    [state.model.envOverride, state.model.ranges, state.model.paramOptions]
  );

  // 2026-09-23 小欧 - setCapabilities：未知值合并（onChange 只含已渲染 5 枚举，
  //   uiValues ∪ state 未知原值 → state 恒含未知值，提交直接送无二次合并）+ isCapsDirty 联合置脏（baseline 不动）
  // 2026-09-23 小欧 - 已知值集合改用 modelUtils 单源常量（原每次调用重建 Set）
  // 2026-09-24 小欧 - ②归一：next 过 normalizeCaps（恒含 text——antd Checkbox disabled 项 onChange 可能不带，
  //   归一兜底；未知值仍保留）；isDirty 联合 removedParams — 小欧-2026-09-24
  const setCapabilities = useCallback((uiValues: string[]) => {
    setState((s) => {
      const unknown = s.model.capabilities.filter(
        (v) => !KNOWN_CAPABILITY_VALUES.has(v)
      );
      const next = normalizeCaps([...uiValues, ...unknown]);
      const paramsDirty = Object.values(
        isDirty(s.model.params, s.model.defaults, s.model.envOverride)
      ).some(Boolean);
      return {
        ...s,
        model: {
          ...s.model,
          capabilities: next,
          isDirty:
            paramsDirty ||
            isCapsDirty(next, s.model.capabilitiesBaseline) ||
            s.model.removedParams.length > 0,
        },
      };
    });
  }, []);

  // 2026-09-23 小欧 - addParam：新键注入 params+ranges+paramOptions，defaults 不同步（立即判脏）
  const addParam = useCallback(
    (
      key: string,
      value: unknown,
      meta?: { range?: { min: number; max: number }; options?: string[] }
    ) => {
      // 2026-09-24 小欧 - BZ-8：env 接管 Provider 禁添加参数（后端 _raise_if_env_takeover 拒保存；
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
        //   仅该键从名单移除，isDirty 仍为 true（新键不在 defaults，注入即脏）- 小欧-2026-09-24
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
      //   BZ-8 守卫需 providerConfig/selectedProvider）
    },
    [
      state.model.params,
      state.model.providerConfig,
      state.model.selectedProvider,
    ]
  );

  // 2026-09-24 小欧 - ①removeParam：参数行 × 删除（A 方案，点即删无确认）——四处同步删键
  //   （params/defaults/ranges/paramOptions；defaults 必须删否则 params⊔defaults 并集仍渲染、「重置为默认」复活）；
  //   仅 key∈defaults（已落盘）记入 removedParams 待后端 remove_params；未保存新键直接丢弃不送后端。
  //   env 接管键 UI 已禁用，此处再守一道（防绕过）；isDirty 联合 caps/removedParams/paramsDirty - 小欧-2026-09-24
  const removeParam = useCallback(
    (key: string) => {
      if (state.model.envOverride[key]) {
        showMessage(ErrorType.WARNING, `参数 ${key} 由环境变量接管，不可删除`);
        return;
      }
      setState((s) => {
        if (!(key in s.model.params) && !(key in s.model.defaults)) return s;
        const params = { ...s.model.params };
        const defaults = { ...s.model.defaults };
        const ranges = { ...s.model.ranges };
        const paramOptions = { ...s.model.paramOptions };
        const wasPersisted = key in defaults;
        delete params[key];
        delete defaults[key];
        delete ranges[key];
        delete paramOptions[key];
        const removedParams = wasPersisted
          ? s.model.removedParams.includes(key)
            ? s.model.removedParams
            : [...s.model.removedParams, key]
          : s.model.removedParams.filter((k) => k !== key);
        const paramsDirty = Object.values(
          isDirty(params, defaults, s.model.envOverride)
        ).some(Boolean);
        const capsDirty = isCapsDirty(
          s.model.capabilities,
          s.model.capabilitiesBaseline
        );
        return {
          ...s,
          model: {
            ...s.model,
            params,
            defaults,
            ranges,
            paramOptions,
            removedParams,
            isDirty: paramsDirty || capsDirty || removedParams.length > 0,
          },
        };
      });
    },
    // 2026-09-24 小欧 - deps 只留 envOverride（state.model.capabilities* 在 setState 回调内经 s 读取，lint unnecessary 修正）
    [state.model.envOverride]
  );

  // 2026-09-23 小欧 - 重置只清参数脏，能力脏保留（原 isDirty:false 连能力脏一起抹，
  //   仅能力脏时点「重置为默认」→ 能力修改变不可保存。同 saveAll/isGroupDirty 的联合语义对齐）
  // 2026-09-24 小欧 - ①重置不清 removedParams（结构变更保留，仍需保存才落盘）；isDirty 联合之 - 小欧-2026-09-24
  const resetParams = useCallback(() => {
    patchModel({
      params: { ...state.model.defaults },
      isDirty:
        isCapsDirty(
          state.model.capabilities,
          state.model.capabilitiesBaseline
        ) || state.model.removedParams.length > 0,
    });
  }, [
    patchModel,
    state.model.defaults,
    state.model.capabilities,
    state.model.capabilitiesBaseline,
    state.model.removedParams,
  ]);

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
            // 2026-09-24 小欧 - ②refreshModels(select) 通道：normalizeCaps 归一（恒含 text 防假脏）- 小欧-2026-09-24
            capabilities: normalizeCaps([...(m.capabilities ?? [])]),
            capabilitiesBaseline: normalizeCaps([...(m.capabilities ?? [])]),
            // S5：目标 provider env 接管时禁用其参数区
            envOverride: getEnvOverride(p.env, Object.keys(defaults)),
            // 2026-09-24 小欧 - ①定位重置删除名单（已随 ensureModelSaved 落库）- 小欧-2026-09-24
            removedParams: [],
            isDirty: false,
          });
        }
      }
      return models;
    },
    [patchModel, ensureModelSaved, reloadProviderCache]
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
    // 2026-09-23 小欧 - 暴露 addParam 与 setCapabilities
    addParam,
    // 2026-09-24 小欧 - ①暴露 removeParam（参数行 × 删除，A 方案）- 小欧-2026-09-24
    removeParam,
    setCapabilities,
    resetParams,
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
