/**
 * useTaskInfo - 任务信息条数据派生 Hook
 *
 * 【小欧 2026-08-26 8.6 / R1 修正】
 * - B2：输入=全量 executionSteps（final 是业务类型，此前只喂 meta 流导致
 *   completed/failed 徽标成死分支）+ metaFrames（统计类通知，见 8.4.14）；
 *   注：error 事件不入 executionSteps（8.4.5），失败徽标由 final.outcome='failed'
 *   与 onError→liveErrorText 双通道承载，下方 case 'error' 仅作遗留库数据防御。
 * - B28：卡死阈值显式常量 STUCK_RATIO=3（规范仅述"≫"，默认 3 待北京老陈定案）；
 * - B33：badge 仅在收到 startinfo 帧后才亮"执行中"，连接建立不再提前亮灯。
 * 纯 SSE 收流、无前端发起请求（4.8.4.4）；会话累计 token 不在此（三分归位②）。
 *
 * @author 小欧
 * @date 2026-08-26
 */

import { useMemo } from 'react';
import type { ExecutionStep, TaskMetaFrames } from '../../utils/sse';

/** 卡死预警阈值：llm_call_count ≥ step_count×STUCK_RATIO 视为疑似死循环（待定案） */
export const STUCK_RATIO = 3;

export interface ProcessEvent {
  kind: 'started' | 'paused' | 'resumed' | 'retrying';
  text: string;
  time: number;
}

export type TaskBadge =
  | 'idle'
  | 'running'
  | 'paused'
  | 'completed'
  | 'failed'
  | 'cancelled';

export const useTaskInfo = (
  steps: ExecutionStep[],
  frames: TaskMetaFrames,
  receiving: boolean
) => {
  return useMemo(() => {
    let badge: TaskBadge = 'idle';
    const processEvents: ProcessEvent[] = [];

    // ① 过程状态条事件 + 终态徽标（全量步骤流内派生）
    // 【小欧 2026-08-26 18:49 修正】startinfo 不进 executionSteps（8.4.3 只写 metaFrames），
    // 不可从 steps.find 搜索；改用 frames.startInfo 判断。
    const hasStartInfo = frames.startInfo !== null;
    for (const s of steps) {
      switch (s.type) {
        case 'paused':
          badge = 'paused';
          processEvents.push({
            kind: 'paused',
            text: s.content || '任务已暂停',
            time: s.timestamp,
          });
          break;
        case 'resumed':
          badge = 'running';
          processEvents.push({
            kind: 'resumed',
            text: s.content || '任务已恢复',
            time: s.timestamp,
          });
          break;
        case 'retrying':
          processEvents.push({
            kind: 'retrying',
            text: s.content || '正在重试',
            time: s.timestamp,
          });
          break;
        case 'final':
          if (s.outcome === 'cancelled') badge = 'cancelled';
          else if (s.outcome === 'failed') badge = 'failed';
          else badge = 'completed';
          break;
        case 'error':
          // 防御遗留库数据（error 现不入 executionSteps，见 8.4.5）；实时失败走 final.outcome
          badge = 'failed';
          break;
        default:
          break;
      }
    }

    // ② startinfo 帧 -> "任务已开始"过程条首行 + 执行中徽标（B33：有帧才亮）
    // startinfo 仅存在于 metaFrames（8.4.3），时间戳取 start 事件的 startTimestamp
    if (hasStartInfo && badge === 'idle')
      badge = receiving ? 'running' : 'idle';
    if (hasStartInfo) {
      processEvents.unshift({
        kind: 'started',
        text: '任务已开始',
        time: frames.startTimestamp || Date.now(),
      });
    }

    const stats = frames.stats;
    const llmCallCount = stats?.llm_call_count ?? 0;
    const stepCount = stats?.step_count ?? 0;
    const stuckWarning =
      llmCallCount > 0 &&
      stepCount > 0 &&
      llmCallCount >= stepCount * STUCK_RATIO;

    return {
      badge,
      elapsedSec: stats?.duration ?? 0,
      stepCount,
      llmCallCount,
      retryCount: stats?.retry_count ?? 0,
      usage: frames.usage,
      overview: frames.contextOverview,
      truncatedTip: frames.truncated?.content ?? null,
      processEvents: processEvents.slice(-20).reverse(), // 新事件插顶，保留最近20条
      stuckWarning,
    };
  }, [steps, frames, receiving]);
};
