# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 小欧 - 新增: thought-start 实时信号 step(不落库, 仅 SSE)
# 2026-10-12 小欧 - 首帧带 task_id（北京老陈令）: __init__ 增可选 task_id, 有值才下发; 后续帧与老调用走默认值 — 小欧-2026-10-12

from typing import Any, Dict, Optional

from .base import ReasoningStep


class ThoughtStartStep(ReasoningStep):
    """思考开始信号 - 纯实时, 不落库"""

    TYPE: str = "thought-start"

    def __init__(self, step: int, task_id: Optional[str] = None,
                 timestamp: Optional[str] = None):
        # 2026-10-12 小欧 - 首帧带 task_id（北京老陈令）: 仅首轮发射点传参,
        #   后续帧走默认值不下发该键; 可选参数, 老调用零改动 — 小欧-2026-10-12
        ReasoningStep.__init__(self, step, timestamp)
        self._task_id = task_id

    def get_content(self) -> str:
        return ""

    def _extra_fields(self) -> Dict[str, Any]:
        return {"task_id": self._task_id} if self._task_id else {}
