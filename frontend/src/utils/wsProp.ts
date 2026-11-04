/**
 * wsProp — 会话工作区属性(workspace_property)前端单一真源
 *
 * 创建: 2026-10-30 小欧
 * 编辑历史: 2026-10-30 小欧 - 提取为独立模块: 从 SessionWorkspacePanel 抽出,
 *   消除面板/历史页两处展示口径漂移(面板中文标签 vs 历史页机器值 [read_write])。
 * 编辑历史: 2026-11-02 小欧 - 删 PROP_COLORS: 属性标签去色后全仓无引用, 死代码清零 — 小欧-2026-11-02
 * 编辑历史: 2026-11-02 小欧 - 纳入自定义属性持久化(load/save/options, 含形态校验)与 wsPathKey
 *   (路径比较键): 二者原散在面板组件内, 归位属性域单一真源 — 小欧-2026-11-02
 *
 * 后端对应: app/services/chat/workspace_service.py 的 ws_prop_value/ws_prop_label,
 *   前端只负责展示与入库前归一, 权限判定一律由后端安全矩阵裁决。
 */

/** 属性三档预设：机器值 + 中文标签 */
export const WS_PROP_PRESETS = [
  { value: 'read_only', label: '读取工作区' },
  { value: 'read_write', label: '读写工作区' },
  { value: 'write', label: '写工作区' },
] as const;

export const DEFAULT_WS_PROP = 'read_write';

/** 属性展示唯一源：机器值 → 中文标签；自定义原样；缺失 → 读写工作区 */
export function wsPropLabel(raw?: string | null): string {
  const v = (raw || '').trim();
  if (!v) return '读写工作区';
  const hit = WS_PROP_PRESETS.find((p) => p.value === v || p.label === v);
  return hit ? hit.label : v;
}

/** 属性入库唯一源：缺失/空 → read_write；中文标签 → 机器值；自定义原样 */
export function wsPropValue(raw?: string | null): string {
  const v = (raw || '').trim();
  if (!v) return DEFAULT_WS_PROP;
  if (WS_PROP_PRESETS.some((p) => p.value === v)) return v;
  const byLabel = WS_PROP_PRESETS.find((p) => p.label === v);
  return byLabel ? byLabel.value : v;
}

/** 自定义属性持久化：localStorage 唯一读写处（面板只管 UI，不再碰存储细节） — 小欧-2026-11-02 */
const CUSTOM_PROPS_KEY = 'ws_custom_props';
const MAX_CUSTOM_PROPS = 16;

/** 读自定义属性：非数组/非字符串项一律过滤（脏数据降级空，绝不让渲染抛错） — 小欧-2026-11-02 */
export function loadCustomProps(): string[] {
  try {
    const raw = localStorage.getItem(CUSTOM_PROPS_KEY);
    if (!raw) return [];
    const arr: unknown = JSON.parse(raw);
    return Array.isArray(arr)
      ? arr.filter((x): x is string => typeof x === 'string' && !!x.trim())
      : [];
  } catch {
    return [];
  }
}

/** 存自定义属性（预设不存、已有不存、FIFO 淘汰、写失败静默） — 小欧-2026-11-02 */
export function saveCustomProp(prop: string): void {
  if (WS_PROP_PRESETS.some((p) => p.value === prop || p.label === prop)) return;
  const list = loadCustomProps();
  if (list.includes(prop)) return;
  list.push(prop);
  if (list.length > MAX_CUSTOM_PROPS) list.shift();
  try {
    localStorage.setItem(CUSTOM_PROPS_KEY, JSON.stringify(list));
  } catch {
    /* 隐私模式/配额满：静默降级，不影响主流程 — 小欧-2026-11-02 */
  }
}

/** AutoComplete 选项：预设 + 自定义（saveCustomProp 保证自定义不含预设，此处不再重复过滤） — 小欧-2026-11-02 */
export function wsPropOptions(): { value: string; label: string }[] {
  return [
    ...WS_PROP_PRESETS.map((p) => ({ value: p.value, label: p.label })),
    ...loadCustomProps().map((c) => ({ value: c, label: c })),
  ];
}

/** 路径比较键：对齐后端「Windows 大小写不敏感 + 去尾分隔符 + 正斜杠归一」口径。
 *  仅用于前端配对（问题行/默认标记），不做路径解析——解析与安全判定一律交后端 — 小欧-2026-11-02 */
export function wsPathKey(p: string): string {
  return p.trim().replace(/\//g, '\\').replace(/\\+$/, '').toLowerCase();
}
