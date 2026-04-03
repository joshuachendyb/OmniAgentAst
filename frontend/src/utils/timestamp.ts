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
 * 
 * 【重要说明 - Bug追踪记录 - 2026-04-01 小强】
 * 
 * 问题描述：
 *   导出JSON时，timestamp 显示 "1970-01-01 08:00:02.026" 而不是正确时间
 * 
 * 根本原因：
 *   1. message.timestamp 在创建时是 Date 对象
 *   2. JSON.stringify() 存储到 sessionStorage 时，Date对象转成 ISO 字符串
 *      例如："2026-04-01T08:13:25.744Z"
 *   3. JSON.parse() 从 sessionStorage 恢复时，字符串不会自动变回 Date 对象
 *   4. formatTimestamp() 收到的是 ISO 字符串，不是 Date 对象
 * 
 * 错误代码问题：
 *   const timestamp = typeof ts === 'string' ? parseInt(ts, 10) : ts;
 *   
 *   当 ts = "2026-04-01T08:13:25.744Z" 时：
 *   - parseInt("2026-04-01T08:13:25.744Z", 10) = 2026（只取前导数字）
 *   - new Date(2026) = 1970-01-01 08:00:02.026（错误！）
 * 
 * 修复方案：
 *   使用 Date.parse() 替代 parseInt() 来正确解析 ISO 字符串
 *   - Date.parse("2026-04-01T08:13:25.744Z") = 1743478405744（正确毫秒时间戳）
 *   - new Date(1743478405744) = 2026-04-01 08:13:25.744（正确时间）
 * 
 * 如果此修复无效，请检查：
 *   1. message.timestamp 在 NewChatContainer.tsx 中是如何创建和存储的
 *   2. sessionStorage 恢复时是否正确转换回 Date 对象
 *   3. 导出时 message.timestamp 的实际类型（可用 console.log 打印）
 */
export const formatTimestamp = (ts: number | string | undefined): string => {
  if (!ts) return '';
  
  let timestamp: number;
  
  // 【修复Bug - 2026-04-01 小强】
  // 原因：sessionStorage 恢复后 ts 是 ISO 字符串（如 "2026-04-01T08:13:25.744Z"）
  // 问题：parseInt("2026-04-01...", 10) 只取前导数字 2026，导致 new Date(2026) = 1970年
  // 解决：使用 Date.parse() 正确解析 ISO 格式字符串为毫秒时间戳
  if (typeof ts === 'string') {
    const parsed = Date.parse(ts);
    timestamp = isNaN(parsed) ? 0 : parsed;
  } else {
    timestamp = ts;
  }
  
  if (isNaN(timestamp)) return '';
  const date = new Date(timestamp);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');
  const ms = String(date.getMilliseconds()).padStart(3, '0');
  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}.${ms}`;
};
