# -*- coding: utf-8 -*-
"""
_handle_thought_only — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第183-200行
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.services.agent.chunk_buffer import ChunkBuffer


class HandleThoughtOnlyMixin:
    """thought_only纯思考分支"""

    async def _handle_thought_only(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第183-200行"""
        self._parse_retry_engine.reset_attempts()
        thought = parsed.get("thought", "")
        thought_content = parsed.get("content", "")

        _thought_val = self._merge_thought_text(thought, thought_content)

        thought_step = StepFactory.create_thought_step(
            step=step_count, content="", tool_name="", tool_params={},
            thought=_thought_val, reasoning=parsed.get("reasoning", "")
        )
        yield self._emit_step(thought_step)
        self.message_builder.add_assistant(_thought_val)
        self.message_builder.trim_history()
        chunk_buffer.clear()
