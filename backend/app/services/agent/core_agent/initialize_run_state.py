# -*- coding: utf-8 -*-
"""
_initialize_run_state — 每次运行前初始化Agent状态

职责: 重置steps/message_builder/status/llm_call_count,注入system prompt和task
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, Optional

from app.constants import MAX_CONSECUTIVE_CHUNKS
from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer
from app.utils.prompt_logger import get_prompt_logger


def _inject_conversation_history(self, context: Optional[Dict[str, Any]]) -> None:
    """注入会话历史(多轮对话支持) — 北京老陈 2026-06-13"""
    if not context or not isinstance(context, dict):
        return
    prev = context.get("previous_messages")
    if not prev or not isinstance(prev, list):
        return
    history = self.message_builder.conversation_history
    for msg in prev:
        if msg.get("role") in ("user", "assistant") and msg.get("content"):
            history.append({"role": msg["role"], "content": msg["content"]})
    self.message_builder.conversation_history = history
    self.message_builder.trim_history()


def initialize_run_state(
    self, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
) -> ChunkBuffer:
    """初始化每轮运行状态:重置steps/注入system prompt和task"""
    self.steps = []
    self.message_builder.reset_per_run()
    self.status = AgentStatus.THINKING
    self.llm_call_count = 0
    if task_id:
        self.task_id = task_id

    self._on_session_init(task, context)
    sys_prompt = self._get_system_prompt()

    prompt_logger = get_prompt_logger()
    prompt_logger.log_system_prompt(
        step_name="运行时系统Prompt注入",
        prompt_content=sys_prompt,
        source=f"{self.__class__.__name__}._get_system_prompt()",
    )
    prompt_logger.log_task_prompt(
        task_content=task,
        context=context if context else None,
    )

    self._on_before_loop(sys_prompt, task, context)
    self.message_builder.init_history(sys_prompt, task)
    _inject_conversation_history(self, context)

    return ChunkBuffer(MAX_CONSECUTIVE_CHUNKS)
