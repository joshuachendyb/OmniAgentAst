// 编辑历史: 2026-09-20 小强 - 新建：纯函数层（isDirty/clampToRange/validate，无 JSX，可单测，见 6.2/7.5）
// 2026-09-22 小强 - S7：validate 拒 null（原 null 与 undefined 一并 continue 放行，前端放行 → 落库被后端拒）；
//    null 仅当 schema 默认值本身为 null（可空项）时放行，其余类型返回「不能为空」
// 2026-09-22 小强 - 31候选 #3/#8：int 补 Number.isInteger（1.5 曾过前端、后端"应为整数"拒=契约漂移；
//    红测先红），range 补 step 倍数校验（12.5 过前端、对称后端 #8）
// 2026-09-22 小欧 - 实施 isDirty 对象深比较：补 sameValue（Object.is 快路径 + 双对象
//    JSON.stringify 深比），替换原 `!==`——对象/数组参数两个独立字面量内容相同但引用不同被判恒脏
// 2026-09-23 小欧 - 新增 isCapsDirty + CAPABILITY_OPTIONS（复用既有 sameValue 与单源词表）- 小欧-2026-09-23
// 2026-09-23 小欧 - isCapsDirty 排序后比(集合语义, 手写 YAML 顺序不产生假脏);
//   新增 KNOWN_CAPABILITY_VALUES 单源(setCapabilities 每次重建 Set → 模块常量) - 小欧-2026-09-23
// 2026-09-24 小欧 - 能力默认值语义（北京老陈拍板）：①文本项 disabled 恒勾选；②normalizeCaps 归一恒含 text
//   （load/select 四通道防假脏）；③capsForSave 保存转换——无增强送 []、有增强送 ['text',...extras] - 小欧-2026-09-24
// 2026-10-03 小欧 - 免费判定迁入本纯函数层（原组件内私有，无法单测）；判据扩为三判据 OR — 小欧 2026-10-03
// 2026-10-10 小欧 - PARAM_PRESETS 自 AddParamForm 整块迁移至此（与 PARAM_DEFAULT_RANGES 同数据层）：
//   AddParamForm（勾选添加参数）与 ModelModals（新建模型参数模板）双消费，组件间互引数据是分层异味。
//   同步：reasoning_effort options 加 minimal 档（与后端 DEFAULT_PARAM_OPTIONS 同步，校验只认后端那张表，
//   漏同步则存 minimal 报"非法选项"；fre2e_08 用自带列表，不受影响） — 小欧-2026-10-10
// 2026-10-24 小欧 - reasoning_effort options 移除 minimal: OpenAI 官方文档 "Not all reasoning models
//   support every value"，minimal 是少数派值，全局兜底只留 low/medium/high — 小欧-2026-10-24
// 2026-11-01 小欧 - 键名统一 + 上下文窗口可编辑（北京老陈指令）：
//   ①PARAM_DEFAULT_RANGES / PARAM_PRESETS 的 context_limit → context_length（与后端 yaml 真源同名）；
//   ②新增 withDeclaredMeta：基线补厂商声明窗口与输出上限（用户值优先，声明值仅兜底），
//     使模型库勾选进来的模型在②参数区也有一条可编辑的 context_length 行 — 小欧-2026-11-01
// 2026-11-08 小欧 - 新增 KNOWN_OUTPUT_MODALITY_VALUES 单源（输出行未知值灰标 + setter 保留非可选项） — 小欧-2026-11-08
// 2026-11-09 小欧 - OUTPUT_MODALITY_OPTIONS 补 audio=音频生成（实库 kilo/lyria 音频输出）；未知值域收窄 text/file — 小欧-2026-11-09
// 2026-11-09 小欧 - OUTPUT 再补 text=文本：4 枚徽标齐显(声明橙/未声明灰)，未知值域仅剩 file — 小欧-2026-11-09
// 2026-11-09 小欧 - 输出标签去「生成」后缀, 四枚与输入侧同词(文本/图片/视频/音频) — 小欧-2026-11-09
import type { SettingSchemaItem } from '@/services/api/settings.api';
import type { RemoteModelItem } from '@/services/api/model.api';
import type { ModelState } from '../types';

/** 报价是否为 0。Number() 兼容 "0"/0/"0.000"；v != null 必留（Number(null)===0 会误标免费）。 */
const isZeroPrice = (v: string | undefined): boolean =>
  v != null && Number(v) === 0;

/** 名称 free 尾巴。必须 endsWith：includes('-free') 实测 OpenRouter 460 个命中 0（它用 :free），
 *  且会误伤 free-tier。`-free` 本仓实证 / `:free` OpenRouter 实证；_free 无实证不引入(YAGNI)。 */
