# -*- coding: utf-8 -*-
"""
ObservationStep - 观察步骤（SRP拆分）

只负责observation模式，接收完整的llm_data/tool_result/other_data

小健 2026-06-22
"""
from typing import Any, Dict, Optional

from .base import ReasoningStep


class ObservationStep(ReasoningStep):
    """观察步骤 - 只负责observation模式"""

    def __init__(
        self,
        step: int,
        *,
        llm_data: Optional[Dict[str, Any]] = None,
        tool_result: Any = None,
        other_data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self.TYPE = "observation"
        self._llm_data = llm_data or {}
        self._tool_result = tool_result
        self._other_data = other_data or {}

    def get_content(self) -> str:
        if self._llm_data and isinstance(self._llm_data, dict):
            return self._llm_data.get("summary", "")
        return ""

    def _extra_fields(self) -> Dict[str, Any]:
        obs: Dict[str, Any] = {}
        if self._llm_data:
            obs["llm_data"] = self._llm_data
        if self._tool_result is not None:
            obs["tool_result"] = self._tool_result
        if self._other_data:
            obs["other_data"] = self._other_data
        return {"observation": obs}