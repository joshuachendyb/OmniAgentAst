# -*- coding: utf-8 -*-
"""
chat — 从 llm_core.py 拆出

复制来源: llm_core.py 第220-264行
Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Optional

from app.utils.logger import logger
from app.services.llm.core import ChatResponse


async def chat(self, message: str, history: Optional[List[Dict]] = None) -> ChatResponse:
    """复制自 llm_core.py 第220-264行"""
    try:
        full_content = ""
        full_reasoning = ""
        has_non_reasoning_content = False
        stream_error = None
        async for chunk in self.chat_stream(message, history):
            if chunk.content:
                if getattr(chunk, "is_reasoning", False):
                    full_reasoning += chunk.content
                else:
                    full_content += chunk.content
                    has_non_reasoning_content = True
            if chunk.reasoning:
                full_reasoning += chunk.reasoning
            if chunk.stream_error:
                stream_error = chunk.stream_error
            if chunk.is_done:
                break
        if not has_non_reasoning_content and full_reasoning:
            full_content = full_reasoning
            logger.info(f"[chat] 无普通content，使用reasoning_content作为fallback")
        logger.info(
            f"[chat] 聚合结果, model={self.model}, "
            f"full_content长度={len(full_content)}, "
            f"full_reasoning长度={len(full_reasoning)}, "
            f"has_error={stream_error is not None}"
        )
        if stream_error:
            return ChatResponse(content="", model=self.model, provider=self.provider, error=stream_error)
        return ChatResponse(content=full_content, model=self.model, provider=self.provider,
                            reasoning=full_reasoning)
    except Exception as e:
        logger.error(f"[chat] 异常: {e}")
        return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))
