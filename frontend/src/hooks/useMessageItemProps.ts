/**
 * useMessageItemProps Hook - 自定义比较函数
 *
 * 功能：为 MessageItem 组件提供 React.memo 自定义比较函数
 * 仅当实际影响渲染的props变化时才重新渲染，减少不必要的重渲染
 *
 * Phase 2 P1级优化 - MessageItem React.memo
 *
 * @author 小强
 * @version 1.0.0
 * @since 2026-04-12
 */

import type { ChatMessage } from '../services/api';
import type { ExecutionStep } from '../utils/sse';

/**
 * MessageItem 组件的 props 类型定义
 */
export interface MessageItemProps {
  message: ChatMessage & {
    id: string;
    timestamp: Date;
    executionSteps?: ExecutionStep[];
    model?: string;
    provider?: string;
    isStreaming?: boolean;
    isError?: boolean;
    display_name?: string;
    is_reasoning?: boolean;
    task_id?: string;
    errorType?: string;
    // 【小沈修改2026-04-16】删除details/stack/retryable，后端已删除
    errorMessage?: string;
    errorRetryAfter?: number;
    errorTimestamp?: string;
    // 【小沈添加2026-04-15】新增recoverable和context
    errorRecoverable?: boolean;
    errorContext?: {
      step?: number;
      model?: string;
      provider?: string;
      thought_content?: string;
    };
  };
  showExecution?: boolean;
  sessionId?: string | null;
  sessionTitle?: string | null;
}

/**
 * 比较函数：判断前后两次props是否相等
 * 仅比较影响渲染的字段，避免不必要的重渲染
 * 
 * @param prev - 上一次的props
 * @param next - 当前的props
 * @returns true表示props相等，组件不需要重新渲染
 */
export const areMessageItemPropsEqual = (
  prev: MessageItemProps,
  next: MessageItemProps
): boolean => {
  // 比较消息内容
  if (prev.message.content !== next.message.content) {
    return false;
  }
  
  // 比较消息角色
  if (prev.message.role !== next.message.role) {
    return false;
  }
  
  // 比较时间戳 - 支持Date对象、数字或字符串类型
  const getTimestamp = (ts: Date | string | number): number => {
    if (ts instanceof Date) {
      return ts.getTime();
    }
    if (typeof ts === 'string') {
      return new Date(ts).getTime();
    }
    return Number(ts);
  };
  const prevTime = getTimestamp(prev.message.timestamp);
  const nextTime = getTimestamp(next.message.timestamp);
  if (prevTime !== nextTime) {
    return false;
  }
  
  // 比较是否显示执行过程
  if (prev.showExecution !== next.showExecution) {
    return false;
  }
  
  // 比较会话ID
  if (prev.sessionId !== next.sessionId) {
    return false;
  }
  
  // 比较会话标题
  if (prev.sessionTitle !== next.sessionTitle) {
    return false;
  }

  // 【小沈修复 2026-04-13】比较 executionSteps - 支持实时显示AI步骤
  // 当后端实时推送 step 时，executionSteps 会变化，需要触发组件重新渲染
  const prevSteps = prev.message.executionSteps;
  const nextSteps = next.message.executionSteps;

  // 处理 undefined 和 null 情况
  const prevStepsArray = prevSteps || [];
  const nextStepsArray = nextSteps || [];

  // 比较长度 - 最简单的变化检测
  if (prevStepsArray.length !== nextStepsArray.length) {
    return false;
  }

  // 如果长度相同，也可以比较最后一项的content来确保step内容变化
  // （但实际上长度变化已经足够触发重新渲染）
  if (prevStepsArray.length > 0 && nextStepsArray.length > 0) {
    const prevLast = prevStepsArray[prevStepsArray.length - 1];
    const nextLast = nextStepsArray[nextStepsArray.length - 1];
    // 比较最后一步的content和type
    if (prevLast?.content !== nextLast?.content || prevLast?.type !== nextLast?.type) {
      return false;
    }
  }

  return true;
};

/**
 * 导出比较函数别名 - 便于直接使用
 */
export const messageItemCompare = areMessageItemPropsEqual;

export default areMessageItemPropsEqual;