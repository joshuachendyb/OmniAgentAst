# -*- coding: utf-8 -*-
"""
步骤发射和Task追踪 — 从 base_react.py 拆出

复制来源: base_react.py 第427-491行 (_emit_step, _exit_with_error, _check_interrupt, _complete_tracked_task, record_operation)
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, Optional

from app.services.agent.steps import StepFactory, IncidentStep
from app.services.agent.types import AgentStatus
from app.utils.logger import logger


class StepEmitter:
    """步骤发射和Task追踪（SRP）"""

    def __init__(self, agent):
        self.agent = agent

    def emit(self, step) -> 'ReasoningStep':
        """复制自 base_react.py 第427-434行 — 记录步骤并返回Step对象"""
        self.agent.steps.append(step)
        return step

    def exit_with_error(self, step_count: int, error_type: str, error_message: str, recoverable: bool = False) -> 'ReasoningStep':
        """复制自 base_react.py 第436-449行 — 创建error_step并返回Step对象"""
        self.agent.status = AgentStatus.FAILED
        error_step = StepFactory.create_error_step(
            step=step_count,
            error_type=error_type,
            error_message=error_message,
            recoverable=recoverable
        )
        return self.emit(error_step)

    def check_interrupt(self, step_count: int, running_tasks: Optional[Dict[str, Any]] = None) -> Optional['IncidentStep']:
        """复制自 base_react.py 第451-469行 — 检查任务是否被中断"""
        task_id = getattr(self.agent, '_task_id', None) or getattr(self.agent, 'task_id', None)
        if not task_id or not running_tasks:
            return None
        task_data = running_tasks.get(task_id, {})
        if task_data.get("cancelled", False):
            return IncidentStep(
                step=step_count,
                incident_value='interrupted',
                message='用户取消了任务'
            )
        return None

    def complete_task(self, success: bool):
        """复制自 base_react.py 第471-479行 — Task追踪：完成任务记录"""
        task_tracker = getattr(self.agent, '_task_tracker', None)
        tracked_task_id = getattr(self.agent, '_tracked_task_id', None)
        if task_tracker and tracked_task_id:
            try:
                task_tracker.complete_task(tracked_task_id, success=success)
            except Exception as _e:
                logger.debug(f"[TaskTracker] 完成任务失败: {_e}")

    def record_operation(self, operation_type: str, **kwargs):
        """复制自 base_react.py 第481-491行 — Task追踪：记录一次操作"""
        task_tracker = getattr(self.agent, '_task_tracker', None)
        tracked_task_id = getattr(self.agent, '_tracked_task_id', None)
        if task_tracker and tracked_task_id:
            try:
                task_tracker.add_operation(
                    tracked_task_id, operation_type, **kwargs,
                )
            except Exception as _e:
                logger.debug(f"[TaskTracker] 记录操作失败: {_e}")
