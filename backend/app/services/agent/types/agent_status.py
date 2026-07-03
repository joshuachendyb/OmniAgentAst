# -*- coding: utf-8 -*-
"""
AgentStatus 枚举定义

Author: 小沈 - 2026-03-21
"""

from enum import Enum


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"
