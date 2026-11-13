// 编辑历史: 2026-11-12 小欧 - 新建: 全站控件刻度**唯一真源**(控件高三档 + 圆角三档 + 页面级圆角预设)。
//
//   【铁律 —— 北京老陈 2026-10-10「不许拿 UI 库默认值当标准」的落地】
//   ★ 严禁使用 antd 的默认规格属性(控件高/内距/行高/圆角/焦点环/密度)★
//   任何"和 antd 缺省一致"都不是理由 —— antd 的默认值只是库作者的工程折中, 不是本项目的设计标准。
//   控件规格一律取**本项目标准**, 严禁沿用任何 UI 库的缺省值, 更严禁依赖库的派生公式:
//     antd v5 的 seed 缺省 = controlHeight 32 / borderRadius 6;
//     它的派生公式 controlHeightSM = base × 0.75、controlHeightLG = base × 1.25
//     会算出 21px / 35px 这类**不在 4px 网格上**的值, 其中 21px 还低于本项目
//     「文字不被压」的 22px 硬底线(见下方推导) —— 故本文件把三档**显式钉死**,
//     antd 只作渲染实现, 不参与任何规格推导。
//   配套规范: 文档 doc-11月优化/[32] 全站控件刻度统一与界面密度设计。
//
//   【控件高推导 —— 与 theme/settingsTokens.ts 原 28 同一套推导, 此处补全三档】
//     本项目控件内字号 = 14px。14px 在 UI 内的可读行高下限为 1.43×, 即文字行盒最小 20px;
//     再 + 上下边框各 1px = 22px —— 此为「文字不被压」的硬底线, 任何档位不得低于它。
//     small  24 = 行盒 20 + 上下留白各 1 + 边框 2  (密集工具条控件; 1px 留白是可接受下沿)
//     normal 28 = 行盒 20 + 上下留白各 3 + 边框 2  ← 项目标准值(明确不采纳库缺省 32)
//     large  32 = 行盒 24 + 上下留白各 3 + 边框 2  (16px 大字, 行盒 24)
//     三档构成 24 / 28 / 32 **等差 4px** 阶梯; 不引入 26 这类半档(与[31]删 13px 半档同源纪律)。
//
//   【密度语义 —— 只切「哪一档生效」, 不是「在某个基线上减几 px」】
//     舒适 comfortable = { small 24, normal 28, large 32 }
//     紧凑 compact     = { small 24, normal 24, large 28 }   (整档下移一档)
//     small 档**两档同值**: 已贴 22px 底线, 再降即压字; 且流水线内唯一的 antd 控件
//     (ParamsPanel 的 Segmented size="small") 高度恒为 controlHeightSM,
//     故密度天然不触碰流水线(文档[31] §4.4 作用范围表: 密度绝不触碰流水线)。
//     密度**只改控件高**: 字号恒 14(不动 fontSize/fontSizeSM/fontSizeLG),
//     严禁用 antd 的 componentSize 承载密度 —— 它会连带把 Select/DatePicker 的
//     字号切到 fontSizeSM(=12), 违[31] §7.1 第 5 项与 §7.2 第 4 项。
//
//   【圆角推导】沿用本项目 Colors/Spacing 刻度自带的 Radius 阶梯(utils/stepStyles.ts):
//     全局 6(Radius.DEFAULT) / 小控件 4(Radius.SM) / 浮层容器 8(Radius.LG);
//     borderRadiusXS 全局 2 / 页面级 1 是 antd 按 base 派生的结果, 恰与现状渲染同值,
//     本项目阶梯无对应项 → 不显式下发(不引入游离值)。
//     设置页/文件页/事项工作区面板另有逐页审计结论(控件圆角全档 4, 见 PAGE_RADIUS_FLAT),
//     属页面级决策, 须**显式补发 borderRadiusLG: 4**, 否则会继承全局 8 导致弹窗圆角 4→8。

import type { AppearanceDensity } from '@/constants/appearancePrefs';
import { Radius, Spacing } from '@/utils/stepStyles';

/**
 * 小号档控件高(px) —— **两档密度同值**, 原因见文件头推导:
 *   已贴「文字不被压」22px 底线, 再降即压字; 同时保证流水线像素零变化。
 */
export const CONTROL_HEIGHT_SM = 24;

/** 控件高三档 × 两档密度(px) —— 全站唯一定义点 */
export const CONTROL_HEIGHT = {
  comfortable: { small: CONTROL_HEIGHT_SM, normal: 28, large: 32 },
  compact: { small: CONTROL_HEIGHT_SM, normal: 24, large: 28 },
} as const;

