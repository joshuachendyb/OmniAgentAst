# -*- coding: utf-8 -*-
"""
LLM核心数据类与辅助函数 — SRP拆分自llm_core.py — 小健 2026-05-27

职责：定义LLM层的响应数据类（ChatResponse、StreamChunk）、
重试上下文（_StreamRetryContext）、异常解析（_resolve_exception）。

拆分原则：数据/辅助定义与BaseAIService主服务类分离，遵循SRP。
对外透明：llm_core.py重新导出这些类，外部import路径不变。
"""

import asyncio
from typing import List, Dict, Optional

from app.utils.logger import logger
from app.utils.retry_engine import RetryEngine, BackoffStrategy
from app.constants import ERROR_TYPE_MAP, HTTPX_EXCEPTION_TO_ERROR_KEY


def _resolve_exception(e: Exception) -> tuple:
    """解析异常→(用户消息, 错误类型)，复用constants.py已有常量组合查询 — 小健 2026-05-25

    httpx异常通过HTTPX_EXCEPTION_TO_ERROR_KEY映射到error_key，
    httpcore异常共用同名映射（如httpcore.ReadError与httpx.ReadError→"read_error"），
    再通过ERROR_TYPE_MAP[error_key]获取(分类, 用户消息)。
    """
    error_key = HTTPX_EXCEPTION_TO_ERROR_KEY.get(type(e).__name__)
    if error_key and error_key in ERROR_TYPE_MAP:
        _, user_msg = ERROR_TYPE_MAP[error_key]
        return user_msg, error_key
    return f"AI服务调用失败: {type(e).__name__}", "unknown_error"


class ChatResponse:
    """聊天响应类 - 非流式响应"""
    def __init__(self, content: str, model: str, provider: str = "", error: Optional[str] = None,
                 reasoning: Optional[str] = None, tool_calls: Optional[List[Dict]] = None):
        self.content = content
        self.model = model
        self.provider = provider
        self.error = error
        self.success = error is None
        self.reasoning = reasoning or ""
        self.tool_calls = tool_calls or []


class StreamChunk:
    """流式响应片段"""
    def __init__(self, content: str, model: str, is_done: bool = False,
                 stream_error: Optional[str] = None, stream_error_type: Optional[str] = None,
                 reasoning: Optional[str] = None, is_reasoning: bool = False):
        self.content = content
        self.model = model
        self.is_done = is_done
        self.stream_error = stream_error
        self.stream_error_type = stream_error_type
        self.reasoning = reasoning
        self.is_reasoning = is_reasoning


class _StreamRetryContext:
    """流式请求429重试上下文管理器 — 委托到RetryEngine统一退避策略 — 小沈 2026-05-27"""

    def __init__(self, service, url, headers, json_body, max_retries=3, retry_delay=2.0):
        self.service = service
        self.url = url
        self.headers = headers
        self.json_body = json_body
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._response_ctx = None
        self._engine = RetryEngine(
            max_retries=max_retries,
            backoff_strategy=BackoffStrategy.EXPONENTIAL,
            backoff_factor=retry_delay,
        )

    async def __aenter__(self):
        from app.utils.retry_engine import BackoffStrategy
        for attempt in range(self.max_retries):
            self._response_ctx = self.service.client.stream(
                "POST", self.url, headers=self.headers, json=self.json_body
            )
            response = await self._response_ctx.__aenter__()
            if self.service._is_rate_limit_status(response.status_code):
                await self._response_ctx.__aexit__(None, None, None)
                if attempt < self.max_retries - 1:
                    delay = self._engine._calculate_delay(attempt + 1)
                    logger.warning(f"[429重试] 流式HTTP {response.status_code}, 第{attempt+1}/{self.max_retries}次, {delay:.0f}s后重试")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"[429重试] 流式HTTP {response.status_code}, 持续{self.max_retries}次, 放弃")
                    return response
            return response
        return response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._response_ctx:
            return await self._response_ctx.__aexit__(exc_type, exc_val, exc_tb)


__all__ = [
    "ChatResponse",
    "StreamChunk",
    "_StreamRetryContext",
    "_resolve_exception",
]
