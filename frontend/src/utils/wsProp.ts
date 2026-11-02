/**
 * wsProp — 会话工作区属性(workspace_property)前端单一真源
 *
 * 创建: 2026-10-30 小欧
 * 编辑历史: 2026-10-30 小欧 - 提取为独立模块: 从 SessionWorkspacePanel 抽出,
 *   消除面板/历史页两处展示口径漂移(面板中文标签 vs 历史页机器值 [read_write])。
 * 编辑历史: 2026-11-02 小欧 - 删 PROP_COLORS: 属性标签去色后全仓无引用, 死代码清零 — 小欧-2026-11-02
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
