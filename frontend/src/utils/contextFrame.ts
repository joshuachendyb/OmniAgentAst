/**
 * contextFrame —— history_context 帧读侧唯一真源
 *
 * 2026-10-10 小欧[20]: context_history 结构定稿(conv_context / inject_context 双分组),
 *   只认这定稿分组, 不做任何形状猜测或旧格式回落 —— 旧写法即 backward 双写法, 且会让类型
 *   层面骗人、逼出下游各自兼容。字段缺失就读出空, UI 如实显示空, 不补键不置空不伪造。
 *
 * @author 小欧
 * @date 2026-10-10
 */
import type {
  ConvContextFrame,
  ContextOverviewFrame,
  InjectContextFrame,
} from '@/types/sse';

/** 取「对话上下文」分组(定稿结构唯一来源); 缺失返回 null */
export const pickConv = (
  o: string | ContextOverviewFrame | null | undefined
): ConvContextFrame | null => {
  const frame = typeof o === 'object' && o !== null ? o : null;
  return frame?.conv_context ?? null;
};

/** 取「历史上下文」分组(定稿结构唯一来源); 缺失返回 null */
export const pickInject = (
  o: string | ContextOverviewFrame | null | undefined
): InjectContextFrame | null => {
  const frame = typeof o === 'object' && o !== null ? o : null;
  return frame?.inject_context ?? null;
};
