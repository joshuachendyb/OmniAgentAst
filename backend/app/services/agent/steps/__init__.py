# -*- coding: utf-8 -*-
"""
steps包 - ReAct Agent Step封装类

【10大原则规范 2026-05-30 小健】
- SRP: 每个Step类型独立文件 + 独立工厂文件
- DRY: StepFactory统一构建入口，消除各处重复dict构造
- KISS: 每个文件一个类，职责单一
- YAGNI: 不提前引入抽象基类的额外方法
- 禁止向后兼容: reasoning_steps.py转发层已删除，统一从本包导入

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
from .incident_step import IncidentStep
from .start_step import StartStep
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
    "IncidentStep",
    "StartStep",
    "StepFactory",
    "create_timestamp",
    "create_step_counter",
]
