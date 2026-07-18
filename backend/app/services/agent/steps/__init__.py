# -*- coding: utf-8 -*-
"""
steps包 - ReAct Agent Step封装类

按SRP原则拆分,每个文件单一职责:
- base.py: ReasoningStep(ABC) + MetaStep (start/cancelled/paused/resumed/retrying/authorization_required)
- action_step.py: ActionStep (action_tool模式)
- observation_step.py: ObservationStep (observation模式)
- chunk_step.py: ChunkStep
- thought_step.py: ThoughtStep
- final_step.py: FinalStep
- error_step.py: ErrorStep

Author: 小沈
Date: 2026-04-15
Updated: 2026-06-22 SRP拆分：ActionStep(action_tool) + ObservationStep(observation)
"""

from .base import ReasoningStep, MetaStep, create_step_counter
from .action_step import ActionStep
from .observation_step import ObservationStep
from .chunk_step import ChunkStep
from .thought_step import ThoughtStep
from .final_step import FinalStep
from .error_step import ErrorStep

__all__ = [
    "ReasoningStep",
    "MetaStep",
    "ActionStep",
    "ObservationStep",
    "ChunkStep",
    "ThoughtStep",
    "FinalStep",
    "ErrorStep",
    "create_step_counter",
]
