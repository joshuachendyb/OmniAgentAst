# -*- coding: utf-8 -*-
"""
Agent 执行结果类型定义

Author: 小沈 - 2026-03-21
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.agent.reasoning_steps import ReasoningStep


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
