from typing import Any, Dict, Optional

from .base import ReasoningStep


class IncidentStep(ReasoningStep):
    """
    IncidentStep类 - 运行时事件步骤

    表示运行过程中的事件(中断/暂停/恢复/重试):
    - type: incident_value的具体值(interrupted/paused/resumed/retrying)
    - is_done() = False → 不结束循环

    字段说明:
    - incident_value: 事件类型值(interrupted/paused/resumed/retrying)
    - message: 事件消息
    - content: 内容(可选,默认等于message)

    【修改 2026-06-09 小沈】直接使用incident_value作为type字段，简化前端转换逻辑
    """

    # 删除固定TYPE，使用动态type
    # TYPE: str = "incident"

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
        """直接返回incident_value作为type，简化前端转换"""
        return self._incident_value

    def get_content(self) -> str:
        return self._content

    @property
    def incident_value(self) -> str:
        return self._incident_value

    @property
    def message(self) -> str:
        return self._message

    @property
    def incident_content(self) -> str:
        return self._content

    def _extra_fields(self) -> Dict[str, Any]:
        """删除incident_value字段，已作为type返回"""
        return {
            "message": self._message,
        }
