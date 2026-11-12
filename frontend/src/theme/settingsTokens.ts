// 编辑历史: 2026-09-20 小强 - 新建：只增页级派生常量（pagePadding/rowHeight/labelWidth），复用 stepStyles + chatTokens，不建大表（7.9）
// 2026-09-21 小欧 - 实施：新增 settingsControl 控件宽度族，收敛散落硬编码宽度
// 2026-09-21 小欧 - v1.12 全文核查：新增 settingsModalWidth 弹窗宽度族，收敛规范一散落硬编码宽（设计文档 v1.12）
// 2026-09-22 小欧 - 统一控件宽度：inputWidth/secretWidth/selectWidth/inputNumberWidth/textareaWidth 统一为 240px；新增 inputNumberWidth/rangeNumberWidth 令牌；sliderWidth 160→140 配合 InputNumber 组合约 240；新增 apiKeyWidth/baseUrlWidth 360px - 小欧-2026-09-22
// 2026-09-22 小欧 - DRY+YAGNI 收口：行容器样式抽 settingsRowStyle、行 label 样式抽 settingsLabelStyle（SettingRow/ProviderConfig/ModelParams 三处复用，杜绝三套行样式漂移）；删 settingsRowLayout.gap 死配置（行容器已不用 gap，用量随布局对齐移除）- 小欧-2026-09-22
// 2026-09-23 小欧 - labelWidth 132→180（适配"频次惩罚 (frequency_penalty)"长标签）；控件宽度 inputWidth/secretWidth/selectWidth/inputNumberWidth/textareaWidth/modelSelectWidth/modelNameWidth 统一 240→180 - 小欧-2026-09-23
// 2026-09-23 小欧 - 十遍会审：settingsControl 增 actionBtnWidth:120（标题行三按钮等长，消 style={{width:120}}×3
//   重复字面量；标题操作按钮非 180 输入族，单列不混入 inputWidth）- 小欧-2026-09-23
// 2026-09-24 小欧 - modelNameWidth 180→280（北京老陈指示：模型下拉单独加宽，长模型名截断难读；
//   与 modelSelectWidth 不必等宽。超 280 的极端长名靠 AntD 悬停 title+下拉面板自适应兜底，不做动态宽防布局抖动）- 小欧-2026-09-24
// 2026-09-29 小欧 - 新增 filterSearchWidth:160：模型库筛选行搜索条专用宽度(北京老陈两次指正太长)，
//   不复用 searchWidth(那是右上角全局 SearchBox 的，两者密度诉求不同) - 小欧-2026-09-29
// 2026-10-05 22:16:38 小欧 - 新增 contextSelectWidth:96：模型库筛选行「上下文」下拉宽度令牌（原复用
//   modelSelectWidth:180 过长，北京老陈指令位置1尽量一行不折行），不散落硬编码 - 小欧-2026-10-05
// 编辑历史: 2026-10-11 00:18:37 小欧 - 设置页视觉密度统一: 新增 SETTINGS_CONTROL_HEIGHT=28/SETTINGS_RADIUS/SETTINGS_SWITCH 设计令牌(推导见注释: 不许拿 UI 库默认值当标准, 28=文字行盒20×1.4 取整) — 小欧-2026-10-11
// 2026-11-02 小欧 - settingsModalWidth 增 workspace:720（事项工作区面板档: 内容宽 672 → mono 14 约 80 字符/行） — 小欧-2026-11-02
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

/**
 * 控件高与圆角已迁出本文件 → 唯一真源 theme/controlScale.ts(文档[32])。
 *   迁出原因: ①控件高原先在本文件是「设置页专属 28」, 但控件规格是**全站**规格,
 *     聊天域/文件页/事项工作区面板都要用 → 留在本文件会造成跨域反向依赖(聊天域引设置页令牌);
 *   ②圆角同理(设置页逐页审计结论 4px 现由 controlScale 的 PAGE_RADIUS_FLAT 承载);
 *   ③控件高要随界面密度变化, 而密度是**运行时偏好**(改设置即时生效),
 *     常量表达不了 → 必须由 controlScale 的 token 构造器按密度解算。
 *   推导正文(行盒20/留白3/边框2、22px 文字底线、4px 圆角多数派依据)已一并迁入 controlScale.ts。
 */

/**
 * 开关 40x18 —— 2026-10-10 23:05 小欧（北京老陈指令："开关要瘦点扁一些"）
 *
 * 现状 44x22 + 1px 边框，放在 28px 的行里显得敦实，带边框更显"有框"。
 * 改为轨 40x18、钮 14、无边框：
 *   长宽比 44:22=2.0（近正方，显笨重） → 40:18=2.22（更扁长，显利落）；
 *   钮 14 与轨 18 留 2px 内边距，滑动行程 22px 仍可点可控。
 */
export const SETTINGS_SWITCH = { width: 40, height: 18, knob: 14 } as const;

export const settingsControl = {
  inputWidth: 180,
  secretWidth: 180,
  selectWidth: 180,
  inputNumberWidth: 180,
  sliderWidth: 140,
  rangeNumberWidth: 80,
  textareaWidth: 180,
  searchWidth: 260,
  // 模型库筛选行专用宽度（北京老陈两次指正：搜索条太长）：不复用 searchWidth(260)——
  // 那是右上角全局 SearchBox 的，两者密度诉求不同；160 与 inputWidth 同宽族 — 小欧 2026-09-29
  filterSearchWidth: 160,
  modelSelectWidth: 180,
  // 2026-10-05 22:16:38 小欧 - 模型库筛选行「上下文」下拉：原复用 modelSelectWidth=180 过长，
  //   北京老陈指令"位置1尽量一行不折行"下砍为 96，只容纳"≥ 32K"/"不限"量级的选项文案。
  contextSelectWidth: 96,
  modelNameWidth: 240,
  apiKeyWidth: 360,
  baseUrlWidth: 360,
  actionBtnWidth: 120,
} as const;

// 弹窗宽度四档（确认/通知=480、表单=520、工作区面板=720、展示=800）— 单点收口，禁散落硬编码
export const settingsModalWidth = {
  confirm: 480,
  form: 520,
  // 2026-11-02 小欧 - 工作区面板档 720: 内容宽 672 → mono 14 约 80 字符/行;
  //   不加宽(900 只多 25 字, 1280 屏压迫感陡增), 长路径靠行内折行完整显示。 — 小欧-2026-11-02
  workspace: 720,
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
