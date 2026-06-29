# -*- coding: utf-8 -*-
"""
AgentStatus 枚举定义

Author: 小沈 - 2026-03-21
Extracted from __init__.py by: 小欧 - 2026-05-27
"""

from enum import Enum


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"

    CANCELLED = "cancelled"  # 【Bug17修复】chendyg 2026-06-26: 任务被取消，区分于COMPLETED
