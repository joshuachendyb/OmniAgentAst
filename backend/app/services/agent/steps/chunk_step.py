from typing import Any, Dict, Optional

from .base import ReasoningStep


class ChunkStep(ReasoningStep):
    """流式块步骤 - LLM生成的流式文本片段"""

    TYPE: str = "chunk"

    def __init__(
        self,
        step: int,
        content: str,
        is_reasoning: bool = False,
        thought: str = '',
        reasoning: str = '',
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._content = content
        self._is_reasoning = is_reasoning
        self._thought = thought
        self._reasoning = reasoning

    def get_content(self) -> str:
        return self._content

    @property
    def is_reasoning(self) -> bool:
        return self._is_reasoning

    @property
    def thought(self) -> str:
        return self._thought

    @property
    def reasoning(self) -> str:
        return self._reasoning

    def _extra_fields(self) -> Dict[str, Any]:
        extra: Dict[str, Any] = {
            "is_reasoning": self._is_reasoning,
        }
        if self._thought:
            extra["thought"] = self._thought
        if self._reasoning:
            extra["reasoning"] = self._reasoning
        return extra
