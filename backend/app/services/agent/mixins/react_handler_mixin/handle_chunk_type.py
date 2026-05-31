# -*- coding: utf-8 -*-
"""
_handle_chunk_type — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第95-133行
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.services.agent.chunk_buffer import ChunkBuffer


class HandleChunkTypeMixin:
    """chunk类型处理"""

    async def _handle_chunk_type(
        self, parsed: Dict[str, Any], step_count: int,
        chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第95-133行"""
        self._parse_retry_engine.reset_attempts()
        chunk_content = parsed.get("content", "")

        # 1. 存入buffer
        chunk_buffer.append(chunk_content)

        # 2. 存入message_builder历史（保留最近10条）
        self.message_builder.temp_history.append({"role": "assistant", "content": chunk_content})
        if len(self.message_builder.temp_history) > 10:
            self.message_builder.temp_history = self.message_builder.temp_history[-10:]

        # 3. 立即显示这个chunk
        chunk_step = StepFactory.create_chunk_step(step=step_count, content=chunk_content)
        yield self._emit_step(chunk_step)

        # 4. 检查是否该"倒水"完成
        # 【3.9修复 北京老陈 2026-05-31】chunk累积超时检测，防止无限循环
        if chunk_buffer.should_force_stop():
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, "chunk累积超时，强制停止"):
                yield step
            return

        if self.tool_category is None:
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, ""):
                yield step
            return

        if chunk_buffer.should_promote():
            content = chunk_buffer.flush()
            async for step in self._complete_chunk(content, step_count, ""):
                yield step
            return