export const isFreeNameSuffix = (v: string | undefined | null): boolean => {
  const s = (v ?? '').trim().toLowerCase(); // (v ?? '') 防 undefined 调 endsWith 抛错
  return s.endsWith('-free') || s.endsWith(':free');
};

/** 免费判据单点收口，三判据 OR（2026-10-03 确认，兼容优先）：
 *  ①free === true（AMD 记账标记，非"要花钱"）②名称 free 尾巴 ③pricing 双 0（2026-09-29 原判据不变）。
 *  OR 的已知代价：AMD MinerU2.5-Pro（free=false + pricing 双 0）会显示「免费」，已如实告知并接受。
 *  严格 === true：远端下发字符串 "true" 时不冒充免费。 */
export const isFreeModel = (m: RemoteModelItem): boolean =>
  m.free === true ||
  isFreeNameSuffix(m.id) ||
  (isZeroPrice(m.pricing?.prompt) && isZeroPrice(m.pricing?.completion));

/** 值深比较——同一引用/Object.is 相同立即真；双方对象则 JSON 深比；其余恒假。 */
function sameValue(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (
    a !== null &&
    b !== null &&
    typeof a === 'object' &&
    typeof b === 'object'
  ) {
    try {
      return JSON.stringify(a) === JSON.stringify(b);
    } catch {
      return false;
    }
  }
  return false;
}

/** 模型 Tab 脏态：值与已保存基线不一致且未被 env 接管。 */
export function isDirty(
  params: Record<string, unknown>,
  baseline: Record<string, unknown>,
  env: Record<string, boolean>
): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  Object.keys(params).forEach((key) => {
    out[key] = !env[key] && !sameValue(params[key], baseline[key]);
  });
  return out;
}

/**
 * 已保存参数基线：用户值优先，厂商声明值(context_length/max_output_length)仅兜底，两键独立判缺补齐。
 * 2026-11-01 小欧 - 声明值只入基线不入 params(少脏态); max_output_length 行只读, 严禁开放编辑
 *   (该键不在后端 pop 名单, 曾随 extra_body 出网易被厂商 400) — 小欧 2026-11-01
 */
export const withDeclaredMeta = (
  params: Record<string, unknown>,
  declaredCtx: number | null | undefined,
  declaredMaxOut: number | null | undefined
): Record<string, unknown> => {
  const out: Record<string, unknown> = { ...params };
  if (
    (out.context_length === undefined || out.context_length === null) &&
    typeof declaredCtx === 'number' &&
    declaredCtx > 0
  ) {
    out.context_length = declaredCtx;
  }
  if (
    (out.max_output_length === undefined || out.max_output_length === null) &&
    typeof declaredMaxOut === 'number' &&
    declaredMaxOut > 0
  ) {
    out.max_output_length = declaredMaxOut;
  }
  return out;
};

/** 超出新模型范围自动截断。 */
export function clampToRange(
  value: unknown,
  range?: { min: number; max: number }
): unknown {
  if (typeof value !== 'number' || !range) return value;
  if (value < range.min) return range.min;
  if (value > range.max) return range.max;
  return value;
}

/** 保存前 schema 校验：返回首个错误 {key, message}，通过返回 null。 */
export function validate(
  items: SettingSchemaItem[],
  values: Record<string, unknown>
): { key: string; message: string } | null {
  for (const item of items) {
    if (item.readonly) continue;
    const value = values[item.key];
    if (value === undefined) continue;
    // S7：null 仅当 schema 默认值本身为 null（声明可空）时放行，其余报错（对齐后端 settings_service._validate_value）
    if (value === null) {
      if (item.default === null) continue;
      return { key: item.key, message: `${item.label}不能为空` };
    }
    if (item.type === 'bool' && typeof value !== 'boolean') {
      return { key: item.key, message: `${item.label}应为开关值` };
    }
    if (
      (item.type === 'int' || item.type === 'float' || item.type === 'range') &&
      typeof value !== 'number'
    ) {
      return { key: item.key, message: `${item.label}应为数字` };
    }
    if (
      item.type === 'int' &&
      typeof value === 'number' &&
      !Number.isInteger(value)
    ) {
      return { key: item.key, message: `${item.label}应为整数` };
    }
    if (item.range && typeof value === 'number') {
      const [lo, hi] = item.range;
      if (value < lo || value > hi) {
        return {
          key: item.key,
          message: `${item.label}超出范围 [${lo}, ${hi}]`,
        };
      }
      if (item.step) {
        const k = (value - lo) / item.step;
        if (Math.abs(k - Math.round(k)) > 1e-9) {
          return {
            key: item.key,
            message: `${item.label}取值需为 ${item.step} 的倍数`,
          };
        }
      }
    }
    if (item.options && !item.options.includes(value as string)) {
      return { key: item.key, message: `${item.label}为非法选项` };
    }
  }
  return null;
}

