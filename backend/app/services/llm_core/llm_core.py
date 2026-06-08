"""
LLM 核心模块 — 类骨架

从 llm_core.py 拆出,遵循 SRP:
- chat / chat_stream / chat_with_tools_stream / chat_with_tools → 独立文件
- 本文件只保留 BaseAIService 类定义、__init__、辅助方法

作者:小沈
"""

import asyncio
import traceback
import httpx
from typing import List, Dict, Optional, AsyncGenerator, Any

from app.utils.logger import logger
from app.utils.retry_engine import RetryEngine, BackoffStrategy
from app.services.llm.core import (
    ChatResponse, StreamChunk, _StreamRetryContext, _resolve_exception,
)
from app.services.llm.stream_parser import create_cancelled_chunk

from app.services.llm.client_sdk import create_llm_client
from app.constants import DEFAULT_LLM_TIMEOUT, RATE_LIMIT_STATUS_CODES

from app.services.llm_core.chat_with_tools_stream import ChatWithToolsStreamMixin
from app.services.llm_core.tool_caller import ToolCallerMixin
from app.services.llm_core.chat import aggregate_chat_response


class BaseAIService(ChatWithToolsStreamMixin, ToolCallerMixin):
    """通用AI服务 — 只保留骨架"""

    def __init__(self, api_key: str, model: str, api_base: str, provider: str = "", timeout: int = DEFAULT_LLM_TIMEOUT,
                 max_tokens: int = 4096, temperature: float = 0.7, seed: Optional[int] = None):
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


    def cancel(self):
        logger.info(f"[BaseAIService.cancel] 正在强制取消请求, model={self.model}")
        self._cancelled = True
        if self._current_response:
            try:
                if hasattr(self._current_response, 'aclose'):
                    try:
                        asyncio.get_event_loop().run_until_complete(self._current_response.aclose())
                    except RuntimeError:
                        pass
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


    def _stream_with_retry(self, url: str, headers: dict, json_body: dict, max_retries: int = 3, retry_delay: float = 2.0):
        return _StreamRetryContext(self, url, headers, json_body, max_retries, retry_delay)

    def _create_stream_error_chunk(self, e: Exception) -> StreamChunk:
        msg, err_type = _resolve_exception(e)
        if err_type == "unknown_error":
            logger.error(f"[{_resolve_exception.__name__}] 未知异常: {e}, 类型: {type(e).__name__}, 堆栈: {traceback.format_exc()}")
        return StreamChunk(content="", model=self.model, is_done=True, stream_error=msg, stream_error_type=err_type)

    def _create_cancelled_chunk(self) -> StreamChunk:
        return create_cancelled_chunk(self.model)

    chat = aggregate_chat_response


    def _build_api_url(self) -> str:
        return f"{self.api_base}/chat/completions"

    def _build_request_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    async def close(self):
        if self._llm_sdk:
            await self._llm_sdk.close()


__all__ = ["BaseAIService", "ChatResponse", "StreamChunk"]
