# -*- coding: utf-8 -*-
"""
steps包 - ReAct Agent Step封装类

按SRP原则拆分,每个文件单一职责:
- base.py: ReasoningStep(ABC) + MetaStep (start/cancelled/paused/resumed/retrying/authorization_required)
- action_step.py: ActionStep (action模式)
- observation_step.py: ObservationStep (observation模式)
- chunk_step.py: ChunkStep
- thought_step.py: ThoughtStep (仅落库)
- thought_start_step.py: ThoughtStartStep (仅SSE实时信号)
- start_content_step.py: StartStep (start完整任务契约, 落库, content=context_summary)
- final_step.py: FinalStep
- error_step.py: ErrorStep

Author: 小沈
Date: 2026-04-15
Updated: 2026-06-22 SRP拆分：ActionStep(action_tool) + ObservationStep(observation)
Updated: 2026-08-18 小欧 - §10.3: 废action_tool改action, 新增ThoughtStartStep, ObservationStep仅tool_result, FinalStep删冗余加reasoning
"""

from .base import ReasoningStep, MetaStep
from .action_step import ActionStep
from .observation_step import ObservationStep
from .chunk_step import ChunkStep
from .thought_step import ThoughtStep
from .thought_start_step import ThoughtStartStep   # 2026-08-18 小欧 新增
from .start_content_step import StartStep           # 2026-08-18 小欧 新增(§10.1.2 P7 start 拆双)
from .final_step import FinalStep
from .error_step import ErrorStep

__all__ = [
    "ReasoningStep",
    "MetaStep",
    "ActionStep",
    "ObservationStep",
    "ChunkStep",
    "ThoughtStep",
    "ThoughtStartStep",
    "StartStep",
    "FinalStep",
    "ErrorStep",
]
