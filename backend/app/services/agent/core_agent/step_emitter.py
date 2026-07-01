# -*- coding: utf-8 -*-
"""
step_emitter — 步骤发射和Task追踪

task检查由 run_sse_stream 层处理,本层不碰

Author: 小沈 - 2026-05-31
统一: 小健 - 2026-05-31 — 删除check_cancelled调用
"""

from typing import Any, Dict, Optional

from app.services.agent.steps import ErrorStep
from app.utils.logger import logger


class StepEmitter:
    """步骤发射和Task追踪(SRP) — 小健 2026-06-18 提取_get_tracker消除DRY"""

    def __init__(self, agent):
        self.agent = agent

    def emit(self, step) -> 'ReasoningStep':
        """记录步骤到agent.steps并返回Step对象"""
        self.agent.steps.append(step)
        return step

    def exit_with_error(self, step_count: int, error_type: str, error_message: str, recoverable: bool = False) -> 'ReasoningStep':
        """创建error_step,返回Step对象 — chendyg 2026-07-01: 不设状态，只创建 ErrorStep"""
        error_step = ErrorStep(
            step=step_count,
            error_type=error_type,
            error_message=error_message,
            recoverable=recoverable
        )
        return self.emit(error_step)

    def _get_tracker(self):
        """获取task_tracker和tracked_task_id — 小健 2026-06-18 DRY提取"""
        return (
            getattr(self.agent, '_task_tracker', None),
            getattr(self.agent, '_tracked_task_id', None),
        )

    def complete_task(self, success: bool):
        """Task追踪:完成任务记录"""
        task_tracker, tracked_task_id = self._get_tracker()
        if task_tracker and tracked_task_id:
            try:
                task_tracker.complete_task(tracked_task_id, success=success)
            except Exception as _e:
                # 【#41修复】logger.debug→warning，完成任务记录失败应有感知 — chendyg 2026-06-26
                logger.warning(f"[TaskTracker] 完成任务失败: {_e}")

    def record_operation(self, operation_type: str, *, status: Optional[str] = None, error: Optional[str] = None, **kwargs):
        """Task追踪:记录一次操作(调用方传入真实status和error)

        10规范: SRP — 只透传,不判断业务逻辑
        """
        task_tracker, tracked_task_id = self._get_tracker()
        if task_tracker and tracked_task_id:
            try:
                task_tracker.add_operation(
                    tracked_task_id, operation_type, status=status, error=error, **kwargs,
                )
            except Exception as _e:
                # 【#40修复】logger.debug→warning，操作记录失败应有感知 — chendyg 2026-06-26
                logger.warning(f"[TaskTracker] 记录操作失败: {_e}")
