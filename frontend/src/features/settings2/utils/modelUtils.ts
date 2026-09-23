// 编辑历史: 2026-09-20 小强 - 新建：纯函数层（isDirty/clampToRange/validate，无 JSX，可单测，见 6.2/7.5）
// 2026-09-22 小强 - S7：validate 拒 null（原 null 与 undefined 一并 continue 放行，前端放行 → 落库被后端拒）；
//    null 仅当 schema 默认值本身为 null（可空项）时放行，其余类型返回「不能为空」
// 2026-09-22 小强 - 31候选 #3/#8：int 补 Number.isInteger（1.5 曾过前端、后端"应为整数"拒=契约漂移；
//    红测先红），range 补 step 倍数校验（12.5 过前端、对称后端 #8）
// 2026-09-22 小欧 - [62]P4 3.2(6) isDirty 对象深比较：补 sameValue（Object.is 快路径 + 双对象
//    JSON.stringify 深比），替换原 `!==`——对象/数组参数两个独立字面量内容相同但引用不同被判恒脏（[62] 3.2(6)）
// 2026-09-23 小欧 - 新增 isCapsDirty + CAPABILITY_OPTIONS（[65]§七，复用既有 sameValue 与 §7.2 单源词表）- 小欧-2026-09-23
// 2026-09-23 小欧 - [65]十遍会审：F2 isCapsDirty 排序后比（集合语义防手写 YAML 顺序假脏）+
//   F4 增 KNOWN_CAPABILITY_VALUES 单源（setCapabilities 每次重建 Set → 模块常量）- 小欧-2026-09-23
import type { SettingSchemaItem } from '@/services/api/settings.api';

/** [62]P4 3.2(6)：值深比较——同一引用/Object.is 相同立即真；双方对象则 JSON 深比；其余恒假。 */
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

/** 模型 Tab 脏态：值与默认不一致且未被 env 接管（6.2）。 */
export function isDirty(
  params: Record<string, unknown>,
  defaults: Record<string, unknown>,
  env: Record<string, boolean>
): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  Object.keys(params).forEach((key) => {
    out[key] = !env[key] && !sameValue(params[key], defaults[key]);
  });
  return out;
}

/** 超出新模型范围自动截断（7.5 范围截断 / 8.2.10 切换边界）。 */
export function clampToRange(
  value: unknown,
  range?: { min: number; max: number }
): unknown {
  if (typeof value !== 'number' || !range) return value;
  if (value < range.min) return range.min;
  if (value > range.max) return range.max;
  return value;
}

/** 保存前 schema 校验：返回首个错误 {key, message}，通过返回 null（7.5 首个错误控件红框+定位）。 */
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

// 2026-09-23 小欧 - [65]§七：模型能力脏判定 + 能力枚举单源词表（useSettings 合并与 SettingsPage 渲染共用，杜绝词表漂移）- 小欧-2026-09-23
// 2026-09-23 小欧 - [65]十遍会审 F2：排序后比较（能力是集合语义；手写 YAML 顺序与 UI 选项顺序不一致时
//   JSON 串比误判假脏。只改本函数内部，不动共享 sameValue——params 数组顺序敏感处仍需顺序比）- 小欧-2026-09-23
export const isCapsDirty = (caps: string[], baseline: string[]): boolean =>
  !sameValue([...caps].sort(), [...baseline].sort());

export const CAPABILITY_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: '图片', value: 'image' },
  { label: '视频', value: 'video' },
  { label: '音频', value: 'audio' },
  { label: 'PDF', value: 'pdf' },
];

// 2026-09-23 小欧 - [65]十遍会审 F4：已知能力值集合单源（setCapabilities 每次调用重建 Set → 模块级常量，
//   与 CAPABILITY_OPTIONS 同源，增枚举只改一处）- 小欧-2026-09-23
export const KNOWN_CAPABILITY_VALUES: ReadonlySet<string> = new Set(
  CAPABILITY_OPTIONS.map((o) => o.value)
);
