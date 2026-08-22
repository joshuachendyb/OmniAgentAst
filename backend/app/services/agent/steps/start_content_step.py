# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 小欧 - 新增: §10.1.2 P7 start 拆双——StartStep(thought 类内容步骤, 落库, content=context_summary)
# 2026-08-22 小欧 - model结构化归一报告v1.25 6.5: display_name/provider/model 三分离入参 → start_model: Optional[ModelRef]
#   单结构承载; display_name 键消亡(设计要求2: 后端零依赖仅前端派生, 消费点 agent_runner startinfo 已随删)
from typing import Any, Dict, Optional

from app.db.models.chat_models import ModelRef   # 归一 — 小欧 2026-08-22
from .base import ReasoningStep


class StartStep(ReasoningStep):
    """start 完整任务契约 - thought 类内容步骤, 落库承载上下文摘要(§10.1.2)"""
    TYPE: str = "start"

    def __init__(self, step: int = 0, context_summary: Optional[Dict] = None,
                 user_message: str = "", task_id: Optional[str] = None,
                 start_model: Optional[ModelRef] = None,
                 system_prompt: str = "",
                 warning: Optional[str] = None, timestamp: Optional[str] = None):
        ReasoningStep.__init__(self, step, timestamp)
        self._context_summary = context_summary or {}
        self._user_message = user_message
        self._task_id = task_id
        self._step_model = start_model   # 复用基类唯一承载 — 小欧 2026-08-22
        self._system_prompt = system_prompt
        self._warning = warning

    def get_content(self) -> Any:      # content=context_summary 结构化对象(10.1.2 <第2步>3)
        return self._context_summary

    def _extra_fields(self) -> Dict[str, Any]:
        _m = self._step_model   # SSE 裸键从 ModelRef 派生 — 小欧 2026-08-22
        return {
            "user_message": self._user_message,   # user_input 顶层化(10.1.2 <第2步>4)
            "task_id": self._task_id,
            "provider": _m.provider if _m else None,
            "model": _m.model if _m else None,
            "api_base": _m.api_base if _m else None,
            "display_name": _m.display_name if _m and _m.display_name else None,  # 仅用户自定义别名透传, 系统不拼接(设计要求2)
            "system_prompt": self._system_prompt,
            "warning": self._warning,
        }