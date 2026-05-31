# -*- coding: utf-8 -*-
"""
chat_stream — 从 llm_core.py 拆出

复制来源: llm_core.py 第269-272行 (chat_stream)
Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Optional, AsyncGenerator
from app.services.llm.core import StreamChunk


class ChatStreamMixin:
    """chat_stream 流式对话（SRP）"""

    async def chat_stream(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """复制自 llm_core.py 第269-272行 — 发送对话请求（流式返回）"""
        async for chunk in self.chat_with_tools_stream(message, history):
            yield chunk
