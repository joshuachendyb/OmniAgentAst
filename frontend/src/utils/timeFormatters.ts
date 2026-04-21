/**
 * Time Formatters - 时间格式化工具函数
 * 
 * @author 小沈
 * @version 1.0
 * @since 2026-04-20
 */

/**
 * 格式化时间为 HH:mm 格式
 */
export const formatTime = (date: Date | string | number): string => {
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    if (isNaN(dateObj.getTime())) {
      return "刚刚";
    }
    return dateObj.toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch (error) {
    return "刚刚";
  }
};

/**
 * 格式化相对时间（刚刚/X分钟前/X小时前/日期）
 */
export const formatRelativeTime = (date: Date | string | number): string => {
  try {
    const dateObj = date instanceof Date ? date : new Date(date);
    if (isNaN(dateObj.getTime())) {
      return "刚刚";
    }
    const now = new Date();
    const diff = now.getTime() - dateObj.getTime();
    const minutes = Math.floor(diff / 60000);
    
    if (minutes < 1) return "刚刚";
    if (minutes < 60) return `${minutes}分钟前`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}小时前`;
    return dateObj.toLocaleDateString("zh-CN");
  } catch (error) {
    return "刚刚";
  }
};