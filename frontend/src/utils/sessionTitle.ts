/**
 * 会话标题生成
 *
 * 编辑历史: 2026-09-30 14:30 小欧 - 新建：自 useChatSession 迁出（S4：纯文案拼装混在生命周期编排里违反 SRP）。
 *   原实现逐字迁入，业务逻辑与输出格式零变化。迁移自 NewChatContainer.tsx 第1351行 — 小欧-2026-09-30 14:30
 */

/**
 * generateNewSessionTitle - 按当前时间生成智能会话标题（如 "9月30日 下午会话 14:25"）
 */
export const generateNewSessionTitle = (): string => {
  const now = new Date();
  const hours = now.getHours();
  let timeOfDay = '';

  if (hours >= 5 && hours < 8) timeOfDay = '清晨';
  else if (hours >= 8 && hours < 12) timeOfDay = '上午';
  else if (hours >= 12 && hours < 14) timeOfDay = '午间';
  else if (hours >= 14 && hours < 18) timeOfDay = '下午';
  else if (hours >= 18 && hours < 21) timeOfDay = '晚间';
  else if (hours >= 21 && hours < 24) timeOfDay = '深夜';
  else timeOfDay = '深夜';

  const dateStr = `${now.getMonth() + 1}月${now.getDate()}日`;
  return `${dateStr} ${timeOfDay}会话 ${hours}:${now.getMinutes().toString().padStart(2, '0')}`;
};
