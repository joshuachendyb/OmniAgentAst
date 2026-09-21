// 编辑历史: 2026-09-20 小强 - 新建：纯函数层（isDirty/clampToRange/validate，无 JSX，可单测，见 6.2/7.5）
import type { SettingSchemaItem } from '@/services/api/settings.api';

/** 模型 Tab 脏态：值与默认不一致且未被 env 接管（6.2）。 */
export function isDirty(
  params: Record<string, unknown>,
  defaults: Record<string, unknown>,
  env: Record<string, boolean>
): Record<string, boolean> {
  const out: Record<string, boolean> = {};
  Object.keys(params).forEach((key) => {
    out[key] = !env[key] && params[key] !== defaults[key];
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
    if (value === undefined || value === null) continue;
    if (item.type === 'bool' && typeof value !== 'boolean') {
      return { key: item.key, message: `${item.label}应为开关值` };
    }
    if (
      (item.type === 'int' || item.type === 'float' || item.type === 'range') &&
      typeof value !== 'number'
    ) {
      return { key: item.key, message: `${item.label}应为数字` };
    }
    if (item.range && typeof value === 'number') {
      const [lo, hi] = item.range;
      if (value < lo || value > hi) {
        return {
          key: item.key,
          message: `${item.label}超出范围 [${lo}, ${hi}]`,
        };
      }
    }
    if (item.options && !item.options.includes(value as string)) {
      return { key: item.key, message: `${item.label}为非法选项` };
    }
  }
  return null;
}
