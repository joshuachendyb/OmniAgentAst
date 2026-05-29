# -*- coding: utf-8 -*-
"""
steps包 - ReAct Agent Step封装类

按SRP原则拆分，每个文件单一职责：
- base.py: ReasoningStep(ABC) + ToolMixin
- chunk_step.py: ChunkStep
- thought_step.py: ThoughtStep
- action_step.py: ActionToolStep
- observation_step.py: ObservationStep
- final_step.py: FinalStep
- error_step.py: ErrorStep
- factory.py: StepFactory

Author: 小沈
Date: 2026-04-15
"""

from .base import ReasoningStep, ToolMixin
from .chunk_step import ChunkStep
from .thought_step import ThoughtStep
from .action_step import ActionToolStep
from .observation_step import ObservationStep
from .final_step import FinalStep
from .error_step import ErrorStep
from .factory import StepFactory

from app.utils.time_utils import create_timestamp, create_step_counter

__all__ = [
    "ReasoningStep",
    "ToolMixin",
    "ThoughtStep",
    "ActionToolStep",
    "ObservationStep",
    "ChunkStep",
    "FinalStep",
    "ErrorStep",
    "StepFactory",
    "create_timestamp",
    "create_step_counter",
]