/** 全局圆角三档(px) —— 取自本项目 Radius 阶梯, 非库缺省 */
export const CONTROL_RADIUS = {
  sm: Radius.SM, // 4
  normal: Radius.DEFAULT, // 6
  lg: Radius.LG, // 8
} as const;

/**
 * 页面级圆角全档 4 —— 老陈 2026-10-10 设置页逐页审计结论:
 *   同页并存 4px 与 6px 两种圆角 = 不是设计, 是缺省结果的堆积 → 全页统一 4。
 *   适用范围: 设置页 / 文件页 / 事项工作区面板(逐页审计同源)。
 */
export const PAGE_RADIUS_FLAT = {
  normal: Radius.SM,
  sm: Radius.SM,
  lg: Radius.SM,
} as const;

/**
 * 控件内距(px) —— 本项目标准, **严禁沿用 UI 库缺省**(antd 的 4px 11px 属库折中, 非本项目设计值)。
 *   TEXT_INPUT_X = 12: 文本输入类控件(Input/TextArea)的水平内距, 取 4px 网格标准档 Spacing.LG。
 *     框内文字/占位层/表单控件左缘统一由本值决定, 不再出现 11px 这类库缺省残留。
 *   TEXT_INPUT_Y_TIGHT = 2: 多行文本输入(空态)的上下内距, 取「字体行盒已含呼吸 + 圆角不压首行」的视觉下限;
 *     该值刻意小于 4px 网格, 属本项目显式例外, 目的为压缩空态高度, 非照抄库缺省。
 */
export const CONTROL_PADDING = {
  TEXT_INPUT_X: Spacing.LG,
  TEXT_INPUT_Y_TIGHT: 2,
} as const;

/**
 * 焦点环规格(px) —— 本项目标准, 与 antd 的 outline 缺省无关。
 *   WIDTH 2: 环线粗细, 保证在浅底上清晰可辨。
 *   OFFSET 2: 环线到控件边缘的间距, 使其落在圆角外侧、不压住 1px 边框。
 */
export const FOCUS_RING_WIDTH = 2;
export const FOCUS_RING_OFFSET = 2;

/** 该密度下的控件高三档 */
export const controlHeightByDensity = (
  density: AppearanceDensity
): (typeof CONTROL_HEIGHT)[AppearanceDensity] => CONTROL_HEIGHT[density];

/**
 * 根 ConfigProvider 的控件规格 token —— 控件高 3 档 + 圆角 3 档**全部显式下发**。
 *   不下发即等于让 antd 用 0.75×/1.25× 去派生(21/35 这类非网格值), 故必须写全。
 *   不下发 borderRadiusXS: 全局 base 6 下其派生值 2 与现状渲染同值, 无项目阶梯对应项。
 */
export const controlScaleTokens = (
  density: AppearanceDensity
): Record<string, number> => {
  const height = CONTROL_HEIGHT[density];
  return {
    controlHeight: height.normal,
    controlHeightSM: height.small,
    controlHeightLG: height.large,
    borderRadius: CONTROL_RADIUS.normal,
    borderRadiusSM: CONTROL_RADIUS.sm,
    borderRadiusLG: CONTROL_RADIUS.lg,
  };
};

/**
 * 页面级控件规格 token —— 设置页/文件页/事项工作区面板统一入口。
 *   controlHeightSM **与 normal 同值**: 老陈 2026-10-10 定案 ——
 *   实测「检查服务」(size=small) 24px 与「保存全部」(默认) 28px 并排时底边不齐,
 *   本页 size="small" 均无「更紧凑」的独立诉求 → 全页按钮只留一个高度。
 *   控件高三档全部显式: 不发 controlHeightLG 会继承根的全局值, 等于把本页的
 *   派生档位交回 antd 的 0.75×/1.25× 公式(28 → 21/35 这类非 4px 网格值)。
 *   圆角三档全发 4: 继承全局 8 会让设置页弹窗/下拉圆角 4→8(现状为 4)。
 */
export const pageControlTokens = (
  density: AppearanceDensity
): Record<string, number> => {
  const height = CONTROL_HEIGHT[density];
  return {
    controlHeight: height.normal,
    controlHeightSM: height.normal,
    controlHeightLG: height.large,
    borderRadius: PAGE_RADIUS_FLAT.normal,
    borderRadiusSM: PAGE_RADIUS_FLAT.sm,
    borderRadiusLG: PAGE_RADIUS_FLAT.lg,
  };
};