// 2026-09-23 小欧 - 实施：模型能力脏判定 + 能力枚举单源词表（useSettings 合并与 SettingsPage 渲染共用，杜绝词表漂移）- 小欧-2026-09-23
// 2026-09-23 小欧 - 排序后比较(能力是集合语义; 手写 YAML 顺序与 UI 选项顺序不一致时 JSON 串比误判假脏,
//   只改本函数内部, 不动共享 sameValue——params 数组顺序敏感处仍需顺序比) - 小欧-2026-09-23
export const isCapsDirty = (caps: string[], baseline: string[]): boolean =>
  !sameValue([...caps].sort(), [...baseline].sort());

/**
 * 模型组待存项计数：参数值脏 + 删键 + 输入模态脏 + Provider 草稿键数。
 * 2026-11-09 小欧 - 自 useSettings.dirtyCount 与 SettingsPage.groupDirtyCount 两处同构算式抽出共用 — 小欧-2026-11-09
 */
export const modelDirtyCount = (m: ModelState): number => {
  const paramsDirty = Object.values(
    isDirty(m.params, m.baseline, m.envOverride)
  ).filter(Boolean).length;
  const capsDirty = isCapsDirty(m.inputModalities, m.inputModalitiesBaseline)
    ? 1
    : 0;
  return (
    paramsDirty +
    m.removedParams.length +
    capsDirty +
    Object.keys(m.providerDraft).length
  );
};

export const CAPABILITY_OPTIONS = [
  // 2026-09-24 小欧 - 文本 disabled 恒勾选（北京老陈拍板②：文本隐含默认，UI 不提供取消）- 小欧-2026-09-24
  { label: '文本', value: 'text', disabled: true },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '音频', value: 'audio' },
  // 2026-11-08 小欧: 枚举统一 pdf→file（与远端 /v1/models 的 input_modalities 值一致，pdf 是 file 子集）
  { label: '文件', value: 'file' },
];

// 2026-11-08 小欧: 输出模态徽标渲染源——
//   与 CAPABILITY_OPTIONS 共用字段值域 {text,image,file,video,audio}，只列可产出维度；
//   标签与输入侧同词（用户指定不带「生成」后缀）。
//   2026-11-09 小欧: 补 audio；text 补位成 4 枚齐显
//   (声明橙/未声明灰统一, 不再走未知值英文 Tag 通道)，唯一未知值只剩 file — 小欧-2026-11-09
export const OUTPUT_MODALITY_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '音频', value: 'audio' },
];

// 2026-11-09 小欧 - 输出模态中文标签单源(生效卡/模型库列/②输出行同源渲染, 未知名回退原词) — 小欧-2026-11-09
export const OUTPUT_MODALITY_LABEL: Readonly<Record<string, string>> =
  Object.fromEntries(OUTPUT_MODALITY_OPTIONS.map((o) => [o.value, o.label]));

// 2026-11-08 小欧 - 输出侧已知值集合（与 OUTPUT_MODALITY_OPTIONS 同源，未知值→只读灰标）
// 2026-11-09 小欧 - audio/text 入已知值(随徽标补位), 未知值域收窄至 file — 小欧-2026-11-09
export const KNOWN_OUTPUT_MODALITY_VALUES: ReadonlySet<string> = new Set(
  OUTPUT_MODALITY_OPTIONS.map((o) => o.value)
);

// 2026-09-24 小欧 - 状态归一：去重后恒含 'text'（防加载/切换时缺 text 致假脏；未知值原样保留）- 小欧-2026-09-24
export const normalizeCaps = (caps: string[]): string[] => {
  const list = [...new Set(caps)];
  if (!list.includes('text')) list.unshift('text');
  return list;
};

// 2026-09-24 小欧 - 保存转换：除 text 外无增强 → []（YAML 无此项=纯文本等价）；
//   有增强 → ['text', ...extras]（extras 含未知值，与已拍板语义一致）- 小欧-2026-09-24
export const capsForSave = (caps: string[]): string[] => {
  const extras = caps.filter((v) => v !== 'text');
  return extras.length ? ['text', ...extras] : [];
};

