# -*- coding: utf-8 -*-
"""
LLM核心数据类与辅助函数 — SRP拆分自llm_core.py — 小健 2026-05-27

职责:定义LLM层的响应数据类(ChatResponse、StreamChunk)、异常解析(_resolve_exception)。

拆分原则:数据/辅助定义与BaseAIService主服务类分离,遵循SRP。
对外透明:llm_core.py重新导出这些类,外部import路径不变。
"""

from typing import List, Dict, Optional

from app.utils.logger import logger


def _resolve_exception(e: Exception) -> tuple:
    """解析异常→(用户消息, 错误类型) — 委托至UnifiedErrorClassifier统一分类 — 小沈 2026-05-28"""
    from app.utils.error_classifier import UnifiedErrorClassifier
    info = UnifiedErrorClassifier.get_error_info(e)
    msg = info["message"]
    err_type = info["code"]
    if info["category"].value == "unknown":
        logger.error(f"[_resolve_exception] 未知异常: {e}, 类型: {type(e).__name__}")
    return msg, err_type


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


__all__ = [
    "ChatResponse",
    "StreamChunk",
    "_resolve_exception",
]
