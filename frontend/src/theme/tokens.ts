// 编辑历史: 2026-08-27 小欧 - 三堂会审P1-1: 抽会话页设计token, 收敛硬编码主色/字号/间距/圆角(对齐AntD5), 消除双主色跳变
/**
 * chatTokens - 会话页 UI 收敛 token（8.2 边距白皮书 / P1-1 Token 收敛）
 *
 * 【小欧 2026-08-27 三堂会审】前端散落硬编码≥18处主色/字号/间距/圆角，抽常量统一：
 * - 主色对齐 AntD 5 默认 colorPrimary #1677ff（旧 #1890ff 为 v4 色，残留即跳变）
 * - 灰阶收敛 2 档：主文 #595959 / 次文 #8c8c8c（旧 #666/#999 统一回落）
 * - 间距主节奏 8（内层4半格）/ 圆角 6 / 边框 #f0f0f0
 *
 * @author 小欧
 * @date 2026-08-27
 */

export const chatTokens = {
  colorText: '#595959',
  colorTextSecondary: '#8c8c8c',
  colorBorder: '#f0f0f0',
  colorPrimary: '#1677ff',
  colorPrimaryBg: '#e6f4ff',
  colorSuccess: '#52c41a',
  colorError: '#ff4d4f',
  colorWarning: '#faad14',
  fontSM: 12,
  fontMD: 14,
  radius: 6,
  gap: 8,
} as const;

export type ChatTokens = typeof chatTokens;
