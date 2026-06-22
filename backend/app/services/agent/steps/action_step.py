# -*- coding: utf-8 -*-
"""
ActionStep - 工具执行步骤（SRP拆分）

只负责action_tool模式，记录工具执行过程

小健 2026-06-22
"""
from typing import Any, Dict, Optional

from .base import ReasoningStep


class ActionStep(ReasoningStep):
    """工具执行步骤 - 只负责action_tool模式"""

    def __init__(
        self,
        step: int,
        tool_name: str,
        tool_params: Dict[str, Any],
        *,
        execution_status: str = "success",
        execution_result: Any = None,
        action_retry_count: int = 0,
        execution_time_ms: int = 0,
        timestamp: Optional[int] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self.TYPE = "action_tool"
        self._tool_name = tool_name
        self._tool_params = tool_params
        self._execution_status = execution_status
        self._execution_result = execution_result
        self._action_retry_count = action_retry_count
        self._execution_time_ms = execution_time_ms

    def get_content(self) -> str:
        return ""

    @property
    def is_error(self) -> bool:
        return self._execution_status == "error"

    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "tool_name": self._tool_name or "",
            "tool_params": self._tool_params or {},
            "execution_status": self._execution_status,
            "execution_result": self._execution_result,
            "action_retry_count": self._action_retry_count,
            "execution_time_ms": self._execution_time_ms,
        }
