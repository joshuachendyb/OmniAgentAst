# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 小欧 - 新增: thought-start 实时信号 step(不落库, 仅 SSE)
# 2026-10-12 小欧 - 首帧带 task_id（北京老陈令）: __init__ 增可选 task_id, 有值才下发; 后续帧与老调用走默认值 — 小欧-2026-10-12
# 2026-11-13 商量 - 增可选 task_start_time(后端权威任务起点, 本地ISO): 首帧下发, 前端实时秒表据此定起点
#   (该帧在历史加载/摘要压缩之前发出 → 压缩期秒表即走动; 起点与终态 duration=end-start_time 同一真源) — 商量-2026-11-13

from typing import Any, Dict, Optional

from .base import ReasoningStep


class ThoughtStartStep(ReasoningStep):
    """思考开始信号 - 纯实时, 不落库"""

    TYPE: str = "thought-start"

    def __init__(self, step: int, task_id: Optional[str] = None,
                 timestamp: Optional[str] = None,
                 task_start_time: Optional[str] = None):
        # 2026-10-12 小欧 - 首帧带 task_id（北京老陈令）: 仅首轮发射点传参,
        #   后续帧走默认值不下发该键; 可选参数, 老调用零改动 — 小欧-2026-10-12
        # 2026-11-13 商量 - task_start_time 同理: 仅首帧下发(任务权威起点), 后续帧走默认值 — 商量-2026-11-13
        ReasoningStep.__init__(self, step, timestamp)
        self._task_id = task_id
        self._task_start_time = task_start_time

    def get_content(self) -> str:
        return ""

    def _extra_fields(self) -> Dict[str, Any]:
        extra: Dict[str, Any] = {}
        if self._task_id:
            extra["task_id"] = self._task_id
        if self._task_start_time:
            extra["task_start_time"] = self._task_start_time
        return extra
