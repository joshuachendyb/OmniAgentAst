// 编辑历史: 2026-09-20 小强 - 新建：只增页级派生常量（pagePadding/rowHeight/labelWidth），复用 stepStyles + chatTokens，不建大表（7.9）
// 2026-09-21 小欧 - P0-6：新增 settingsControl 控件宽度族，收敛散落硬编码宽度（[58] P0-6）
// 2026-09-21 小欧 - v1.12 全文逐章核查：新增 settingsModalWidth 弹窗宽度族，收敛第六章 6.1 规范一散落硬编码宽（[58] v1.12）
// 2026-09-22 小欧 - 统一控件宽度：inputWidth/secretWidth/selectWidth/inputNumberWidth/textareaWidth 统一为 240px；新增 inputNumberWidth/rangeNumberWidth 令牌；sliderWidth 160→140 配合 InputNumber 组合约 240；新增 apiKeyWidth/baseUrlWidth 360px - 小欧-2026-09-22
// 2026-09-22 小欧 - DRY+YAGNI 收口：行容器样式抽 settingsRowStyle、行 label 样式抽 settingsLabelStyle（SettingRow/ProviderConfig/ModelParams 三处复用，杜绝三套行样式漂移）；删 settingsRowLayout.gap 死配置（行容器已不用 gap，用量随布局对齐移除）- 小欧-2026-09-22
// 2026-09-23 小欧 - labelWidth 132→180（适配"频次惩罚 (frequency_penalty)"长标签）；控件宽度 inputWidth/secretWidth/selectWidth/inputNumberWidth/textareaWidth/modelSelectWidth/modelNameWidth 统一 240→180 - 小欧-2026-09-23
// 2026-09-23 小欧 - [65]十遍会审 F3：settingsControl 增 actionBtnWidth:120（②标题行三按钮等长，消 style={{width:120}}×3
//   重复字面量；标题操作按钮非 180 输入族，单列不混入 inputWidth）- 小欧-2026-09-23
// 2026-09-24 小欧 - modelNameWidth 180→280（北京老陈指示：模型下拉单独加宽，长模型名截断难读；
//   与 modelSelectWidth 不必等宽。超 280 的极端长名靠 AntD 悬停 title+下拉面板自适应兜底，不做动态宽防布局抖动）- 小欧-2026-09-24
import {
  Spacing,
  Radius,
  Colors,
  FontSize,
  FontWeight,
} from '@/utils/stepStyles';

export const settingsSpacing = {
  ...Spacing,
  pagePadding: 16,
  rowHeight: 44,
  labelWidth: 180,
} as const;

export const settingsRadius = { ...Radius } as const;

export const settingsControl = {
  inputWidth: 180,
  secretWidth: 180,
  selectWidth: 180,
  inputNumberWidth: 180,
  sliderWidth: 140,
  rangeNumberWidth: 80,
  textareaWidth: 180,
  searchWidth: 260,
  modelSelectWidth: 180,
  modelNameWidth: 240,
  apiKeyWidth: 360,
  baseUrlWidth: 360,
  actionBtnWidth: 120,
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
} as const;

// 2026-09-22 小欧 - DRY：行容器样式单点收口（SettingRow/ProviderConfig/ModelParams 三处复用，改样式只改这一处）
export const settingsRowStyle = {
  display: settingsRowLayout.display,
  alignItems: settingsRowLayout.alignItems,
  flexWrap: 'wrap',
  minHeight: settingsRowLayout.minHeight,
  borderBottom: `1px solid ${Colors.BORDER.LIGHT}`,
} as const;

// 2026-09-22 小欧 - DRY：行 label 样式单点收口（SettingRow/ProviderConfig/ModelParams 三处复用）
export const settingsLabelStyle = {
  width: settingsRowLayout.labelWidth,
  fontSize: FontSize.PRIMARY,
  fontWeight: FontWeight.REGULAR,
} as const;

export const settingsShadow = '0 -2px 8px rgba(0, 0, 0, 0.06)' as const;
