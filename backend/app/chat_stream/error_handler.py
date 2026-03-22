# -*- coding: utf-8 -*-
"""
统一错误处理模块

从 chat_stream.py 拆分出来
职责：统一的错误处理
Author: 小沈 - 2026-03-22
"""

import json
from typing import Dict, Any, Optional

from app.chat_stream.chat_helpers import create_timestamp


def create_error_response(
    error_type: str,
    message: str,
    code: str = "INTERNAL_ERROR",
    model: Optional[str] = None,
    provider: Optional[str] = None,
    details: Optional[str] = None,
    stack: Optional[str] = None,
    retryable: bool = False,
    retry_after: Optional[int] = None,
    step: Optional[int] = None
) -> str:
    """
    创建统一的错误响应格式
    
    Args:
        error_type: 错误类型（如 timeout_error, connection_error 等）
        message: 用户友好的错误信息
        code: 错误码（如 TIMEOUT, NOT_FOUND, SECURITY_BLOCKED）
        model: 模型名称（可选）
        provider: 提供商（可选）
        details: 详细错误信息（可选）
        stack: 堆栈信息（可选，仅用于调试）
        retryable: 是否可重试（可选）
        retry_after: 重试等待秒数（可选）
        step: 步骤序号（可选）
    
    Returns:
        SSE 格式的错误响应字符串
    """
    response: Dict[str, Any] = {
        'type': 'error',
        'code': code,
        'message': message,
        'error_type': error_type
    }
    if step is not None:
        response['step'] = step
    if model is not None:
        response['model'] = model
    if provider is not None:
        response['provider'] = provider
    if details:
        response['details'] = details
    if stack:
        response['stack'] = stack
    if retryable:
        response['retryable'] = retryable
    if retry_after is not None:
        response['retry_after'] = retry_after
    response['timestamp'] = create_timestamp()
    return f"data: {json.dumps(response)}\n\n"


def get_user_friendly_error(error: Exception) -> Dict[str, Any]:
    """
    获取用户友好的错误信息
    
    Args:
        error: 异常对象
    
    Returns:
        错误信息字典，包含 code, message, error_type, retryable
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()
    
    # 优先处理 IdleTimeoutError
    try:
        from app.utils.idle_timeout import IdleTimeoutError
        if isinstance(error, IdleTimeoutError):
            return {
                "code": "IDLE_TIMEOUT",
                "message": "请求超时：AI模型30秒内未返回任何内容，已重试3次，请更换问题或稍后重试",
                "error_type": "timeout",
                "retryable": True,
                "retry_after": 5
            }
    except ImportError:
        pass
    
    # 根据错误类型返回用户友好的错误信息
    if error_type == "TimeoutError" or "timeout" in error_msg:
        return {
            "code": "TIMEOUT",
            "message": "请求超时，请重试",
            "error_type": "network",
            "retryable": True,
            "retry_after": 5
        }
    elif error_type == "ConnectionError" or "connection" in error_msg:
        return {
            "code": "CONNECTION_ERROR",
            "message": "网络连接失败，请检查网络",
            "error_type": "network",
            "retryable": True,
            "retry_after": 10
        }
    elif error_type == "HTTPError" or "http" in error_msg:
        return {
            "code": "HTTP_ERROR",
            "message": "服务器响应异常，请稍后重试",
            "error_type": "network",
            "retryable": True,
            "retry_after": 10
        }
    elif error_type == "ValueError":
        return {
            "code": "VALIDATION_ERROR",
            "message": "参数值错误，请检查输入",
            "error_type": "validation",
            "retryable": False
        }
    elif "not found" in error_msg or "不存在" in error_msg:
        return {
            "code": "NOT_FOUND",
            "message": "文件或资源不存在",
            "error_type": "file_system",
            "retryable": False
        }
    elif "permission" in error_msg or "权限" in error_msg:
        return {
            "code": "PERMISSION_DENIED",
            "message": "权限不足，无法执行操作",
            "error_type": "security",
            "retryable": False
        }
    else:
        return {
            "code": "UNKNOWN_ERROR",
            "message": "AI 处理异常，请稍后重试",
            "error_type": "unknown",
            "retryable": True,
            "retry_after": 5
        }


# 错误类型映射表（用于重试失败后的错误分类）
ERROR_TYPE_MAP = {
    'idle_timeout': ('timeout', '请求超时：AI模型30秒内未返回任何内容，已重试3次，请更换问题或稍后重试'),
    'timeout_error': ('timeout', '请求超时，请重试'),
    'read_error': ('server', '读取响应失败，请重试'),
    'connect_error': ('network', '连接失败，请检查网络'),
    'protocol_error': ('server', '协议错误，请重试'),
    'proxy_error': ('network', '代理错误，请检查网络配置'),
    'write_error': ('server', '发送请求失败'),
    'network_error': ('network', '网络错误，请检查网络连接'),
}


def classify_error(error_type: str, error_message: str = "") -> tuple[str, str]:
    """
    根据错误类型分类，获取用户友好的错误信息
    
    Args:
        error_type: 错误类型标识
        error_message: 原始错误信息
    
    Returns:
        (code, message) 元组
    """
    if error_type in ERROR_TYPE_MAP:
        return ERROR_TYPE_MAP[error_type]
    else:
        return 'server', f"服务调用失败: {error_message}"
