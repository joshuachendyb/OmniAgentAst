# -*- coding: utf-8 -*-
"""
_initialize_run_state — 每次运行前初始化Agent状态

职责: 重置steps/message_builder/status/llm_call_count,注入system prompt和task
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, Optional

from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer


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
    self._on_before_loop(sys_prompt, task, context)
    self.message_builder.init_history(sys_prompt, task)

    return ChunkBuffer(self.max_consecutive_chunks)
