# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 小欧 - 新增: §10.3.3(1) thought-start 实时信号 step(不落库, 仅 SSE)

from typing import Any, Dict

from .base import ReasoningStep


class ThoughtStartStep(ReasoningStep):
    """思考开始信号 - 纯实时, 不落库（§10.3.3(1)）"""

    TYPE: str = "thought-start"

    def get_content(self) -> str:
        return ""

    def _extra_fields(self) -> Dict[str, Any]:
        return {}
