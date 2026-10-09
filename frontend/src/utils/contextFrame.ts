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
  InjectContextFrame,
} from '@/types/sse';

/**
 * 帧载体最小结构契约 —— ContextOverviewFrame 与 ExecutionStep 都靠结构化子类型满足,
 *   故本真源一处即可服务两个载体(调用点无需各自转类型, 避免第二处形状猜测)。
 */
type FrameLike = {
  conv_context?: ConvContextFrame | null;
  inject_context?: InjectContextFrame | null;
} | null
  | undefined;

/** 取「对话上下文」分组(定稿结构唯一来源); 缺失或载体为 null 返回 null */
export const pickConv = (o: FrameLike): ConvContextFrame | null => {
  return o?.conv_context ?? null;
};

/** 取「历史上下文」分组(定稿结构唯一来源); 缺失或载体为 null 返回 null */
export const pickInject = (o: FrameLike): InjectContextFrame | null => {
  return o?.inject_context ?? null;
};
