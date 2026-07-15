# -*- coding: utf-8 -*-
"""
LLM核心数据类与辅助函数 — SRP拆分自llm_core.py — 小健 2026-05-27

职责:定义LLM层的响应数据类(ChatResponse、StreamChunk)、异常解析(_resolve_exception)。

编辑历史:
  小欧 - 2026-07-15: FCFormatError.__init__加self.message=message,补缺失的实例属性(写测试挖出的预存bug)

拆分原则:数据/辅助定义与BaseAIService主服务类分离,遵循SRP。
对外透明:llm_core.py重新导出这些类,外部import路径不变。
"""

from typing import List, Dict, Optional
from app.services.llm.error_classifier import SystemErrorClassifier


class FCFormatError(Exception):
    """FC格式错误 — LLM返回的tool_calls无法解析 — 小欧 2026-06-25"""
    def __init__(self, *, message: str, details: dict = None):
        super().__init__(message)
        self.message = message  # 小欧 2026-07-15: 补缺失实例属性,防_format_fc_error访问e.message时AttributeError
        self.details = details or {}


def _resolve_exception(e: Exception) -> tuple:
    """解析异常→(用户消息, 错误类型) — 委托至SystemErrorClassifier统一分类 — 小沈 2026-05-28"""
    info = SystemErrorClassifier.get_error_info(e)
    msg = info["message"]
    err_type = info["code"]
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
    """流式响应片段 — FC-only: tool_calls原生传递,不走JSON roundtrip — 小沈 2026-06-12; 小健 2026-06-17 新增usage"""
    def __init__(self, content: str, model: str, is_done: bool = False,
                 stream_error: Optional[str] = None, stream_error_type: Optional[str] = None,
                 reasoning: Optional[str] = None, is_reasoning: bool = False,
                 tool_calls: Optional[List[Dict]] = None,
                 raw_data: str = "",
                 usage: Optional[Dict] = None):
        self.content = content
        self.model = model
        self.is_done = is_done
        self.stream_error = stream_error
        self.stream_error_type = stream_error_type
        self.reasoning = reasoning
        self.is_reasoning = is_reasoning
        self.tool_calls = tool_calls or []
        self.raw_data = raw_data
        self.usage = usage


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
    "ChatResponse",
    "StreamChunk",
    "FCFormatError",
    "_resolve_exception",
    "create_cancelled_chunk",
    "create_error_chunk",
]
