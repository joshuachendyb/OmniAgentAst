# -*- coding: utf-8 -*-
"""
_handle_parse_error — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第202-237行
Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import Any, Dict, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.utils.error_classifier import UnifiedErrorClassifier
from app.utils.logger import logger
from app.services.agent.chunk_buffer import ChunkBuffer


class HandleParseErrorMixin:
    """解析错误重试"""

    async def _handle_parse_error(
        self, parsed: Dict[str, Any], step_count: int, chunk_buffer: ChunkBuffer
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第202-237行"""
        error_msg = parsed.get("error", "Unknown parse error")
        chunk_buffer.clear()

        is_network_error, _error_type = UnifiedErrorClassifier.is_network_or_api_error(error_msg)

        if not is_network_error:
            self.message_builder.add_observation(
                f"Parse Error: {error_msg}. Please ensure your response follows the ReAct format (Thought -> Action -> Action Input)."
            )
        else:
            logger.info(f"[parse_react_response] 网络/API错误，不注入history: {error_msg}")
            if _error_type == "api_error_429":
                _retry_delay = self._parse_retry_engine.current_delay
                logger.warning(f"[parse_react_response] 429限流, 等待{_retry_delay:.0f}s后重试 (第{self._parse_retry_engine.attempt_count+1}次)")
                await asyncio.sleep(_retry_delay)
            yield StepFactory.create_incident_step(
                step=step_count,
                incident_value='rate_limit',
                message=f"API暂时不可用，正在重试（第{self._parse_retry_engine.attempt_count + 1}次）"
            )

        self._parse_retry_engine.record_attempt()
        if self._parse_retry_engine.exhausted:
            yield self._exit_with_error(step_count, "parse_error", f"解析失败: {error_msg}（已重试{self._parse_retry_engine.max_retries}次）")
            self._on_after_loop()
            return

        yield StepFactory.create_incident_step(
            step=step_count,
            incident_value='retrying',
            message=f"解析失败，正在重试（第{self._parse_retry_engine.attempt_count}次）"
        )
