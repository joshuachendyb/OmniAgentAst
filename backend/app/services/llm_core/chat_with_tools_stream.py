# -*- coding: utf-8 -*-
"""
chat_with_tools_stream — 调用SDK层实现流式FC

重构：Service层调用SDK层，消除重复代码 - 小沈 2026-06-09
Author: 小沈 - 2026-05-31
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator

from app.utils.logger import logger
from app.services.llm.core import StreamChunk
from app.services.llm.stream_parser import parse_sse_stream, handle_http_error_stream
from app.services.agent.agent_utils.message_utils import build_llm_messages


class ChatWithToolsStreamMixin:
    """chat_with_tools_stream Function Calling流式对话(SRP)"""

    async def chat_with_tools_stream(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式FC对话 — 调用SDK层chat_stream() - 小沈 2026-06-09"""
        self.reset_cancel()
        self._ensure_client()

        messages = build_llm_messages(message, history)

        async for chunk in self._stream_with_retry(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
        ):
            yield chunk

    async def _stream_with_retry(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
        max_retries: int = 3,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式调用+重试逻辑 - 小沈 2026-06-09"""
        from app.utils.retry import create_network_retry_engine

        retry_count = 0
        while retry_count <= max_retries:
            try:
                async for data_str in self._llm_sdk.chat_stream(
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    seed=self.seed,
                    tools=tools,
                    tool_choice=tool_choice,
                ):
                    if self._cancelled:
                        yield self._create_cancelled_chunk()
                        return

                    chunk = self._parse_sse_data(data_str)
                    if chunk:
                        yield chunk
                        if chunk.is_done:
                            return

                yield StreamChunk(content="", model=self.model, is_done=True)
                return

            except Exception as e:
                if self._should_retry(e) and retry_count < max_retries:
                    retry_count += 1
                    wait_time = 2 ** retry_count
                    logger.warning(f"[_stream_with_retry] 重试 {retry_count}/{max_retries}, 等待{wait_time}秒, 错误: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    yield self._create_stream_error_chunk(e)
                    return

    def _should_retry(self, e: Exception) -> bool:
        """判断是否应该重试 - 小沈 2026-06-09"""
        import httpx
        if isinstance(e, httpx.HTTPStatusError):
            return e.response.status_code in [429, 500, 502, 503, 504]
        if isinstance(e, (httpx.ConnectError, httpx.ReadError, httpx.WriteError)):
            return True
        return False

    def _parse_sse_data(self, data_str: str) -> Optional[StreamChunk]:
        """解析SSE data字符串为StreamChunk - 小沈 2026-06-09"""
        from app.utils.json_utils import parse_json
        from app.services.llm.model_adapters.reasoning import extract_reasoning_from_chunk

        try:
            data = parse_json(data_str)
            if data is None:
                return None

            choices = data.get("choices", [])
            if not choices:
                return None

            delta = choices[0].get("delta", {})
            content = delta.get("content", "") or ""
            reasoning_content = extract_reasoning_from_chunk(delta) or ""

            if content:
                return StreamChunk(content=content, model=self.model, is_done=False, is_reasoning=False)
            if reasoning_content:
                return StreamChunk(content=reasoning_content, model=self.model, is_done=False, is_reasoning=True)

            return None

        except Exception as e:
            logger.debug(f"[_parse_sse_data] 解析失败: {e}, data={data_str[:100]}")
            return None
