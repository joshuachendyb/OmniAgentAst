/**
 * Time Formatters - 时间格式化工具函数
 *
 * @author 小沈
 * @version 1.0
 * @since 2026-04-20
 */

import { parseTimeSafe } from './timestamp';

// 编辑历史: 2026-08-27 小欧 - 修复B12: 未来时间(diff<0)不再显示为"刚刚", 返回日期
// 编辑历史: 2026-08-28 小沈 - 修复review-bugs#7: 统一调用parseTimeSafe, 非法值返回null由调用方fallback - 小沈-2026-08-28

/**
 * 格式化时间为 HH:mm 格式
 */
export const formatTime = (date: Date | string | number): string => {
  const dateObj = parseTimeSafe(date);
  if (!dateObj) return '';
  return dateObj.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  });
};

/**
 * 格式化相对时间（刚刚/X分钟前/X小时前/日期）
 */
export const formatRelativeTime = (date: Date | string | number): string => {
  const dateObj = parseTimeSafe(date);
  if (!dateObj) return '';
  const now = new Date();
  const diff = now.getTime() - dateObj.getTime();
  // 2026-08-27 小欧 修复B12: 未来时间(diff<0)按未来处理, 不显示为"刚刚"
  if (diff < 0) return dateObj.toLocaleDateString('zh-CN');
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) return '刚刚';
  if (minutes < 60) return `${minutes}分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}小时前`;
  return dateObj.toLocaleDateString('zh-CN');
};
