# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-18 小欧 - 新增: §10.1.2 P7 start 拆双——StartStep(thought 类内容步骤, 落库, content=context_summary)
from typing import Any, Dict, Optional

from .base import ReasoningStep


class StartStep(ReasoningStep):
    """start 完整任务契约 - thought 类内容步骤, 落库承载上下文摘要(§10.1.2)"""
    TYPE: str = "start"

    def __init__(self, step: int = 0, context_summary: Optional[Dict] = None,
                 user_message: str = "", task_id: Optional[str] = None,
                 display_name: str = "", provider: Optional[str] = None,
                 model: Optional[str] = None, system_prompt: str = "",
                 warning: Optional[str] = None, timestamp: Optional[str] = None):
        ReasoningStep.__init__(self, step, timestamp)
        self._context_summary = context_summary or {}
        self._user_message = user_message
        self._task_id = task_id
        self._display_name = display_name
        self._provider = provider
        self._model = model
        self._system_prompt = system_prompt
        self._warning = warning

    def get_content(self) -> Any:      # content=context_summary 结构化对象(10.1.2 <第2步>3)
        return self._context_summary

    def _extra_fields(self) -> Dict[str, Any]:
        return {
            "user_message": self._user_message,   # user_input 顶层化(10.1.2 <第2步>4)
            "task_id": self._task_id,
            "display_name": self._display_name,
            "provider": self._provider,
            "model": self._model,
            "system_prompt": self._system_prompt,
            "warning": self._warning,
        }