// 编辑历史: 2026-09-20 小强 - 新建：只增页级派生常量（pagePadding/rowHeight/labelWidth），复用 stepStyles + chatTokens，不建大表（7.9）
// 2026-09-21 小欧 - P0-6：新增 settingsControl 控件宽度族，收敛散落硬编码宽度（[58] P0-6）
// 2026-09-21 小欧 - v1.12 全文逐章核查：新增 settingsModalWidth 弹窗宽度族，收敛第六章 6.1 规范一散落硬编码宽（[58] v1.12）
// 2026-09-22 小欧 - 统一控件宽度：inputWidth/secretWidth/selectWidth/inputNumberWidth/textareaWidth 统一为 240px；新增 inputNumberWidth/rangeNumberWidth 令牌；sliderWidth 160→140 配合 InputNumber 组合约 240；新增 apiKeyWidth/baseUrlWidth 360px - 小欧-2026-09-22
import { Spacing, Radius } from '@/utils/stepStyles';

export const settingsSpacing = {
  ...Spacing,
  pagePadding: 16,
  rowHeight: 44,
  labelWidth: 132,
} as const;

export const settingsRadius = { ...Radius } as const;

export const settingsControl = {
  inputWidth: 240, // 统一输入框宽度
  secretWidth: 240, // 密码框对齐输入框
  selectWidth: 240, // 下拉框对齐输入框
  inputNumberWidth: 240, // 数字输入框对齐输入框
  sliderWidth: 140, // 滑块（配合 InputNumber 组合约 240）
  rangeNumberWidth: 80, // range 内 InputNumber（与 slider 组合）
  textareaWidth: 240, // 多行文本对齐统一宽度
  searchWidth: 260, // 搜索框独立
  modelSelectWidth: 240, // 模型选择器对齐
  modelNameWidth: 240, // 模型名对齐
  apiKeyWidth: 360, // API Key 输入框（值较长）
  baseUrlWidth: 360, // Base URL 输入框（值较长）
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
  minHeight: settingsSpacing.rowHeight, // 44
  labelWidth: settingsSpacing.labelWidth, // 132
  gap: Spacing.MD, // 8
} as const;

export const settingsShadow = '0 -2px 8px rgba(0, 0, 0, 0.06)' as const;
