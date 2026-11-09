// 编辑历史: 2026-11-09 小欧 - 新建：危险键词表与提示构建自 SettingsPage 组件体内移出（模块常量，免每次渲染重建）— 小欧-2026-11-09
// 2026-11-09 小欧 - 修正 confirm_dangerous_ops 键名错位致后果说明恒空, 文案按后端 notice 语义重写（原误写为拦截类）— 小欧-2026-11-09
export type GroupedValues = Record<string, Record<string, unknown>>;

/** 需二次确认的危险键（与后端 settings_registry 键名逐字一致，后端改名此处必须同步） */
export const DANGEROUS_KEYS: readonly string[] = [
  'security.hitl.enabled',
  'security.system.confirm_dangerous_ops',
];

export const DANGER_LABELS: Readonly<Record<string, string>> = {
  'security.hitl.enabled': '人工确认总开关',
  'security.system.confirm_dangerous_ops': '保存设置时二次确认',
};

/** 后果说明开/关两向都给：只给单向会在该方向变更时留空整块 */
export const DANGER_EFFECTS: Readonly<
  Record<string, { on: string[]; off: string[] }>
> = {
  'security.hitl.enabled': {
    on: [
      '开启后：写入/删除/命令等授权操作都会弹窗等人工确认，不会自动放行',
      '（代价是每次操作都要点一次确认）',
    ],
    off: [
      '关闭后：不再弹人工确认，按自动确认倒计时放行',
      '（磁盘根、项目根等删除硬防线仍生效，不受本开关影响）',
    ],
  },
  'security.system.confirm_dangerous_ops': {
    on: [
      '开启后：保存设置时多弹一次确认框，防误触提交',
      '（后端的安全拦截逻辑不依赖这个开关）',
    ],
    off: [
      '关闭后：保存设置不再二次确认，直接提交',
      '（后端的安全拦截逻辑不依赖这个开关，关它不会放松拦截）',
    ],
  },
};

/** 值可能是 bool 也可能是字符串 "true"（YAML 手写），两种都认 */
const readBool = (
  src: GroupedValues | undefined,
  group: string | null,
  key: string
): boolean => {
  const v = group ? src?.[group]?.[key] : undefined;
  return typeof v === 'boolean' ? v : v === 'true';
};

export const pickDangerDirtyKeys = (
  dirtyKeys: Record<string, boolean>
): string[] => DANGEROUS_KEYS.filter((k) => dirtyKeys[k]);

/** 变更清单：旧值取已保存基线，新值取脏键缓冲值（不回落到已落盘值） */
export const buildDangerChanges = (
  keys: string[],
  values: GroupedValues | undefined,
  baseline: GroupedValues | undefined,
  groupOfKey: (key: string) => string | null
): { label: string; from: string; to: string }[] =>
  keys.map((k) => ({
    label: DANGER_LABELS[k] ?? k,
    from: readBool(baseline, groupOfKey(k), k) ? '开启' : '关闭',
    to: readBool(values, groupOfKey(k), k) ? '开启' : '关闭',
  }));

/** 后果按变更分组：key = 变更中文名，与 buildDangerChanges 的 label 同源 */
export const buildDangerHints = (
  keys: string[],
  values: GroupedValues | undefined,
  groupOfKey: (key: string) => string | null
): Record<string, string[]> =>
  Object.fromEntries(
    keys.map((k) => {
      const eff = DANGER_EFFECTS[k];
      const lines = eff
        ? readBool(values, groupOfKey(k), k)
          ? eff.on
          : eff.off
        : [];
      return [DANGER_LABELS[k] ?? k, lines];
    })
  );
