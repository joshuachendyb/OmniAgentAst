# -*- coding: utf-8 -*-
"""
_handle_completion_type — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第155-181行
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.services.agent.types import AgentStatus
from app.services.agent.chunk_buffer import ChunkBuffer


class HandleCompletionTypeMixin:
    """answer/implicit完成处理"""

    async def _handle_completion_type(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第155-181行"""
        self._parse_retry_engine.reset_attempts()

        if chunk_buffer.buffer:
            content = chunk_buffer.flush()
            if content:
                self.message_builder.temp_history.clear()
                self.message_builder.add_assistant(content)

        answer_response = parsed.get("response", "")
        if not answer_response or not answer_response.strip():
            answer_response = parsed.get("tool_params", {}).get("result", "") if isinstance(parsed.get("tool_params"), dict) else ""
        if not answer_response or not answer_response.strip():
            answer_response = parsed.get("content", "")
        if not answer_response or not answer_response.strip():
            answer_response = parsed.get("reasoning", "")

        _reasoning = parsed.get("reasoning", "")
        final_step = StepFactory.create_final_step(
            step=step_count, response=answer_response, thought=_reasoning,
            model=getattr(self, 'model', None), provider=getattr(self, 'provider', None)
        )
        yield self._emit_step(final_step)
        self.status = AgentStatus.COMPLETED
