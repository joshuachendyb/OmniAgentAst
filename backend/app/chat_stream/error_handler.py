# -*- coding: utf-8 -*-
"""
统一错误处理模块

从 chat_stream.py 拆分出来
职责：统一的错误处理
Author: 小沈 - 2026-03-22
"""

import json
import re
from typing import Any, Dict, Optional

from app.constants import ERROR_TYPE_MAP, HTTPX_EXCEPTION_TO_ERROR_KEY, HTTP_STATUS_MAP_ENTRIES, PATTERN_ERROR_ENTRIES
from app.utils.time_utils import create_timestamp
from app.services.agent.reasoning_steps import StepFactory


def _build_error_response(code: str, msg_key: str, retryable: bool,
                           retry_after: Optional[int] = None,
                           message: Optional[str] = None) -> Dict[str, Any]:
    """统一构建错误响应字典。使用 ERROR_TYPE_MAP 获取标准错误消息。"""
    error_type, default_message = ERROR_TYPE_MAP.get(
        msg_key, ("unknown", "AI服务暂无响应，请稍后重试"))
    result: Dict[str, Any] = {
        "code": code,
        "message": message if message is not None else default_message,
        "error_type": error_type,
        "retryable": retryable,
    }
    if retry_after is not None:
        result["retry_after"] = retry_after
    return result


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
    创建统一的错误响应格式 — 委托给sse_formatter统一入口
    
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
    from app.chat_stream.sse_formatter import format_error_sse
    return format_error_sse(
        error_type=error_type,
        error_message=error_message,
        step=step,
        model=model,
        provider=provider,
        details=details,
        stack=stack,
        recoverable=recoverable,
        retry_after=retry_after
    )


def get_function_call_error_info(error: Exception) -> Dict[str, Any]:
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # P1: IdleTimeoutError 特殊处理
    try:
        from app.utils.idle_timeout import IdleTimeoutError
        if isinstance(error, IdleTimeoutError):
            return _build_error_response("IDLE_TIMEOUT", "idle_timeout",
                                          retryable=True, retry_after=5)
    except ImportError:
        pass

    # P2: httpx 异常 → 数据驱动查表
    if error_type in HTTPX_EXCEPTION_TO_ERROR_KEY:
        msg_key = HTTPX_EXCEPTION_TO_ERROR_KEY[error_type]
        retry_after = 10 if msg_key in ("connect_error", "network_error", "protocol_error") else 5
        return _build_error_response(error_type.upper(), msg_key,
                                      retryable=True, retry_after=retry_after)

    # P3: 字符串模式匹配 — 数据表驱动（替换原6个if/elif P3a-P3f）
    for entry in PATTERN_ERROR_ENTRIES:
        if error_type in entry["types"] or \
           any(kw in error_msg for kw in entry["keywords"]):
            return _build_error_response(entry["code"], entry["msg_key"],
                                          entry["retryable"], entry.get("retry_after"))

    # P4: HTTP 状态码/关键词 → 查 HTTP_STATUS_MAP_ENTRIES 数据表
    for entry in HTTP_STATUS_MAP_ENTRIES:
        if any(code in error_msg for code in entry["codes"]) or \
           any(kw in error_msg for kw in entry.get("keywords", [])):
            return _build_error_response(entry["code"], entry["msg_key"],
                                          entry["retryable"], entry.get("retry_after"))

    # O1: 兜底
    return _build_error_response("UNKNOWN_ERROR", "unknown_fallback", retryable=True, retry_after=5)



