from typing import Any, Dict, Optional

from .base import ReasoningStep


class IncidentStep(ReasoningStep):
    """
    IncidentStep类 - 运行时事件步骤

    表示运行过程中的事件(中断/暂停/恢复/重试/授权请求):
    - type: incident_value的具体值(interrupted/paused/resumed/retrying/authorization_required)
    - is_done() = False → 不结束循环

    字段说明:
    - incident_value: 事件类型值(interrupted/paused/resumed/retrying/authorization_required)
    - message: 事件消息
    - content: 内容(可选,默认等于message)
    - data: 附加数据(如authorization_required的tool_name/params/safety_level)

    【修改 2026-06-09 小沈】直接使用incident_value作为type字段，简化前端转换逻辑
    【v3.4新增 2026-06-09 小沈】支持authorization_required事件，携带data字段
    """

    def __init__(
        self,
        step: int,
        incident_value: str,
        message: str = "",
        content: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        timestamp: Optional[int] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)

        self._incident_value = incident_value
        self._message = message
        self._content = content or message
        self._data = data or {}

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

    @property
    def data(self) -> Dict[str, Any]:
        return self._data

    def _extra_fields(self) -> Dict[str, Any]:
        """返回message和data字段"""
        extra = {
            "message": self._message,
        }
        if self._data:
            extra["data"] = self._data
        return extra
