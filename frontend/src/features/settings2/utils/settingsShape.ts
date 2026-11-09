// 编辑历史: 2026-11-09 小欧 - 新建：设置键归属组查找与 secret 归一（原 useSettings 内联纯函数原样搬迁）— 小欧-2026-11-09
import type { SettingsState } from '../types';

// 2026-09-22 小欧 - DRY 收口：saveKeys 内两处手写「查 schema 键归属组」循环与 groupOfKey 重复 → 单纯函数（setState 回调内传最新 s.schema）
export function findGroupOfKey(
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
export function normalizeSecret(raw: unknown): unknown {
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
