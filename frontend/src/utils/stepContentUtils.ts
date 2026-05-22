/**
 * 步骤内容文本处理工具 - 统一管理步骤内容的文本转换和格式化
 *
 * 功能：将字面\n转为真换行符，支持后续扩展（打字机效果等）
 * 设计原则：thought/content/response共享formatStepContent，reasoning单独formatReasoningContent
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-05-01
 */

export const formatStepContent = (text: string | undefined | null): string => {
  if (!text) return '';
  return String(text).replace(/\\n/g, '\n');
};

export const formatReasoningContent = (text: string | undefined | null): string => {
  if (!text) return '';
  return String(text).replace(/\\n/g, '\n');
};
