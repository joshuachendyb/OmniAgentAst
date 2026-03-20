# -*- coding: utf-8 -*-
"""
Agent 类型定义

Author: 小沈 - 2026-03-21
"""

from enum import Enum
from .step_types import (
    ThoughtStep,
    ActionToolStep,
    ObservationStep,
    Step,
)
from .result_types import AgentResult


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


__all__ = [
    "ThoughtStep",
    "ActionToolStep",
    "ObservationStep",
    "Step",
    "AgentResult",
    "AgentStatus",
]
