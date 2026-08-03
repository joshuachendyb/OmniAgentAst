# -*- coding: utf-8 -*-
"""
AgentResult — Agent执行结果
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.agent.steps import ReasoningStep


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
