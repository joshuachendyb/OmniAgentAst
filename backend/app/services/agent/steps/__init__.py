# -*- coding: utf-8 -*-
"""
steps包 - ReAct Agent Step封装类

按SRP原则拆分,每个文件单一职责:
- base.py: ReasoningStep(ABC)
- meta_step.py: MetaStep (start/interrupted/paused/resumed/retrying/authorization_required)
- tool_step.py: ToolStep (action_tool + observation 合并)
- chunk_step.py: ChunkStep
- thought_step.py: ThoughtStep
- final_step.py: FinalStep
- error_step.py: ErrorStep

Author: 小沈
Date: 2026-04-15
Updated: 2026-06-13 重构合并：StartStep+IncidentStep→MetaStep, ActionToolStep+ObservationStep→ToolStep
"""

from .base import ReasoningStep
from .meta_step import MetaStep
from .tool_step import ToolStep
from .chunk_step import ChunkStep
from .thought_step import ThoughtStep
from .final_step import FinalStep
from .error_step import ErrorStep

from app.utils.time_utils import create_timestamp
from app.utils.counter_utils import create_step_counter

__all__ = [
    "ReasoningStep",
    "MetaStep",
    "ToolStep",
    "ChunkStep",
    "ThoughtStep",
    "FinalStep",
    "ErrorStep",
    "create_timestamp",
    "create_step_counter",
]
