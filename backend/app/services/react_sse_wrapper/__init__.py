# -*- coding: utf-8 -*-
"""
react_sse_wrapper — 从 react_sse_wrapper.py 拆出的职责

- _core: SSE流式生成主流程
- task操作统一在 services/task/ 层

Author: 小沈 - 2026-05-31
统一: 小健 - 2026-05-31 — task操作移出本层
"""

from app.services.react_sse_wrapper.react_sse_wrapper import (
    SSEConfig,
    generate_sse_stream,
    generate_sse_stream_with_retry,
)

__all__ = [
    "generate_sse_stream",
    "generate_sse_stream_with_retry",
]
