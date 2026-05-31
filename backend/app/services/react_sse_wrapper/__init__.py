# -*- coding: utf-8 -*-
"""
react_sse_wrapper — 从 react_sse_wrapper.py 拆出的职责

- task_registry: 任务注册和管理（核心）
 - task_cancel: 取消任务
 - task_pause: 暂停任务
 - task_resume: 恢复任务
 - task_cleanup: 清理过期任务
- _core: SSE流式生成主流程
"""

from app.services.react_sse_wrapper.task_registry import running_tasks_lock, running_tasks
from app.services.react_sse_wrapper.task_cancel import cancel_task
from app.services.react_sse_wrapper.task_pause import pause_task
from app.services.react_sse_wrapper.task_resume import resume_task
from app.services.react_sse_wrapper.task_cleanup import cleanup_expired_tasks
from app.services.react_sse_wrapper.react_sse_wrapper import (
    generate_sse_stream,
    generate_sse_stream_with_retry,
)

__all__ = [
    "running_tasks_lock",
    "running_tasks",
    "cancel_task",
    "pause_task",
    "resume_task",
    "cleanup_expired_tasks",
    "generate_sse_stream",
    "generate_sse_stream_with_retry",
]