def get_stream_error_info(error_type: str, original_message: str = None) -> tuple[str, str]:
    """
    根据错误类型获取错误码和用户友好的错误信息
    
    【新增 2026-04-01 小沈】
    用于 chat_stream_query.py 中从 ERROR_TYPE_MAP 获取错误信息
    
    【重构 2026-04-10 小沈】
    增加 original_message 参数，优先使用原始错误消息
    
    Args:
        error_type: 错误类型标识（如 connect_error, protocol_error, api_error_429 等）
        original_message: 原始错误消息，如果有则优先使用
    
    Returns:
        (error_code, message) 元组
        - error_code: 错误类型（timeout/connect/protocol/server/network）
        - message: 错误消息，优先使用原始消息
    """
    # 获取错误类型对应的错误码
    if error_type in ERROR_TYPE_MAP:
        error_code, default_message = ERROR_TYPE_MAP[error_type]
    else:
        error_code, default_message = 'server', f"服务调用失败，请稍后重试"
    
    # 优先使用原始错误消息，保留API返回的真实信息
    if original_message and original_message.strip():
        # 【新增 2026-04-10】提取 message 和 type 追加到用户友好提示后
        original_info = _extract_message_and_type(original_message)
        if original_info:
            message = f"{default_message}\n原始信息: {original_info}"
        else:
            # 【修复 2026-04-10】提取不到时仍用默认提示，不直接用原始消息
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
    
    【重构 小健 2026-05-24】统一引用 constants.HTTP_STATUS_TO_ERROR_TYPE 映射表
    """
    if not error_message:
        return None
    
    from app.constants import HTTP_STATUS_TO_ERROR_TYPE, API_ERROR_429, API_ERROR_401, API_ERROR_403
    
    for match in re.finditer(r'\b(\d{3})\b', error_message):
        code = int(match.group(1))
        if code in HTTP_STATUS_TO_ERROR_TYPE:
            return HTTP_STATUS_TO_ERROR_TYPE[code]
    
    msg_lower = error_message.lower()
    if "rate limit" in msg_lower or "too many requests" in msg_lower or "limit_error" in msg_lower:
        return API_ERROR_429
    if "auth" in msg_lower or "unauthorized" in msg_lower:
        return API_ERROR_401
    if "forbidden" in msg_lower:
        return API_ERROR_403
    
    return None


def create_error_from_exception(
    error: Exception,
    step_num: int,
    model: Optional[str] = None,
    provider: Optional[str] = None
) -> tuple[str, Dict[str, Any]]:
    """
    统一的异常错误处理函数 - 解析异常、组装错误信息、创建错误响应和步骤
    
    【新增 2026-04-10 小沈】
    用于 react_sse_wrapper.py 中处理 Exception 对象
    
    统一处理：
    1. 解析异常（调用 get_function_call_error_info）
    2. 创建 error_response（yield给前端）
    3. 创建 error_step（保存到数据库）
    
    Args:
        error: 异常对象
        step_num: 步骤序号
        model: 模型名称（可选）
        provider: 提供商（可选）
    
    Returns:
        (error_response, error_step) 元组
        - error_response: SSE格式的错误响应字符串，用于yield给前端
        - error_step: 错误步骤字典，用于保存到数据库
    """
    # 1. 解析异常
    error_info = get_function_call_error_info(error)
    
    error_code = error_info.get("code", "INTERNAL_ERROR")
    error_message = error_info.get("message", "服务调用失败")
    error_type = error_info.get("error_type", "server")
    retryable = error_info.get("retryable", False)
    retry_after = error_info.get("retry_after")
    
    # 2. 创建 error_response（yield给前端）
    error_response = create_error_response(
        error_type=error_type,
        error_message=error_message,
        model=model,
        provider=provider,
        recoverable=retryable,
        retry_after=retry_after,
        step=step_num
    )
    
    # 3. 创建 error_step（保存到数据库）— 小健 2026-05-27：直接用StepFactory
    error_step = StepFactory.create_error_step(
        step=step_num,
        error_type=error_type,
        error_message=error_message,
        recoverable=retryable,
        model=model,
        provider=provider,
        context={"step": step_num, "model": model, "provider": provider, "thought_content": ""},
        retry_after=retry_after
    ).to_dict()
    
    return error_response, error_step

