# -*- coding: utf-8 -*-
"""
task_context — 任务ID ContextVar

从 utils/message_id_tracker.py 拆分
小欧 2026-07-10
"""

from contextvars import ContextVar
from typing import Optional

_current_task_id: ContextVar[Optional[str]] = ContextVar("tool_task_id", default=None)
