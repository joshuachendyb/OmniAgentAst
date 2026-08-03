# 编辑历史:
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致

from typing import Any, Dict, Optional

from .base import ReasoningStep


class ThoughtStep(ReasoningStep):
    """思考步骤 - 表示正在思考并准备执行工具"""

    TYPE: str = "thought"

    def __init__(
        self,
        step: int,
        content: str,
        tool_name: str = "",
        tool_params: Optional[Dict[str, Any]] = None,
        thought: str = "",
        reasoning: str = "",
        timestamp: Optional[str] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._content = content
        self._thought = thought or content
        self._reasoning = reasoning
        self._tool_name = tool_name
        self._tool_params = tool_params or {}

    def get_content(self) -> str:
        return self._content

    @property
    def content(self) -> str:
        return self._content

    @property
    def thought(self) -> str:
        return self._thought

    @property
    def reasoning(self) -> str:
        return self._reasoning

    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "thought": self._thought,
            "reasoning": self._reasoning,
            "tool_name": self._tool_name,
            "tool_params": self._tool_params,
        }
