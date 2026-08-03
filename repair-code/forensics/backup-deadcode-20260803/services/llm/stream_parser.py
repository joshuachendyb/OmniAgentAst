# -*- coding: utf-8 -*-
"""
LLM流式响应解析 — StreamChunk工厂函数

小健 2026-05-27
小沈 2026-06-13 删除死代码parse_sse_stream/handle_http_error_stream,仅保留工厂函数
"""

from app.services.llm.core import StreamChunk



def create_cancelled_chunk(model: str) -> StreamChunk:
    """创建取消响应片段 — 小健 2026-05-27"""
    return StreamChunk(content="", model=model, is_done=True,
                       stream_error="Request cancelled",
                       stream_error_type="cancelled")


def create_error_chunk(model: str, error: str, error_type: str = "http_error") -> StreamChunk:
    """创建错误响应片段 — 小健 2026-05-27"""
    return StreamChunk(content="", model=model, is_done=True,
                       stream_error=error,
                       stream_error_type=error_type)


__all__ = [
    "create_cancelled_chunk",
    "create_error_chunk",
]
