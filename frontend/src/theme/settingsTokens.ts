// 编辑历史: 2026-09-20 小强 - 新建：只增页级派生常量（pagePadding/rowHeight/labelWidth），复用 stepStyles + chatTokens，不建大表（7.9）
import { Spacing, Radius } from '@/utils/stepStyles';

export const settingsSpacing = {
  ...Spacing,
  pagePadding: 16,
  rowHeight: 44,
  labelWidth: 132,
} as const;

export const settingsRadius = { ...Radius } as const;

export type SettingsSpacing = typeof settingsSpacing;
