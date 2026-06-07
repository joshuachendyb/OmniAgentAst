# -*- coding: utf-8 -*-
"""
_initialize_run_state — 从 base_react.py 拆出

复制来源: base_react.py 第295-338行
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, Optional, Tuple, Set

from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer
from app.utils.logger import logger


def initialize_run_state(
    self, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
) -> Tuple[ChunkBuffer, Set[str]]:
    """复制自 base_react.py 第295-338行"""
    self.steps = []
    self.message_builder.reset_per_run()
    self.conversation_history = self.message_builder.conversation_history
    self.status = AgentStatus.THINKING
    self.llm_call_count = 0
    if task_id:
        self.task_id = task_id

    self._on_session_init(task, context)
    sys_prompt = self._get_system_prompt()
    task_prompt = self._get_task_prompt(task, context)
    self._on_before_loop(sys_prompt, task_prompt, context)
    self.message_builder.init_history(sys_prompt, task_prompt)
    self.conversation_history = self.message_builder.conversation_history

    chunk_buffer = ChunkBuffer(self.max_consecutive_chunks)
    valid_tool_names: Set[str] = {"finish"}
    try:
        from app.services.tools.registry import tool_registry
        valid_tool_names = {t["name"] for t in tool_registry.list_tools()} | {"finish"}
    except Exception as _e:
        logger.debug(f"[工具名验证] 获取工具列表失败: {_e}, 仅允许finish")

    from app.services.agent.base_react.agent_initializer import AgentInitializer
    AgentInitializer._init_task_tracking(self, enable=True, description=task)

    return chunk_buffer, valid_tool_names
