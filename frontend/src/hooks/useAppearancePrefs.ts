// 编辑历史: 2026-11-12 小欧 - 新建: 外观偏好读取 hook(「阅读区字号」/「界面密度」的唯一读取点)。
//   动因: 两项设置此前**写而不读** —— 全仓无任何读取方, 滑块拖完界面不变;
//   本 hook 是读取侧单点, 供 ①Markdown 排版(base) ②Markdown 排版间隔(density)
//   ③根 ConfigProvider(控件高/尺寸) 三处消费, 杜绝多处各读一份。
//   事件订阅复用既有 SETTINGS_SAVED_EVT 机制(设置保存成功广播) + 本地偏好变更事件
//   (同标签页即时生效) + 浏览器原生 storage 事件(跨标签页同步)。
import { useCallback, useEffect, useState } from 'react';
import {
  APPEARANCE_PREFS_CHANGED_EVT,
  clampDensity,
  clampFontSize,
  readLocalPrefs,
  type AppearanceDensity,
} from '@/constants/appearancePrefs';
import { SETTINGS_SAVED_EVT } from '@/constants/settingsEvents';

export interface AppearancePrefs {
  /** 阅读区字号(px): 合法档 12 / 14 / 16 */
  fontSize: number;
  /** 界面密度: comfortable / compact */
  density: AppearanceDensity;
}

const DEFAULT_PREFS: AppearancePrefs = {
  fontSize: clampFontSize(undefined),
  density: clampDensity(undefined),
};

const readPrefs = (): AppearancePrefs => {
  const prefs = readLocalPrefs();
  return {
    fontSize: clampFontSize(prefs.fontSize),
    density: clampDensity(prefs.density),
  };
};

/**
 * 读取外观偏好并订阅变更。
 *   同标签页: 设置页改动后写 localStorage 并派发 APPEARANCE_PREFS_CHANGED_EVT → 立即生效;
 *   跨标签页: 浏览器 storage 事件(同一 localStorage 键天然共享, 无冲突态);
 *   保存成功: SETTINGS_SAVED_EVT → 重读(权威值以后端为准)。
 */
export const useAppearancePrefs = (): AppearancePrefs => {
  const [prefs, setPrefs] = useState<AppearancePrefs>(readPrefs);

  const refresh = useCallback(() => {
    setPrefs(readPrefs());
  }, []);

  useEffect(() => {
    refresh();
    window.addEventListener(APPEARANCE_PREFS_CHANGED_EVT, refresh);
    window.addEventListener(SETTINGS_SAVED_EVT, refresh);
    window.addEventListener('storage', refresh);
    return () => {
      window.removeEventListener(APPEARANCE_PREFS_CHANGED_EVT, refresh);
      window.removeEventListener(SETTINGS_SAVED_EVT, refresh);
      window.removeEventListener('storage', refresh);
    };
  }, [refresh]);

  return prefs;
};
