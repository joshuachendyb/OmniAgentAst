# -*- coding: utf-8 -*-
"""
_handle_action_type — 从 react_handler_mixin.py 拆出

task检查通过 task_registry 函数直接读，不再接收 running_tasks 参数

Author: 小沈 - 2026-05-31
统一: 小健 - 2026-05-31 — 去掉running_tasks参数
"""

from typing import Any, Dict, Set, Optional, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer


class HandleActionTypeMixin:
    """action工具执行入口"""

    async def _handle_action_type(
        self, parsed: Dict[str, Any], step_count: int,
        chunk_buffer: ChunkBuffer, valid_tool_names: Set[str],
        task_id: Optional[str],
        response: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第239-292行"""
        tool_name = parsed.get("tool_name")
        tool_params = parsed.get("tool_params", {})
        thought_content = parsed.get("content", "")
        thought = parsed.get("thought", "")
        reasoning = parsed.get("reasoning", "")

        self._parse_retry_engine.reset_attempts()

        chunk_buffer_was_flushed = bool(chunk_buffer.buffer)
        if chunk_buffer.buffer:
            content = chunk_buffer.flush()
            if content:
                self.message_builder.temp_history.clear()
                self.message_builder.add_assistant(content)

        _thought_val = self._merge_thought_text(thought, thought_content)

        thought_step = StepFactory.create_thought_step(
            step=step_count, content="", tool_name=tool_name,
            tool_params=tool_params, thought=_thought_val, reasoning=reasoning
        )
        yield self._emit_step(thought_step)

        self.status = AgentStatus.EXECUTING

        outcome = await self._execute_tool_step(tool_name, tool_params, step_count)

        async for step in self._handle_observation_flow(
            outcome, parsed, step_count, task_id
        ):
            yield step
