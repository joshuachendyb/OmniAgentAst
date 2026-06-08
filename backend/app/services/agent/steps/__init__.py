# -*- coding: utf-8 -*-
"""
steps包 - ReAct Agent Step封装类

【10大原则规范 2026--05-30 小健】
- SRP: 每个Step类型独立文件
- DRY: 直接调用Step构造函数,无需工厂类
- KISS: 每个文件一个类,职责单一
- YAGNI: 不提前引入抽象基类的额外方法
- 禁止向后兼容: reasoning_steps.py转发层已删除,统一从本包导入

【修复P0-4 2026-06-08 小沈】删除StepFactory过度设计,直接调用Step构造函数
StepFactory只是简单透传,没有额外逻辑,违反YAGNI原则

按SRP原则拆分,每个文件单一职责:
- base.py: ReasoningStep(ABC)
- chunk_step.py: ChunkStep
- thought_step.py: ThoughtStep
- action_step.py: ActionToolStep
- observation_step.py: ObservationStep
- final_step.py: FinalStep
- error_step.py: ErrorStep

Author: 小沈
Date: 2026-04-15
"""

from .base import ReasoningStep
from .chunk_step import ChunkStep
from .thought_step import ThoughtStep
from .action_step import ActionToolStep
from .observation_step import ObservationStep
from .final_step import FinalStep
from .error_step import ErrorStep
from .incident_step import IncidentStep
from .start_step import StartStep

from app.utils.time_utils import create_timestamp
from app.utils.counter_utils import create_step_counter

__all__ = [
    "ReasoningStep",
    "ThoughtStep",
    "ActionToolStep",
    "ObservationStep",
    "ChunkStep",
    "FinalStep",
    "ErrorStep",
    "IncidentStep",
    "StartStep",
    "create_timestamp",
    "create_step_counter",
]
