# -*- coding: utf-8 -*-
"""
Task 系统模块入口

导出：
- Registry: register_task, check_cancelled, check_paused, check_was_paused,
            set_cancelled, set_paused, set_resumed, set_was_paused,
            get_cancel_request_time, get_task_status, is_task_running,
            pop_task_field, get_task_field, cleanup_task, cleanup_expired_tasks
- cancel_task: 取消任务
- pause_task: 暂停任务
- resume_task: 恢复任务
- TaskTracker: 任务追踪器（DB持久化）
- TaskQueries: 查询服务

统一: 小健 - 2026-05-31
"""

from app.services.task.task_registry import (
    register_task,
    check_cancelled,
    check_paused,
    check_was_paused,
    set_cancelled,
    set_paused,
    set_resumed,
    set_was_paused,
    get_cancel_request_time,
    get_task_status,
    is_task_running,
    pop_task_field,
    get_task_field,
    cleanup_task,
    cleanup_expired_tasks,
)
from app.services.task.task_cancel import cancel_task
from app.services.task.task_pause import pause_task
from app.services.task.task_resume import resume_task
from app.services.task.task_cleanup import task_cleanup
from app.services.task.task_cancel_check import task_cancel_check_and_yield
from app.services.task.task_incident_check import (
    create_incident_data,
    task_interrupt_check,
    task_pause_check,
)
from app.services.task.task_tracker import TaskTracker, get_tracker
from app.services.task.task_queries import TaskQueries

__all__ = [
    # registry
    "register_task",
    "check_cancelled",
    "check_paused",
    "check_was_paused",
    "set_cancelled",
    "set_paused",
    "set_resumed",
    "set_was_paused",
    "get_cancel_request_time",
    "get_task_status",
    "is_task_running",
    "pop_task_field",
    "get_task_field",
    "cleanup_task",
    "cleanup_expired_tasks",
    # operations
    "cancel_task",
    "pause_task",
    "resume_task",
    "task_cleanup",
    "task_cancel_check_and_yield",
    "create_incident_data",
    "task_interrupt_check",
    "task_pause_check",
    # tracker/queries
    "get_tracker",
    "TaskTracker",
    "TaskQueries",
]
