# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
# 2026-08-18 小欧 - §10.3.3(3): ObservationStep 仅携带 tool_result 数组(每元素自包含);
#   删 llm_data/other_data/parallel_results 顶层字段; get_content 返回 ""(数据在 tool_result, 不重复发 content)

from typing import Any, Dict, List, Optional

from .base import ReasoningStep


class ObservationStep(ReasoningStep):
    """观察步骤 - 仅承载 tool_result 数组（§10.3.3(3)）"""

    TYPE: str = "observation"

    def __init__(
        self,
        step: int,
        *,
        tool_result: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[str] = None,
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._tool_result = tool_result or []

    def get_content(self) -> str:
        return ""

    @property
    def tool_result(self) -> List[Dict[str, Any]]:
        return self._tool_result

    def _extra_fields(self) -> Dict[str, Any]:
        if self._tool_result:
            return {"tool_result": self._tool_result}
        return {}
