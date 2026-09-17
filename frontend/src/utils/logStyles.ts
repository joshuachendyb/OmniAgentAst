/**
 * 聊天日志工具函数
 *
 * 统一管理NewChatContainer中的console.log样式
 *
 * @author 小新
 * @version 1.0.0
 * @since 2026-03-13
 */

// 日志样式常量
export const LOG_STYLES = {
  // 成功/完成的蓝色样式（原来黄色看不清楚，改成蓝色）
  success: 'color: #0066CC; font-weight: bold; font-size: 14px;',
  successSmall: 'color: #0066CC; font-size: 12px;',

  // 调试/信息的蓝色样式
  debug: 'color: blue; font-weight: bold; font-size: 14px;',
  debugSmall: 'color: blue; font-size: 12px;',

  // 用户消息的红色样式
  user: 'color: red; font-weight: bold; font-size: 14px;',
  userSmall: 'color: red; font-size: 12px;',

  // 错误样式
  error: 'color: #cf1322; font-weight: bold; font-size: 14px;',
  errorSmall: 'color: #cf1322; font-size: 12px;',

  // 通用样式
  info: 'color: #666; font-size: 12px;',
};

/**
 * 打印带样式的日志头
 */
export const logHeader = (title: string, style: string = LOG_STYLES.debug) => {
  console.log(`%c┌───── ${title} START ─────`, style);
};

/**
 * 打印带样式的日志尾
 */
export const logFooter = (title: string, style: string = LOG_STYLES.debug) => {
  console.log(`%c└───── ${title} END ─────`, style);
};

/**
 * 打印带样式的日志内容
 */
export const logContent = (
  content: string,
  style: string = LOG_STYLES.debugSmall
) => {
  console.log(`%c│ ${content}`, style);
};

/**
 * 打印分隔线
 */
export const logDivider = (style: string = LOG_STYLES.debug) => {
  console.log(`%c├────────────────────────────────`, style);
};

// ============================================================
// 特定场景的日志函数
// ============================================================

/**
 * AI响应完成的日志
 */
export const logAIComplete = (responseLength: number) => {
  console.log(`✅ AI响应完成, 长度: ${responseLength}`);
};

/**
 * AI响应错误的日志
 */
export const logAIError = (errorMessage: string) => {
  console.error(`❌ AI响应错误: ${errorMessage}`);
};

/**
 * 用户发送消息的日志
 */
export const logUserSend = (content: string) => {
  const truncated = content.substring(0, 100);
  console.log(`🚀 用户发送: ${truncated}`);
};

/**
 * 历史消息加载的日志
 */
export const logHistoryLoad = (
  messageCount: number,
  fromCache: boolean = false
) => {
  const source = fromCache ? '缓存' : '数据库';
  console.log(`📥 ${source}加载: ${messageCount} 条消息`);
};

/**
 * 调试日志（开发模式）
 */
export const logDebug = (label: string, data?: unknown) => {
  if (import.meta.env.DEV) {
    console.log(`🔍 [${label}]`, data);
  }
};

/**
 * 错误日志
 */
export const logError = (label: string, error: unknown) => {
  console.error(`🔴 [${label}]`, error);
};
