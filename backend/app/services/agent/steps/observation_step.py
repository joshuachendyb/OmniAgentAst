# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
"""
ObservationStep - 观察步骤（SRP拆分）

只负责observation模式，接收完整的llm_data/tool_result/other_data
parallel_results: 并行tool call时保留每个call的完整数据映射 — 小健 2026-06-25

2026-07-08 北京老陈: llm_data改为始终存列表（单或多工具统一），索引与parallel_results 1:1
小健 2026-06-22
"""
from typing import Any, Dict, List, Optional, Union

from .base import ReasoningStep


class ObservationStep(ReasoningStep):
    """观察步骤 - 只负责observation模式"""

    def __init__(
        self,
        step: int,
        *,
        llm_data: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
        tool_result: Any = None,
        other_data: Optional[Dict[str, Any]] = None,
        parallel_results: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[str] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self.TYPE = "observation"
        # 始终存列表，索引与parallel_results 1:1 — 北京老陈 2026-07-08
        if llm_data is None:
            self._llm_data = []
        elif isinstance(llm_data, list):
            self._llm_data = llm_data
        else:
            self._llm_data = [llm_data]  # 兼容单条dict
        self._tool_result = tool_result
        self._other_data = other_data or {}
        self._parallel_results = parallel_results

    def get_content(self) -> str:
        if self._llm_data and isinstance(self._llm_data, list):
            parts = [d.get("summary", "") for d in self._llm_data if isinstance(d, dict)]
            return parts[0] if len(parts) == 1 else "\n\n".join(parts)
        return ""

    def _extra_fields(self) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        if self._llm_data:
            extra["llm_data"] = self._llm_data
        if self._tool_result is not None:
            extra["tool_result"] = self._tool_result
        if self._other_data:
            extra["other_data"] = self._other_data
        if self._parallel_results:
            extra["parallel_results"] = self._parallel_results
        return extra