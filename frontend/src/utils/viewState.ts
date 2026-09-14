// 前端视图态判定纯函数：[36]前端3接收实时变量冗余收敛（方案A，北京老陈批准）
// 用途：RightViewer.isCurrentLive / PipelineRenderer.taskActive 判定逻辑提纯（SLAP），供渲染层消费与单测直测
// 作者：小欧  日期：2026-09-14
import type { TaskBadge } from '../features/chat/hooks/useTaskInfo';

/**
 * taskActive —— 任务活跃/等待圈显示判定（改动点④：删 streaming 条件）
 * highlightToolName 非空（HITL 确认高亮保活）或 badge 为 running/paused（实时/挂起保活）即真；
 * 唯一差异窗口 = startinfo 未到且无业务步骤（旧 streaming=true 窗口无 waiting 段/action-waiting 段，
 * 无 UI 载体），已由 C4 单测锁定（[36]§5.4-C）。
 * 作者：小欧  日期：2026-09-14
 */
export function computeTaskActive(
  highlightToolName: string | null | undefined,
  badge: TaskBadge | undefined
): boolean {
  return !!highlightToolName || badge === 'running' || badge === 'paused';
}

export interface ComputeIsCurrentLiveArgs {
  /** 当前选中任务（null=无选中/历史列表页） */
  activeTaskId: string | null;
  /** SSE 当前流水任务 */
  serverTaskId: string | null;
  /** liveSteps 已含 final 终态（12.6 早退切历史） */
  hasFinal: boolean;
  /** liveSteps 含任一业务步骤（thought-start/action/observation/chunk）——铁证兜底 */
  hasBusinessSteps: boolean;
  /** useTaskInfo 派生的实时徽标（startinfo 门无条件 running 后即首屏 live 权威信号） */
  liveBadge: TaskBadge;
}

/**
 * isCurrentLive —— 右侧栏是否展示实时任务（改动点③：删 receiving 条件）
 * match(activeTaskId→serverTaskId) 且 !hasFinal 且（有业务步骤 或 badge running/paused）即 true；
 * 删 receiving 后公证语义：startinfo 未到+无业务步骤窗口不再误判 live（[36]§3.3 双覆盖推出，B4 锁定）。
 * 作者：小欧  日期：2026-09-14
 */
export function computeIsCurrentLive({
  activeTaskId,
  serverTaskId,
  hasFinal,
  hasBusinessSteps,
  liveBadge,
}: ComputeIsCurrentLiveArgs): boolean {
  return (
    activeTaskId != null &&
    activeTaskId === serverTaskId &&
    !hasFinal &&
    (hasBusinessSteps || liveBadge === 'running' || liveBadge === 'paused')
  );
}
