# -*- coding: utf-8 -*-
"""
_handle_empty_response — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第61-104行
Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, AsyncGenerator

from app.services.agent.steps import StepFactory
from app.utils.logger import logger


class HandleEmptyResponseMixin:
    """空响应截断历史重试"""

    async def _handle_empty_response(
        self, step_count: int
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """复制自 react_handler_mixin.py 第61-104行"""
        _retry_cnt = self._empty_response_retry_engine.attempt_count
        _max_retries = self._empty_response_retry_engine.max_retries
        logger.error(
            f"[空响应] LLM返回空响应 (第{_retry_cnt}次重试), "
            f"history长度={len(self.conversation_history)}"
        )

        if _retry_cnt > _max_retries:
            yield self._exit_with_error(step_count, "empty_response", f"AI服务返回空响应（已重试{_retry_cnt}次）")
            self._on_after_loop()
            return

        original_len = len(self.conversation_history)
        if original_len <= 4:
            logger.warning("[空响应] 历史已很短无法截断，直接报错")
            yield self._exit_with_error(step_count, "empty_response", f"AI服务返回空响应（已重试{_retry_cnt}次）")
            self._on_after_loop()
            return

        kept_head = self.conversation_history[:2]
        kept_tail = self.conversation_history[-2:]
        seen_ids = set()
        deduped = []
        for item in kept_head + kept_tail:
            item_id = id(item)
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                deduped.append(item)
        removed_len = original_len - len(deduped)
        self.conversation_history = deduped
        self.message_builder.conversation_history = deduped
        logger.warning(
            f"[空响应截断历史] 从{original_len}条截断到{len(deduped)}条, "
            f"移除{removed_len}条中间历史, 准备重试"
        )
        yield StepFactory.create_incident_step(
            step=step_count,
            incident_value='retrying',
            message=f"AI返回空响应，已压缩对话历史重试（第{_retry_cnt}次）"
        )
