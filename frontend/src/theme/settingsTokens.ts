// 编辑历史: 2026-09-20 小强 - 新建：只增页级派生常量（pagePadding/rowHeight/labelWidth），复用 stepStyles + chatTokens，不建大表（7.9）
// 2026-09-21 小欧 - P0-6：新增 settingsControl 控件宽度族，收敛散落硬编码宽度（[58] P0-6）
// 2026-09-21 小欧 - v1.12 全文逐章核查：新增 settingsModalWidth 弹窗宽度族，收敛第六章 6.1 规范一散落硬编码宽（[58] v1.12）
import { Spacing, Radius } from '@/utils/stepStyles';

export const settingsSpacing = {
  ...Spacing,
  pagePadding: 16,
  rowHeight: 44,
  labelWidth: 132,
} as const;

export const settingsRadius = { ...Radius } as const;

export const settingsControl = {
  inputWidth: 260,
  secretWidth: 220,
  selectWidth: 200,
  sliderWidth: 160,
  textareaWidth: 320,
  searchWidth: 260,
  modelSelectWidth: 200,
  modelNameWidth: 240,
} as const;

// 第六章 6.1 规范一：弹窗宽度三档（确认/通知=480、表单=520、展示=800）— 单点收口，禁散落硬编码
export const settingsModalWidth = {
  confirm: 480,
  form: 520,
  display: 800,
} as const;

export type SettingsSpacing = typeof settingsSpacing;

export const settingsRowLayout = {
  display: 'flex',
  alignItems: 'center',
  minHeight: settingsSpacing.rowHeight,   // 44
  labelWidth: settingsSpacing.labelWidth, // 132
  gap: Spacing.MD,                        // 8
} as const;

export const settingsShadow = '0 -2px 8px rgba(0, 0, 0, 0.06)' as const;
