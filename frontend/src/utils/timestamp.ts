/**
 * 时间格式化工具函数
 * 
 * 提供统一的时间戳格式化功能
 * 
 * @author 小强
 * @version 1.0.0
 * @since 2026-03-17
 */

/**
 * 把时间戳转换为可读的北京时间
 * 格式：YYYY-MM-DD HH:mm:ss.SSS
 * 
 * @param ts - 时间戳（毫秒）或 ISO 字符串
 * @returns 格式化后的时间字符串
 * 
 * @example
 * formatTimestamp(1773720971439)
 * // => "2026-03-14 15:36:11.439"
 */
export const formatTimestamp = (ts: number | string | undefined): string => {
  if (!ts) return '';
  const date = new Date(typeof ts === 'string' ? parseInt(ts) : ts);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  const ms = String(date.getMilliseconds()).padStart(3, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${ms}`;
};
