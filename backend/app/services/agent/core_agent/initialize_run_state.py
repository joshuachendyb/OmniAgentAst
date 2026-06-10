# -*- coding: utf-8 -*-
"""
_initialize_run_state — 从 base_react.py 拆出

复制来源: base_react.py 第295-338行
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, Optional

from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer


def initialize_run_state(
    self, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
) -> ChunkBuffer:
    """复制自 base_react.py 第295-338行"""
    self.steps = []
    self.message_builder.reset_per_run()
    self.status = AgentStatus.THINKING
    self.llm_call_count = 0
    if task_id:
        self.task_id = task_id

    self._on_session_init(task, context)
    sys_prompt = self._get_system_prompt()
    task_prompt = self._get_task_prompt(task, context)
    self._on_before_loop(sys_prompt, task_prompt, context)
    self.message_builder.init_history(sys_prompt, task_prompt)

    return ChunkBuffer(self.max_consecutive_chunks)
