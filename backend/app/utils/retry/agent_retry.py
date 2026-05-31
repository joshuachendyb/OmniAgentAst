# -*- coding: utf-8 -*-
"""
调用点2：第2层 Agent循环 — Parse + 空响应重试

唯一调用点：BaseAgent.__init__()
一次调用返回两个engine（parse_engine, empty_engine），
分别供 _handle_parse_error 和 _handle_empty_response 使用。
"""
from typing import Tuple
from app.utils.retry_engine import RetryEngine, BackoffStrategy


def create_agent_retry_engine(
    parse_max_retries: int = 3,
    parse_backoff_factor: float = 2.0,
    empty_max_retries: int = 2,
    empty_backoff_factor: float = 1.0,
) -> Tuple[RetryEngine, RetryEngine]:
    """创建Agent循环重试引擎（一次返回两个）

    原理：LLM返回格式错误或空响应时，修改prompt/截断历史后重新调LLM。
    """
    parse_engine = RetryEngine(
        max_retries=parse_max_retries,
        backoff_strategy=BackoffStrategy.EXPONENTIAL,
        backoff_factor=parse_backoff_factor,
    )
    empty_engine = RetryEngine(
        max_retries=empty_max_retries,
        backoff_strategy=BackoffStrategy.FIXED,
        backoff_factor=empty_backoff_factor,
    )
    return parse_engine, empty_engine
