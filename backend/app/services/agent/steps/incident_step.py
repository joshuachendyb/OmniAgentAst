from typing import Any, Dict, Optional

from .base import ReasoningStep


class IncidentStep(ReasoningStep):
    """
    IncidentStep类 - 运行时事件步骤

    表示运行过程中的事件（中断/暂停/恢复/重试）：
    - type: "incident"
    - is_done() = False → 不结束循环

    字段说明：
    - incident_value: 事件类型值（interrupted/paused/resumed/retrying）
    - message: 事件消息
    - content: 内容（可选，默认等于message）
    """

    def __init__(
        self,
        step: int,
        incident_value: str,
        message: str,
        content: Optional[str] = None,
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)

        self._incident_value = incident_value
        self._message = message
        self._content = content or message

    def get_type(self) -> str:
        return "incident"

    def get_content(self) -> str:
        return self._message

    @property
    def incident_value(self) -> str:
        return self._incident_value

    @property
    def message(self) -> str:
        return self._message

    @property
    def incident_content(self) -> str:
        return self._content

    def is_done(self) -> bool:
        return False

    def to_dict(self) -> Dict[str, Any]:
        base_dict = ReasoningStep.to_dict(self)
        base_dict.update({
            "incident_value": self._incident_value,
            "message": self._message,
            "content": self._content,
        })
        return base_dict
