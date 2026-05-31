# -*- coding: utf-8 -*-
"""
统一错误处理模块

从 chat_stream.py 拆分出来
职责：统一的错误处理
Author: 小沈 - 2026-03-22
Updated: 小欧 - 2026-05-30 改用 ErrorStep + format_agent_sse
"""

import json
import re
from typing import Any, Dict, Optional

from app.utils.time_utils import create_timestamp
from app.services.agent.steps import StepFactory
from app.chat_stream.sse_formatter import format_agent_sse


def create_error_response(
    error_type: str,
    error_message: str,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    details: Optional[str] = None,
    stack: Optional[str] = None,
    recoverable: Optional[bool] = None,
    retry_after: Optional[int] = None,
    step: Optional[int] = None
) -> str:
    """
    创建统一的错误响应格式 — 使用 ErrorStep + format_agent_sse
    
    Args:
        error_type: 错误类型
        error_message: 错误信息
        model: 模型名称（可选）
        provider: 提供商（可选）
        details: 详细错误信息（可选）
        stack: 堆栈信息（可选）
        recoverable: 是否可恢复
        retry_after: 重试等待秒数（可选）
        step: 步骤序号（可选）
    
    Returns:
        SSE 格式的错误响应字符串
    """
    error_step = StepFactory.create_error_step(
        step=step or 0,
        error_type=error_type,
        error_message=error_message,
        model=model,
        provider=provider,
        recoverable=recoverable or False,
        retry_after=retry_after,
        details=details,
        stack=stack
    )
    return format_agent_sse(error_step)


def get_function_call_error_info(error: Exception) -> Dict[str, Any]:
    from app.utils.error_classifier import UnifiedErrorClassifier
    info = UnifiedErrorClassifier.get_error_info(error)
    category = info["category"]
    return {
        "code": category.name,
        "message": info["message"],
        "error_type": info["code"],
        "retryable": info["retryable"],
        "retry_after": 5 if info["retryable"] else None,
    }



def get_stream_error_info(error_type: str, original_message: str = None) -> tuple[str, str]:
    """
    根据错误类型获取错误码和用户友好的错误信息
    
    【重构 2026-05-28 小沈】
    委托至 UnifiedErrorClassifier.classify_error_message 统一分类
    
    Args:
        error_type: 错误类型标识（如 api_error_429, connect, timeout 等）
        original_message: 原始错误消息，如果有则优先使用
    
    Returns:
        (error_code, message) 元组
        - error_code: 错误类型（timeout/connect/protocol/server/network）
        - message: 错误消息，优先使用原始消息
    """
    from app.utils.error_classifier import UnifiedErrorClassifier
    error_code, default_message = UnifiedErrorClassifier.classify_error_message(error_type, original_message)
    
    if original_message and original_message.strip():
        original_info = _extract_message_and_type(original_message)
        if original_info:
            message = f"{default_message}\n原始信息: {original_info}"
        else:
            message = default_message
    else:
        message = default_message
    
    return error_code, message


def _extract_message_and_type(error_message: str) -> str:
    """
    提取原始错误信息中的 message、type、param、code
    
    【新增 2026-04-10】
    【增强 2026-04-10】增加 param 和 code 字段
    从原始错误（如 {"error":{"message":"...","type":"...","param":"...","code":"..."}}）中解析提取
    
    Args:
        error_message: 原始错误消息字符串
    
    Returns:
        格式化后的字符串，如 "message=..., type=..., param=..., code=..."
        如果无法解析，返回空字符串
    """
    if not error_message:
        return ""
    
    # 匹配 {"error":{"message":"...","type":"...","param":"...","code":"..."...}}
    json_match = re.search(r'\{["\']?error["\']?\s*:\s*\{([^}]+)\}', str(error_message), re.IGNORECASE)
    if json_match:
        inner = json_match.group(1)
        # 提取 message
        msg_match = re.search(r'["\']?message["\']?\s*:\s*["\']([^"\']+)["\']', inner, re.IGNORECASE)
        # 提取 type
        type_match = re.search(r'["\']?type["\']?\s*:\s*["\']([^"\']+)["\']', inner, re.IGNORECASE)
        # 提取 param
        param_match = re.search(r'["\']?param["\']?\s*:\s*["\']([^"\']*)["\']', inner, re.IGNORECASE)
        # 提取 code
        code_match = re.search(r'["\']?code["\']?\s*:\s*["\']([^"\']+)["\']', inner, re.IGNORECASE)
        
        parts = []
        if msg_match:
            parts.append(f"message={msg_match.group(1)}")
        if type_match:
            parts.append(f"type={type_match.group(1)}")
        if param_match and param_match.group(1):
            parts.append(f"param={param_match.group(1)}")
        if code_match:
            parts.append(f"code={code_match.group(1)}")
        
        if parts:
            return ", ".join(parts)
    
    return ""


def resolve_http_error_type(error_message: str) -> Optional[str]:
    """
    从错误消息字符串中解析并返回 HTTP 错误类型标识
    
    【重构 小健 2026-05-31】委托给UnifiedErrorClassifier，消除重复分类逻辑
    """
    if not error_message:
        return None
    
    from app.utils.error_classifier import UnifiedErrorClassifier
    category = UnifiedErrorClassifier.classify_error(error_message)
    if category.value == "unknown":
        return None
    return category.value

