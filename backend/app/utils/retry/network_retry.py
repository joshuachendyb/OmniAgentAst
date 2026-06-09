# -*- coding: utf-8 -*-
"""
调用点1:第3层 LLM服务 — HTTP 429指数退避重试

唯一调用点:BaseAIService.__init__()
_post_with_retry 和 _stream_with_retry 共用同一个engine实例。
"""
from app.utils.retry_engine import create_retry_engine


def create_network_retry_engine(
    max_retries: int = 3,
    backoff_factor: float = 2.0,
):
    """创建HTTP 429重试引擎 — 委托公共 create_retry_engine — 小欧 2026-06-09"""
    return create_retry_engine(max_retries=max_retries, backoff_factor=backoff_factor)
