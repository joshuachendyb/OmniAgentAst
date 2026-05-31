# -*- coding: utf-8 -*-
"""
调用点1：第3层 LLM服务 — HTTP 429指数退避重试

唯一调用点：BaseAIService.__init__()
_post_with_retry 和 _stream_with_retry 共用同一个engine实例。
"""
from app.utils.retry_engine import RetryEngine, BackoffStrategy


def create_network_retry_engine(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> RetryEngine:
    """创建HTTP 429重试引擎

    用于：BaseAIService._post_with_retry / _stream_with_retry
    原理：HTTP 429时等待退避后重发同一个请求，等服务端冷却。
    """
    return RetryEngine(
        max_retries=max_retries,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_factor=backoff_factor,
    )
