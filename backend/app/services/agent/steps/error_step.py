# 编辑历史:
# 2026-07-18 小欧 - timestamp 注解 Optional[int]→Optional[str] 与运行时 UTC Z 字符串值对齐, 消除时间归一化不一致
# 2026-08-22 小欧 - model结构化归一报告v1.25 6.5: model/provider 分离入参 → error_model: Optional[ModelRef]
#   单结构承载; SSE 裸键由 _extra_fields 从 ModelRef 条件派生(原样保留"有值才输出"语义)

from typing import Any, Dict, Optional

from app.db.models.chat_models import ModelRef   # 归一 — 小欧 2026-08-22
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
        error_model: Optional[ModelRef] = None,
        timestamp: Optional[str] = None
    ):
        ReasoningStep.__init__(self, step, timestamp)
        self._error_type = error_type
        self._error_message = error_message
        self._step_model = error_model   # 复用基类唯一承载 — 小欧 2026-08-22

    def get_content(self) -> str:
        return self._error_message

    @property
    def error_type(self) -> str:
        return self._error_type

    @property
    def error_message(self) -> str:
        return self._error_message


    def _extra_fields(self) -> Dict[str, Any]:
        extra: Dict[str, Any] = {
            "error_type": self._error_type,
            "error_message": self._error_message,
        }
        _m = self._step_model   # SSE 裸键从 ModelRef 派生 — 小欧 2026-08-22
        if _m:
            if _m.model:
                extra["model"] = _m.model
            if _m.provider:
                extra["provider"] = _m.provider
        return extra
