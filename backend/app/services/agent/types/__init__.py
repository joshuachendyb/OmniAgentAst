# -*- coding: utf-8 -*-
"""
Agent 类型定义

小沈 - 2026-06-08 删除Step类re-export(无调用者,统一从steps导入)
"""

from enum import Enum
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.agent.steps import ReasoningStep


class AgentStatus(Enum):
    """Agent状态 — 小沈 2026-03-21"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SUSPENDED = "suspended"


@dataclass
class AgentResult:
    """Agent执行结果"""
    success: bool
    message: str
    steps: List[ReasoningStep]
    total_steps: int
    task_id: Optional[str] = None
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


__all__ = [
    "AgentResult",
    "AgentStatus",
]
