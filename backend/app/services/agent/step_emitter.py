
# -*- coding: utf-8 -*-
"""
step_emitter — 步骤发射和Task追踪

task检查由 run_sse_stream 层处理,本层不碰
编辑历史:
Author: 小沈 - 2026-05-31
2026-05-31 小健 — 删除check_cancelled调用
2026-07-16 小欧  统一TaskID: _get_tracker只返回tracker, complete_task/record_operation直读agent.task_id
2026-07-22 小欧  emit注入FinalStep._accumulated_usage: 自动从agent.accumulated_usage读取
2026-07-22 小欧  emit注入加is None防御: 仅外部未设置时才注入
"""

from typing import Any, Dict, Optional

from app.services.agent.steps import ErrorStep, FinalStep
from app.logger import logger


class StepEmitter:
    """步骤发射和Task追踪(SRP) — 小健 2026-06-18 提取_get_tracker消除DRY"""

    def __init__(self, agent):
        self.agent = agent

    def emit(self, step) -> 'ReasoningStep':
        """记录步骤到agent.steps并返回Step对象"""
        # FinalStep 自动注入累积消耗 — 小欧 2026-07-22
        # 仅当外部未设置时才注入，尊重外部传入值 — 小欧 2026-07-22
        if isinstance(step, FinalStep) and step._accumulated_usage is None:
            step._accumulated_usage = dict(self.agent.accumulated_usage)
        self.agent.steps.append(step)
        return step

    def exit_with_error(self, step_count: int, error_type: str, error_message: str) -> 'ReasoningStep':
        """创建error_step,返回Step对象 — chendyg 2026-07-01: 不设状态，只创建 ErrorStep；小欧 2026-07-13: 删 recoverable（终态由 ErrorStep 表示，不再用 flag 区分可恢复）"""
        error_step = ErrorStep(
            step=step_count,
            error_type=error_type,
            error_message=error_message
        )
        return self.emit(error_step)

    def _get_tracker(self):
        """获取task_tracker — 小健 2026-06-18 DRY提取, 任务ID直接用 agent.task_id — 小欧 2026-07-16"""
        return getattr(self.agent, '_task_tracker', None)

    def complete_task(self, success: bool):
        """Task追踪:完成任务记录 — 小欧 2026-07-16 删除 _tracked_task_id 别名, 直读 agent.task_id"""
        task_tracker = self._get_tracker()
        if task_tracker:
            try:
                task_tracker.complete_task(self.agent.task_id, success=success)
            except Exception as _e:
                logger.warning(f"[TaskTracker] 完成任务失败: {_e}")

    def record_operation(self, operation_type: str, *, status: Optional[str] = None, error: Optional[str] = None, **kwargs):
        """Task追踪:记录一次操作(调用方传入真实status和error)

        10规范: SRP — 只透传,不判断业务逻辑
        """
        task_tracker = self._get_tracker()
        if task_tracker:
            try:
                task_tracker.add_operation(
                    self.agent.task_id, operation_type, status=status, error=error, **kwargs,
                )
            except Exception as _e:
                logger.warning(f"[TaskTracker] 记录操作失败: {_e}")

