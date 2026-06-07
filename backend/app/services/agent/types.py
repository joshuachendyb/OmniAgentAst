# -*- coding: utf-8 -*-
"""
Agent 类型定义

合并 agent_status.py + result_types.py - 小欧 2026-06-07

Author: 小沈 - 2026-03-21
"""
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class AgentStatus(Enum):
    """Agent状态"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    OBSERVING = "observing"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class AgentResult:
    """Agent执行结果"""
    success: bool
    message: str
    steps: List[Any]
    total_steps: int
    task_id: Optional[str] = None
    final_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


__all__ = ["AgentStatus", "AgentResult"]
