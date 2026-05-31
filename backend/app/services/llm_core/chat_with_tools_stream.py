# -*- coding: utf-8 -*-
"""
chat_with_tools_stream — 从 llm_core.py 拆出

复制来源: llm_core.py 第307-346行 (chat_with_tools_stream)
Author: 小沈 - 2026-05-31
"""

from typing import List, Dict, Any, Optional, AsyncGenerator

from app.utils.logger import logger
from app.services.llm.core import StreamChunk
from app.services.llm.model_adapters.reasoning import fix_thinking_messages
from app.services.llm.stream_parser import parse_sse_stream, handle_http_error_stream
from app.services.llm.request_builder import build_messages


class ChatWithToolsStreamMixin:
    """chat_with_tools_stream Function Calling流式对话（SRP）"""

    async def chat_with_tools_stream(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> AsyncGenerator[StreamChunk, None]:
        """复制自 llm_core.py 第307-346行 — 发送对话请求（使用 Function Calling，流式返回）"""
        self.reset_cancel()

        try:
            messages = build_messages(message, history)
            if await self._detect_reasoning_support():
                messages = fix_thinking_messages(messages, True)

            request_json = {"model": self.model, "messages": messages, "stream": True}
            if tools:
                request_json["tools"] = tools
                request_json["tool_choice"] = tool_choice

            async with self._stream_with_retry(
                self._build_api_url(),
                headers=self._build_request_headers(),
                json_body=request_json,
            ) as response:
                self._current_response = response
                if self._cancelled:
                    await response.aclose()
                    yield self._create_cancelled_chunk()
                    return
                if response.status_code != 200:
                    async for chunk in handle_http_error_stream(response, self.model, log_tag="chat_with_tools_stream"):
                        yield chunk
                    return
                async for chunk in parse_sse_stream(response, self.model, lambda: self._cancelled, log_tag="chat_with_tools_stream"):
                    yield chunk
        except Exception as e:
            yield self._create_stream_error_chunk(e)
        finally:
            self._current_response = None
