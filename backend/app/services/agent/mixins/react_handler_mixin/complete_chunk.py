# -*- coding: utf-8 -*-
"""
_complete_chunk — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第135-153行
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.services.agent.types import AgentStatus


class CompleteChunkMixin:
    """chunk完成的公共逻辑"""

    async def _complete_chunk(
        self, content: str, step_count: int, thought: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第135-153行"""
        # builder操作：清空历史，保存accumulated内容
        if content:
            self.message_builder.temp_history.clear()
            self.message_builder.add_assistant(content)

        # 创建final_step
        final_step = StepFactory.create_final_step(step=step_count + 1, response=content, thought=thought)
        yield self._emit_step(final_step)

        # 标记完成
        self.status = AgentStatus.COMPLETED
        self._on_after_loop()
