# -*- coding: utf-8 -*-
"""
LLM流式响应解析器 — SRP拆分自llm_core.py — 小健 2026-05-27

职责：SSE流解析、HTTP错误处理、取消检测。
从BaseAIService提取，遵循SRP原则。

Author: 小健 - 2026-05-27
"""

import json
import asyncio
from typing import AsyncGenerator

from app.utils.logger import logger
from app.services.llm.core import StreamChunk


async def parse_sse_stream(
    response,
    model: str,
    cancelled_flag_func,
    log_tag: str = "sse"
) -> AsyncGenerator[StreamChunk, None]:
    """通用SSE解析生成器 — 小健 2026-05-27

    从HTTP响应中解析SSE流，yield StreamChunk。
    包含：wait_for心跳、取消检查、data:前缀解析、[DONE]处理、choices[0].delta提取。

    Args:
        response: httpx响应对象
        model: 模型名称
        cancelled_flag_func: 返回是否取消的函数
        log_tag: 日志标签

    Yields:
        StreamChunk: 流式响应片段
    """
    line_iterator = response.aiter_lines()
    _reasoning_content_total = 0
    _content_total = 0

    while True:
        try:
            line = await asyncio.wait_for(line_iterator.__anext__(), timeout=1.0)
        except asyncio.TimeoutError:
            if cancelled_flag_func():
                yield StreamChunk(content="", model=model, is_done=True,
                                  stream_error="Request cancelled",
                                  stream_error_type="cancelled")
                return
            continue
        except StopAsyncIteration:
            break

        if cancelled_flag_func():
            yield StreamChunk(content="", model=model, is_done=True,
                              stream_error="Request cancelled",
                              stream_error_type="cancelled")
            return

        if not line or not line.strip():
            continue

        if line.startswith("data: "):
            data_str = line[6:]
        elif line.startswith("data:"):
            data_str = line[5:]
        else:
            continue

        if data_str.strip() == "[DONE]":
            logger.info(f"[{log_tag}] 流结束, content_total={_content_total}, reasoning_total={_reasoning_content_total}")
            yield StreamChunk(content="", model=model, is_done=True)
            return

        try:
            data = json.loads(data_str)
            choices = data.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                content = delta.get("content", "") or ""
                reasoning_content = delta.get("reasoning_content", "") or ""

                if content:
                    _content_total += len(content)
                    yield StreamChunk(content=content, model=model, is_done=False, is_reasoning=False)

                if reasoning_content:
                    _reasoning_content_total += len(reasoning_content)
                    if _reasoning_content_total == len(reasoning_content):
                        logger.info(f"[{log_tag}] 首次收到reasoning, model={model}")
                    yield StreamChunk(content=reasoning_content, model=model, is_done=False, is_reasoning=True)
        except json.JSONDecodeError:
            continue

    yield StreamChunk(content="", model=model, is_done=True)


async def handle_http_error_stream(
    response,
    model: str,
    log_tag: str = "http_error"
) -> AsyncGenerator[StreamChunk, None]:
    """处理HTTP错误响应流 — 小健 2026-05-27

    Args:
        response: httpx响应对象
        model: 模型名称
        log_tag: 日志标签

    Yields:
        StreamChunk: 包含错误信息的流式片段
    """
    try:
        error_text = await response.aread()
        error_text = error_text.decode("utf-8", errors="ignore")
        logger.error(f"[{log_tag}] HTTP {response.status_code}: {error_text[:500]}")
        yield StreamChunk(content="", model=model, is_done=True,
                          stream_error=f"HTTP {response.status_code}: {error_text[:200]}",
                          stream_error_type="http_error")
    except Exception as e:
        logger.error(f"[{log_tag}] 读取错误响应失败: {e}")
        yield StreamChunk(content="", model=model, is_done=True,
                          stream_error=f"HTTP {response.status_code} error",
                          stream_error_type="http_error")


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
    "parse_sse_stream",
    "handle_http_error_stream",
    "create_cancelled_chunk",
    "create_error_chunk",
]
