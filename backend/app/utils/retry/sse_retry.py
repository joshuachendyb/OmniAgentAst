# -*- coding: utf-8 -*-
"""
调用点3：第1.5层 SSE会话 — 网络异常/超时重试

唯一调用点：generate_sse_stream_with_retry()
包裹整个 agent.run_stream()，网络断开或超时时重建Agent重新发起。
"""
from app.utils.retry_engine import RetryEngine, BackoffStrategy


def create_sse_retry_engine(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> RetryEngine:
    """创建SSE流重试引擎

    用于：generate_sse_stream_with_retry() 包裹整个 agent.run_stream()
    原理：网络断开或超时时，重建Agent，重新发起整个SSE流。
    """
    return RetryEngine(
        max_retries=max_retries,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_factor=backoff_factor,
    )
