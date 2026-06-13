from typing import Any, Dict, Optional

from .base import ReasoningStep


class MetaStep(ReasoningStep):
    """运行时元事件 - start/interrupted/paused/resumed/retrying/authorization_required"""

    def __init__(
        self,
        step: int,
        type: str,
        *,
        message: str = "",
        timestamp: Optional[int] = None,
        **kwargs: Any
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self.TYPE = type
        self._message = message
        self._kwargs = kwargs

    def get_content(self) -> str:
        return self._message

    def _extra_fields(self) -> Dict[str, Any]:
        return dict(self._kwargs)
