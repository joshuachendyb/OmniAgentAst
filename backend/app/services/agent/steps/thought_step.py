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
        tool_params: Dict[str, Any] = None,
        thought: str = "",
        reasoning: str = "",
        timestamp: Optional[int] = None
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
