from typing import Any, Dict, Optional

from .base import ReasoningStep


class ErrorStep(ReasoningStep):
    """错误步骤 - 表示执行过程中出现错误"""

    TYPE: str = "error"
    IS_DONE: bool = True

    def __init__(
        self,
        step: int,
        error_type: str,
        error_message: str,
        recoverable: bool = False,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._error_type = error_type
        self._error_message = error_message
        self._recoverable = recoverable
        self._model = model
        self._provider = provider

    def get_content(self) -> str:
        return self._error_message

    @property
    def error_type(self) -> str:
        return self._error_type

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def recoverable(self) -> bool:
        return self._recoverable

    def _extra_fields(self) -> Dict[str, Any]:
        extra: Dict[str, Any] = {
            "error_type": self._error_type,
            "error_message": self._error_message,
            "recoverable": self._recoverable,
        }
        if self._model:
            extra["model"] = self._model
        if self._provider:
            extra["provider"] = self._provider
        return extra
