// 编辑历史: 2026-08-26 小欧 - 8.4/8.10 实施: 权威过滤业务内容步骤, meta/统计类归信息条(4.4.4)
// 编辑历史: 2026-08-27 小欧 - 三堂会审修复: META_STEP_TYPES补入cancelled(6)/取消thought-start特判统一二分(7)
// 编辑历史: 2026-08-27 小欧 - 三堂会审8.6: ExecutionStep导入改从types/execution(断类型环)
/**
 * pipeline 分流工具
 *
 * 【小欧 2026-08-26 8.4/8.10】4.4.4 权威过滤：查看区只渲染业务内容步骤
 * chunk/thought/action/observation/final/error；meta 小事件(start/paused/resumed/
 * retrying)与统计类(usage/stats/final_stats/context_overview/truncated/startinfo)
 * 归任务信息条。thought-start 是 ThinkingStream 的起始信号标记，保留在业务流。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import type { ExecutionStep } from '../../../types/execution';

export const META_STEP_TYPES = [
  'start',
  'startinfo',
  'paused',
  'resumed',
  'retrying',
  'usage',
  'stats',
  'final_stats',
  'context_overview',
  'truncated',
  'cancelled',
] as const;

export const isBusinessStep = (s: ExecutionStep): boolean =>
  !(META_STEP_TYPES as readonly string[]).includes(s.type);

export interface SplitResult {
  /** 查看区流水线输入：业务步骤 + thought-start 标记，按到达顺序 */
  business: ExecutionStep[];
  /** 任务信息条输入：全部 meta 步骤 */
  meta: ExecutionStep[];
}

export const splitSteps = (steps: ExecutionStep[]): SplitResult => {
  const business: ExecutionStep[] = [];
  const meta: ExecutionStep[] = [];
  for (const s of steps) {
    // 2026-08-27 小欧 三堂会审: 取消thought-start特判, 统一按业务/元步骤二分
    if (isBusinessStep(s)) business.push(s);
    else meta.push(s);
  }
  return { business, meta };
};
