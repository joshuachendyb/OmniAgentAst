// 编辑历史: 2026-11-09 小欧 - 新建：外观本地预应用的 localStorage 预置键与读取单点（原 useSettings 内联常量搬迁）— 小欧-2026-11-09
export const PREF_KEY = 'omni.prefs.v1';

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