// 2026-09-23 小欧 - 已知能力值集合单源(与 CAPABILITY_OPTIONS 同源, 增枚举只改一处) - 小欧-2026-09-23
export const KNOWN_CAPABILITY_VALUES: ReadonlySet<string> = new Set(
  CAPABILITY_OPTIONS.map((o) => o.value)
);

// 2026-09-25 05:44:50 小健 - 模型参数默认范围单源（北京老陈选定前端兜底统一显示形态）：
//   AddParamForm 预设表与 ModelParams 渲染共用，杜绝两处范围漂移（如 context_length 上限 900000↔2000000）— 小健-2026-09-25
// 2026-11-01 小欧 - 键名统一 context_limit → context_length（与后端 yaml 真源/厂商通用名同名）— 小欧-2026-11-01
export const PARAM_DEFAULT_RANGES: Readonly<
  Record<string, { min: number; max: number }>
> = {
  context_length: { min: 1000, max: 2000000 },
  temperature: { min: 0, max: 2 },
  max_tokens: { min: 1, max: 100000 },
  top_p: { min: 0, max: 1 },
  seed: { min: 0, max: 999999 },
  frequency_penalty: { min: -2, max: 2 },
  presence_penalty: { min: -2, max: 2 },
};

// 2026-10-10 小欧 - PARAM_PRESETS 自 AddParamForm 整块迁移至此（与 PARAM_DEFAULT_RANGES 同数据层；AddParamForm/ModelModals 双消费，禁组件间数据互引） — 小欧-2026-10-10
/** 预定义参数表：从项目实际使用的模型参数中提取（v1.9：补 8 项 desc 字段，对齐设计 v1.2；显示顺序按北京老陈指定 - 小欧-2026-09-24） */
export const PARAM_PRESETS = [
  {
    key: 'context_length',
    type: 'number' as const,
    default: 262144,
    range: PARAM_DEFAULT_RANGES.context_length,
    label: '上下文窗口',
    desc: '上下文窗口上限(token)，超限裁剪旧轮；不设则用厂商声明值',
  },
  {
    key: 'temperature',
    type: 'number' as const,
    default: 0.7,
    range: PARAM_DEFAULT_RANGES.temperature,
    label: '温度',
    desc: '采样温度：0=完全确定，2=最随机',
  },
  {
    key: 'max_tokens',
    type: 'number' as const,
    default: 16384,
    range: PARAM_DEFAULT_RANGES.max_tokens,
    label: '最大输出Token', // 2026-11-01 小欧 原名「最大Token」语义含糊, 用户指令改为「最大输出Token」
    desc: '最大输出 token 数(输出封顶)，超长截断；与厂商声明/厂商级上限取最小',
  },
  {
    key: 'reasoning_effort',
    type: 'enum' as const,
    default: 'medium',
    // 全局兜底只放所有推理模型都支持的三个核心值；少数派值(none/minimal/xhigh/max)
    //   各模型支持不同，放全局会导致切模型时HTTP 400。模型私有值走 per-model param_options — 小欧-2026-10-24
    options: ['low', 'medium', 'high'],
    label: '推理深度',
    desc: '推理深度模式选择,，仅推理模型有效',
  },
  {
    key: 'enable_thinking',
    type: 'boolean' as const,
    default: true,
    label: '思考开关',
    desc: '开启后模型先思考再回答',
  },
  {
    key: 'thinking_budget',
    type: 'number' as const,
    default: 4000,
    range: { min: 512, max: 32000 },
    label: '思考预算',
    desc: '思考 token 上限，512~32000',
  },
  {
    key: 'top_p',
    type: 'number' as const,
    default: 1.0,
    range: PARAM_DEFAULT_RANGES.top_p,
    label: '核采样',
    desc: '只从概率最高的前 p 部分词里选词；1=全都不筛，调小=更保守、只留高概率词',
  },
  {
    key: 'seed',
    type: 'number' as const,
    default: null,
    range: PARAM_DEFAULT_RANGES.seed,
    label: '随机种子',
    desc: '数字本身无好坏：同一数字=每次结果固定不变，换一个数字=换一组新的随机结果；留空=每次都不固定',
  },
  {
    key: 'frequency_penalty',
    type: 'number' as const,
    default: 0,
    range: PARAM_DEFAULT_RANGES.frequency_penalty,
    label: '频次惩罚',
    desc: '正值减少重复（更多样），负值增加重复，0=不启用',
  },
  {
    key: 'presence_penalty',
    type: 'number' as const,
    default: 0,
    range: PARAM_DEFAULT_RANGES.presence_penalty,
    label: '存在惩罚',
    desc: '正值鼓励新话题，负值鼓励重复，0=不启用',
  },
];
