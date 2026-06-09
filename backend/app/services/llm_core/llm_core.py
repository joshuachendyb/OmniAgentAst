"""
LLM 核心模块 — BaseAIService

重构: 删除mixin继承, 统一为request/request_stream/chat + mode参数 - 小沈 2026-06-09
"""

import asyncio
import traceback
from typing import List, Dict, Optional, AsyncGenerator, Any

import httpx
from app.utils.logger import logger
from app.services.llm.core import ChatResponse, StreamChunk, _resolve_exception
from app.services.llm.stream_parser import create_cancelled_chunk
from app.services.llm.client_sdk import create_llm_client
from app.constants import DEFAULT_LLM_TIMEOUT, RATE_LIMIT_STATUS_CODES


class BaseAIService:
    """通用AI服务 — request/request_stream/chat + mode参数 - 小沈 2026-06-09"""

    def __init__(
        self,
        api_key: str,
        model: str,
        api_base: str,
        provider: str = "",
        timeout: int = DEFAULT_LLM_TIMEOUT,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        seed: Optional[int] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.api_base = api_base
        self.provider = provider
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.seed = seed
        self._llm_sdk = None
        try:
            timeout_value = float(timeout) if timeout else float(DEFAULT_LLM_TIMEOUT)
        except (ValueError, TypeError):
            timeout_value = float(DEFAULT_LLM_TIMEOUT)
        self.timeout = int(timeout_value)
        self._cancelled = False
        self._current_response: Optional[httpx.Response] = None

    def _ensure_client(self):
        if self._llm_sdk is None:
            self._llm_sdk = create_llm_client(
                provider=self.provider or "openai",
                model=self.model,
                api_key=self.api_key,
                base_url=self.api_base,
                timeout=self.timeout,
            )

    async def cancel(self):
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.model}")
        self._cancelled = True
        if self._current_response:
            try:
                if hasattr(self._current_response, 'aclose'):
                    await self._current_response.aclose()
                else:
                    self._current_response.close()
                logger.info("[BaseAIService.cancel] HTTP响应已强制关闭")
            except Exception as e:
                logger.error(f"[BaseAIService.cancel] 关闭响应失败: {e}")

    def reset_cancel(self):
        self._cancelled = False
        self._current_response = None

    RATE_LIMIT_STATUS_CODES = RATE_LIMIT_STATUS_CODES

    def _is_rate_limit_status(self, status_code: int) -> bool:
        return status_code in self.RATE_LIMIT_STATUS_CODES

    def _create_stream_error_chunk(self, e: Exception) -> StreamChunk:
        msg, err_type = _resolve_exception(e)
        if err_type == "unknown_error":
            logger.error(f"[{_resolve_exception.__name__}] 未知异常: {e}, 类型: {type(e).__name__}, 堆栈: {traceback.format_exc()}")
        return StreamChunk(content="", model=self.model, is_done=True, stream_error=msg, stream_error_type=err_type)

    def _create_cancelled_chunk(self) -> StreamChunk:
        return create_cancelled_chunk(self.model)

    async def request(
        self,
        messages: List[Dict],
        mode: str = "text",
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> ChatResponse:
        """非流式请求 - Agent用 - 小沈 2026-06-09"""
        self._ensure_client()
        try:
            response = await self._llm_sdk.request(
                messages=messages,
                mode=mode,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                seed=self.seed,
            )
            choices = response.get("choices", [])
            if not choices:
                return ChatResponse(content="", model=self.model, provider=self.provider, error="无响应")

            msg = choices[0].get("message", {})
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls", [])

            from app.services.llm.model_adapters.reasoning import extract_reasoning_from_chunk
            reasoning = extract_reasoning_from_chunk(msg) or ""

            return ChatResponse(
                content=content,
                model=self.model,
                provider=self.provider,
                tool_calls=tool_calls,
                reasoning=reasoning,
            )
        except Exception as e:
            return ChatResponse(content="", model=self.model, provider=self.provider, error=str(e))

    async def request_stream(
        self,
        messages: List[Dict],
        mode: str = "text",
        tools: Optional[List[Dict]] = None,
        tool_choice: str = "auto",
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式请求 - SSE服务层/Agent用 - 小沈 2026-06-09"""
        self.reset_cancel()
        self._ensure_client()

        retry_count = 0
        max_retries = 3

        while retry_count <= max_retries:
            try:
                async for data_str in self._llm_sdk.request_stream(
                    messages=messages,
                    mode=mode,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    seed=self.seed,
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
                    logger.warning(f"[request_stream] 重试 {retry_count}/{max_retries}, 等待{wait_time}秒, 错误: {e}")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    yield self._create_stream_error_chunk(e)
                    return

    async def chat(
        self,
        message: str,
        history: Optional[List[Dict]] = None,
    ) -> AsyncGenerator[StreamChunk, None]:
        """流式对话便捷方法 - SSE服务层用 - 小沈 2026-06-09"""
        messages = self._build_messages(message, history)
        async for chunk in self.request_stream(messages=messages, mode="text"):
            yield chunk

    def _build_messages(self, message: str, history: Optional[List[Dict]] = None) -> List[Dict]:
        """构建消息列表 - 小沈 2026-06-09"""
        messages = []
        if history:
            for msg in history:
                if isinstance(msg, dict):
                    messages.append(msg)
                else:
                    messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": message})
        return messages

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

    def _should_retry(self, e: Exception) -> bool:
        """判断是否应该重试 - 小沈 2026-06-09"""
        if isinstance(e, httpx.HTTPStatusError):
            return e.response.status_code in [429, 500, 502, 503, 504]
        if isinstance(e, (httpx.ConnectError, httpx.ReadError, httpx.WriteError)):
            return True
        return False

    async def close(self):
        if self._llm_sdk:
            await self._llm_sdk.close()


__all__ = ["BaseAIService", "ChatResponse", "StreamChunk"]
