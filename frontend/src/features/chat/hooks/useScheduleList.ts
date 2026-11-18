// 2026-11-18 商量 - 新建: 从当前任务步骤流派生「最新执行计划」
//   WHY: schedule 工具(一期方案A)是纯回显、不落库、不发 SSE 事件, 清单只存在于 action 步骤的
//   tools[0].params.items 里; 且语义是「整体替换」—— 故最新一次 schedule 调用即当前清单。
//   由此获得: 无需新事件/新快照槽/新表, 切会话与历史回放随步骤自然恢复。
import { useMemo } from 'react';

import type { ExecutionStep } from '../../../types/execution';

export type ScheduleStatus =
  | 'pending'
  | 'in_progress'
  | 'completed'
  | 'cancelled';

export interface ScheduleItem {
  content: string;
  status: ScheduleStatus;
}

export interface ScheduleSnapshot {
  items: ScheduleItem[];
  /** 清单最后被更新的步骤号(展示「第 N 步更新」) */
  step: number;
}

const STATUSES: readonly ScheduleStatus[] = [
  'pending',
  'in_progress',
  'completed',
  'cancelled',
];

const isStatus = (v: unknown): v is ScheduleStatus =>
  STATUSES.includes(v as ScheduleStatus);

/** 取最后一次 schedule 调用作为当前清单; 清空/非法参数返回 null(图标隐藏) */
export function useScheduleList(
  steps: ExecutionStep[]
): ScheduleSnapshot | null {
  return useMemo(() => {
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      const step = steps[i];
      const call = step.tools?.find((t) => t.tool === 'schedule');
      if (!call) continue;
      const raw = call.params?.items;
      if (!Array.isArray(raw)) return null;
      const items = raw.flatMap((it): ScheduleItem[] => {
        if (!it || typeof it !== 'object') return [];
        const { content, status } = it as {
          content?: unknown;
          status?: unknown;
        };
        if (typeof content !== 'string' || !isStatus(status)) return [];
        return [{ content, status }];
      });
      // 最后一次调用即最终态: 空清单=计划已清空, 不再往前找旧版本
      return items.length ? { items, step: step.step ?? 0 } : null;
    }
    return null;
  }, [steps]);
}
