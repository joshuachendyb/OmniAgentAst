// 编辑历史: 2026-11-12 小欧 - 新建: 外观偏好(localStorage)读写**中立层单点**。
//   动因: 「阅读区字号 / 界面密度」两项设置此前只有写入端、没有读取端(写而不读),
//   且 localStorage 键与读侧函数原在 features/settings2 内 —— 而消费方是
//   components/markdown(中立层)与根 ConfigProvider, 跨 feature 反向依赖违仓库依赖方向铁规。
//   故整块上移本中立层: 键、读写、钳制规则、事件名唯一一处。
//
//   键值约定(localStorage 'omni.prefs.v1'):
//     fontSize: number  —— 阅读区字号(px), 合法档 12 / 14 / 16
//     density:  string  —— 界面密度, 'comfortable' | 'compact'
//   ⚠ 本地存储仅是**预览缓存**: 权威值在后端 settings registry(YAML),
//     设置页保存成功后由后端下发; 本地键让「改设置即时生效」无需等待网络往返。


// 2026-11-13 小欧 - 增「本地预应用」设置键单点表(LOCAL_PREF_SETTING_KEYS)与 localPrefKeyOf 推导:
//   写侧(useSettings)原用三元 `key === 'appearance.fontSize' ? 'fontSize' : 'density'` 硬编码映射,
//   新增第三个外观本地项时条件与映射两处必漏一处; 现键表与本键名定义同文件单点,
//   新增项只改键表一行, 本地键由前缀切片推导, 无第二处要同步。 — 小欧-2026-11-13


/** localStorage 预置键(唯一定义点) */
export const PREF_KEY = 'omni.prefs.v1';

/** 阅读区字号合法档(与全局字号阶梯一致, 不产生游离半档) */
export const APPEARANCE_FONT_SIZES = [12, 14, 16] as const;

/** 界面密度合法档 */
export const APPEARANCE_DENSITIES = ['comfortable', 'compact'] as const;

export type AppearanceDensity = (typeof APPEARANCE_DENSITIES)[number];


/**
 * 走「本地预应用」通道的设置键(唯一定义点)。
 *   写侧 useSettings.setValue 按本表判定是否写本地预览缓存;
 *   新增外观本地项只需在表内加一行, 本地键由 localPrefKeyOf 推导, 无第二处映射要同步。
 */
export const LOCAL_PREF_SETTING_KEYS = [
  'appearance.fontSize',
  'appearance.density',
] as const;

/** 设置键 → 本地偏好键('appearance.fontSize' → 'fontSize') */
export const localPrefKeyOf = (settingKey: string): string =>
  settingKey.slice('appearance.'.length);


/** 默认值 */
export const DEFAULT_APPEARANCE_FONT_SIZE = 14;
export const DEFAULT_APPEARANCE_DENSITY: AppearanceDensity = 'comfortable';

/**
 * 外观偏好变更广播事件名(唯一定义点)。
 *   语义: 本地预应用写入后派发 —— 同标签页即时生效靠它;
 *   跨标签页靠浏览器原生 'storage' 事件(同一 localStorage 键天然共享, 无冲突态)。
 */
export const APPEARANCE_PREFS_CHANGED_EVT = 'omni-appearance-prefs-changed';

/** 读取整份本地偏好(损坏时返回空对象, 不抛) */
export function readLocalPrefs(): Record<string, unknown> {
  try {
    return JSON.parse(localStorage.getItem(PREF_KEY) || '{}') as Record<
      string,
      unknown
    >;
  } catch {
    return {};
  }
}

/** 读取数值型偏好 */
export function readPrefNumber(key: string, fallback: number): number {
  const value = readLocalPrefs()[key];
  return typeof value === 'number' && Number.isFinite(value)
    ? value
    : fallback;
}

/** 读取字符串型偏好 */
export function readPrefString(key: string, fallback: string): string {
  const value = readLocalPrefs()[key];
  return typeof value === 'string' ? value : fallback;
}

/**
 * 字号钳制: ① 先夹紧到 [12, 16]; ② 再**向下吸附**到最近合法档(13→12、15→14、17/18→16)。
 *   取"向下"而非"就近"是**不放大**用户已表达的意图(选了 13 落到 12 比落到 14 更保守)。
 *   非数值/缺键 → 默认 14。
 */
export function clampFontSize(value: unknown): number {
  const min = APPEARANCE_FONT_SIZES[0];
  const max = APPEARANCE_FONT_SIZES[APPEARANCE_FONT_SIZES.length - 1];
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return DEFAULT_APPEARANCE_FONT_SIZE;
  }
  const clamped = Math.min(Math.max(value, min), max);
  // 2026-11-12 小欧 - 修类型缺陷: snapped 原被推断为字面量类型 12(APPEARANCE_FONT_SIZES[0]
  //   是 const 元组的首元素 → 类型为字面量 12), 循环里赋 14/16 即报错。
  //   显式标注为 number: 钳制结果本就是任意合法档, 不该被窄化。
  let snapped: number = min;
  for (const size of APPEARANCE_FONT_SIZES) {
    if (size <= clamped) snapped = size;
  }
  return snapped;
}

/** 密度钳制: 非法值 → 默认 comfortable */
export function clampDensity(value: unknown): AppearanceDensity {
  return APPEARANCE_DENSITIES.includes(value as AppearanceDensity)
    ? (value as AppearanceDensity)
    : DEFAULT_APPEARANCE_DENSITY;
}
