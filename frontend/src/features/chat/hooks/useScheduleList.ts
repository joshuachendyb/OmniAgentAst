// 2026-11-18 商量 - 新建: 从当前任务步骤流派生「最新执行计划」
//   WHY: schedule 工具(一期方案A)是纯回显、不落库、不发 SSE 事件, 清单只存在于步骤流里;
//   且语义是「整体替换」—— 故最新一次落地的调用即当前清单。
//   由此获得: 无需新事件/新快照槽/新表, 切会话与历史回放随步骤自然恢复。
// 2026-11-18 商量 - 口径收口(三处, 均为真实链路实测驱动):
//   ① 任务边界即清单边界: 倒序扫描遇到 start/startinfo 立即停 —— 新任务第一秒不显示上一任务的清单,
//      本任务第一次 schedule 落地之前入口不存在。实时流 start 不入步骤(只填元信息帧), 实时侧的复位
//      由发新消息时的 clearSteps 承担, 此处是历史回放/备份恢复侧的同一条边界。
//   ② 认落地结果, 不认模型意图: 清单一律取观察步 tool_result[i].llm_data(action.params.items 经后端归一,
//      status.exec_code 标记成败); action.tools[i].params 是模型提交原文, 后端拒收(超 50 条/超 200 字/
//      status 非法)时它照样"长得像一份清单", 直接显示会出现"计划已生效"的假象。
//   ③ 失败不改清单: exec_code≠success 或被 HITL 拦下(无观察步)时跳过本次继续往前找 —— 与后端
//      "纯回显、失败什么都没改"同义; 而成功但清单为空 = 计划已清空, 就地收口不再往前找旧版本。
//   tool_result[i] 与 action.tools[i] 按下标严格对齐(后端 tool_runner 按下标回填), 故按同一个 i 取结果。
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
  /** 清单最后落地的那一步(排查用, 不参与展示) */
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

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

/** 归一化 items: 只收 content 非空 + status 合法的条目(与后端校验同口径) */
function normalizeItems(raw: unknown): ScheduleItem[] {
  if (!Array.isArray(raw)) return [];
  return raw.flatMap((it): ScheduleItem[] => {
    if (!isRecord(it)) return [];
    const { content, status } = it;
    if (typeof content !== 'string' || !isStatus(status)) return [];
    return [{ content, status }];
  });
}

/**
 * 某一次 schedule 调用的落地结果。
 * @returns undefined = 未落地(进行中 / 被拒 / 失败), null = 落地且清单为空(清空), 数组 = 落地清单
 */
function acceptedItems(
  steps: ExecutionStep[],
  actionIndex: number,
  toolIndex: number
): ScheduleItem[] | null | undefined {
  const action = steps[actionIndex];
  const after = steps.slice(actionIndex + 1);
  // 优先同 step 号的观察步, 兜底其后第一个观察步(后端按 step 号成对下发)
  const observation =
    after.find((s) => s.type === 'observation' && s.step === action.step) ??
    after.find((s) => s.type === 'observation');
  const results = observation?.tool_result;
  if (!Array.isArray(results)) return undefined;

  const entry = results[toolIndex];
  if (!isRecord(entry)) return undefined;
  const llm = isRecord(entry.llm_data) ? entry.llm_data : undefined;
  const status = isRecord(llm?.status) ? llm.status : undefined;
  if (status?.exec_code !== 'success') return undefined;

  const params = isRecord(llm?.action) ? llm.action.params : undefined;
  const items = normalizeItems(isRecord(params) ? params.items : undefined);
  return items.length ? items : null;
}

/** 取本任务最后一次**落地**的 schedule 清单; 无/已清空/未落地返回 null(入口隐藏) */
export function useScheduleList(
  steps: ExecutionStep[]
): ScheduleSnapshot | null {
  return useMemo(() => {
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      const step = steps[i];
      // 任务边界: 越过 start/startinfo 就不是本任务的计划了
      if (step.type === 'start' || step.type === 'startinfo') return null;
      if (step.type !== 'action') continue;
      const tools = step.tools ?? [];
      // 同一步内多次调用时后一次生效(整体替换语义)
      let toolIndex = -1;
      for (let k = tools.length - 1; k >= 0; k -= 1) {
        if (tools[k].tool === 'schedule') {
          toolIndex = k;
          break;
        }
      }
      if (toolIndex < 0) continue;

      const items = acceptedItems(steps, i, toolIndex);
      if (items === undefined) continue; // 未落地 → 上一份落地清单仍是当前态
      return items ? { items, step: step.step ?? 0 } : null;
    }
    return null;
  }, [steps]);
}
