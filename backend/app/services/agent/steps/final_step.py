from typing import Any, Dict, Optional

from .base import ReasoningStep


class FinalStep(ReasoningStep):
    """最终回答步骤 - Agent完成,最终给出答案"""

    TYPE: str = "final"
    IS_DONE: bool = True

    def __init__(
        self,
        step: int,
        response: str,
        thought: str = "",
        model: Optional[str] = None,
        provider: Optional[str] = None,
        is_finished: bool = True,
        display_name: Optional[str] = None,
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._response = response
        self._thought = thought
        self._model = model
        self._provider = provider
        self._is_finished = is_finished
        self._display_name = display_name or (f"{provider} ({model})" if provider and model else provider or model or "")

    def get_content(self) -> str:
        return self._response

    @property
    def response(self) -> str:
        return self._response

    @property
    def thought(self) -> str:
        return self._thought

    @property
    def model(self) -> Optional[str]:
        return self._model

    @property
    def provider(self) -> Optional[str]:
        return self._provider

    @property
    def is_finished(self) -> bool:
        return self._is_finished

    @property
    def display_name(self) -> str:
        return self._display_name

    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "response": self._response,
            "thought": self._thought,
            "model": self._model,
            "provider": self._provider,
            "is_finished": self._is_finished,
            "display_name": self._display_name,
        }
