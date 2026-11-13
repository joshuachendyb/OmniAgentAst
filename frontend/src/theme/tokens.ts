// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: 抽会话页设计token, 收敛硬编码主色/字号/间距/圆角(对齐AntD5), 消除双主色跳变
// 2026-11-13 商量 - 字号双真源归一: fontSM/fontMD 改派生自 FontSize.SECONDARY/PRIMARY(stepStyles 7档阶梯,
//   2026-11-12 定为全站唯一字号真源), 本对象不再自持 12/14 数值; 消费方读值不变, 零视觉差
// 2026-11-13 商量 - radius/gap 同步改派生自 Radius.DEFAULT/Spacing.MD, 消除本文件内 6/8 裸数字;
//   顶部补铁律: 严禁拿 antd 默认规格当本项目标准 — 商量-2026-11-13
/**
 * chatTokens - 会话页 UI 收敛 token（边距白皮书 / Token 收敛）
 *
 * ★ 铁律(强制): 严禁使用 antd 的默认规格属性(控件高/内距/行高/圆角/焦点环)作为本项目标准;
 *   antd 仅作渲染实现。颜色/字号/间距/圆角的唯一真源是 utils/stepStyles.ts,
 *   控件规格的唯一真源是 theme/controlScale.ts, 本文件只做会话页语义别名, 不另立数值。
 *
 * 【小欧 2026-08-27 三堂会审】前端散落硬编码≥18处主色/字号/间距/圆角，抽常量统一：
 * - 主色对齐 AntD 5 默认 colorPrimary #1677ff（旧 #1890ff 为 v4 色，残留即跳变）
 * - 灰阶收敛 2 档：主文 #595959 / 次文 #8c8c8c（旧 #666/#999 统一回落）
 * - 间距主节奏 8（内层4半格）/ 圆角 6 / 边框 #f0f0f0
 *
 * @author 小欧
 * @date 2026-08-27
 */

import { FontSize, Radius, Spacing } from '@/utils/stepStyles';

export const chatTokens = {
  colorText: '#595959',
  colorTextSecondary: '#8c8c8c',
  colorBorder: '#f0f0f0',
  colorPrimary: '#1677ff',
  colorPrimaryBg: '#e6f4ff',
  colorSuccess: '#52c41a',
  colorError: '#ff4d4f',
  colorWarning: '#faad14',
  fontSM: FontSize.SECONDARY,
  fontMD: FontSize.PRIMARY,
  radius: Radius.DEFAULT,
  gap: Spacing.MD,
} as const;

export type ChatTokens = typeof chatTokens;
