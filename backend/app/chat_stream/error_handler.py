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


def create_error_step(
    code: str,
    message: str,
    error_type: str,
    step_num: int,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    retryable: bool = False,
    retry_after: Optional[int] = None
) -> Dict[str, Any]:
    """
    创建保存到数据库的 error_step【小沈修复2026-03-28】
    - 添加更多字段，和SSE返回保持一致

    Args:
        code: 错误码（如 TIMEOUT, SECURITY_BLOCKED）
        message: 错误信息
        error_type: 错误类型（如 timeout, security, server）
        step_num: 步骤序号
        model: 模型名称（可选）
        provider: 提供商（可选）
        retryable: 是否可重试
        retry_after: 重试等待秒数

    Returns:
        error_step 字典
    """
    return {
        'type': 'error',
        'step': step_num,
        'code': code,
        'message': message,
        'content': message,  # 和SSE一致
        'error_message': message,  # 和SSE一致
        'error_type': error_type,
        'timestamp': create_timestamp(),
        'model': model,
        'provider': provider,
        'reasoning': '',  # 和SSE一致
        'is_reasoning': False,  # 和SSE一致
        'retryable': retryable,
        'retry_after': retry_after
    }


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
    return f"data: {json.dumps(response, ensure_ascii=False)}\n\n"


def get_function_call_error_info(error: Exception) -> Dict[str, Any]:
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
    
    # httpx 异常类型映射到 ERROR_TYPE_MAP 键名
    httpx_type_map = {
        'ConnectError': 'connect_error',
        'ProtocolError': 'protocol_error',
        'ProxyError': 'proxy_error',
        'TimeoutException': 'timeout_error',
        'ReadError': 'read_error',
        'WriteError': 'write_error',
        'NetworkError': 'network_error',
    }
    
    # 如果是 httpx 异常，使用 ERROR_TYPE_MAP
    if error_type in httpx_type_map:
        map_key = httpx_type_map[error_type]
        if map_key in ERROR_TYPE_MAP:
            error_code, error_message = ERROR_TYPE_MAP[map_key]
            return {
                "code": error_type.upper(),
                "message": error_message,
                "error_type": error_code,
                "retryable": True,
                "retry_after": 10 if error_code in ['connect', 'network', 'protocol'] else 5
            }
    
    # 其他错误类型继续使用原有逻辑
    if error_type == "TimeoutError" or "timeout" in error_msg:
        return {
            "code": "TIMEOUT",
            "message": "请求超时，请重试",
            "error_type": "timeout",
            "retryable": True,
            "retry_after": 5
        }
    elif error_type == "ConnectionError" or "connection" in error_msg:
        return {
            "code": "CONNECTION_ERROR",
            "message": "连接失败，请检查网络",
            "error_type": "connect",
            "retryable": True,
            "retry_after": 10
        }
    elif error_type == "HTTPError" or "http" in error_msg:
        return {
            "code": "HTTP_ERROR",
            "message": "服务器响应异常，请稍后重试",
            "error_type": "server",
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
    # 【新增 2026-04-09 小沈】HTTP错误码处理
    elif "503" in error_msg or "无可用渠道" in error_msg:
        return {
            "code": "API_CHANNEL_UNAVAILABLE",
            "message": "AI服务渠道不可用 (errorcode=503)，请检查API配置或更换模型",
            "error_type": "api_error",
            "retryable": False
        }
    elif "429" in error_msg or "rate limit" in error_msg.lower() or "limit_error" in error_msg or "配额" in error_msg:
        return {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": "API请求过于频繁 (errorcode=429)，请稍后再试或更换模型",
            "error_type": "api_error",
            "retryable": True,
            "retry_after": 30
        }
    elif "401" in error_msg or "认证" in error_msg or "unauthorized" in error_msg.lower():
        return {
            "code": "AUTH_FAILED",
            "message": "API认证失败 (errorcode=401)，请检查API密钥配置",
            "error_type": "security",
            "retryable": False
        }
    elif "403" in error_msg or "forbidden" in error_msg.lower():
        return {
            "code": "FORBIDDEN",
            "message": "API访问被拒绝 (errorcode=403)，请检查API权限配置",
            "error_type": "security",
            "retryable": False
        }
    elif "400" in error_msg:
        return {
            "code": "BAD_REQUEST",
            "message": "API请求参数错误 (errorcode=400)，请检查输入内容",
            "error_type": "validation",
            "retryable": False
        }
    elif "500" in error_msg:
        return {
            "code": "SERVER_ERROR",
            "message": "AI服务内部错误 (errorcode=500)，请稍后重试或更换模型",
            "error_type": "server",
            "retryable": True,
            "retry_after": 10
        }
    elif "502" in error_msg or "502" in error_msg:
        return {
            "code": "BAD_GATEWAY",
            "message": "AI服务网关错误 (errorcode=502)，请稍后重试",
            "error_type": "server",
            "retryable": True,
            "retry_after": 10
        }
    elif "504" in error_msg:
        return {
            "code": "GATEWAY_TIMEOUT",
            "message": "AI服务响应超时 (errorcode=504)，请稍后重试",
            "error_type": "timeout",
            "retryable": True,
            "retry_after": 15
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
    'connect_error': ('connect', '连接失败，请检查网络'),
    'protocol_error': ('protocol', '协议错误，请重试'),
    'proxy_error': ('protocol', '代理错误，请检查网络配置'),
    'write_error': ('server', '发送请求失败'),
    'network_error': ('network', '网络错误，请检查网络连接'),
    # 【新增 2026-04-09 小沈】HTTP错误码映射
    'api_error_503': ('api_error', 'AI服务渠道不可用 (errorcode=503)，请检查API配置或更换模型'),
    'api_error_429': ('api_error', 'API请求过于频繁 (errorcode=429)，请稍后再试或更换模型'),
    'api_error_401': ('security', 'API认证失败 (errorcode=401)，请检查API密钥配置'),
    'api_error_403': ('security', 'API访问被拒绝 (errorcode=403)，请检查API权限配置'),
    'api_error_400': ('validation', 'API请求参数错误 (errorcode=400)，请检查输入内容'),
    'api_error_500': ('server', 'AI服务内部错误 (errorcode=500)，请稍后重试或更换模型'),
    'api_error_502': ('server', 'AI服务网关错误 (errorcode=502)，请稍后重试'),
    'api_error_504': ('timeout', 'AI服务响应超时 (errorcode=504)，请稍后重试'),
    # 【新增 2026-04-01】LLM 返回空内容或未知错误
    'unknown': ('server', 'AI服务暂无响应，请稍后重试'),
    'empty_response': ('server', 'AI服务返回空响应，请稍后重试'),
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


def get_stream_error_info(error_type: str) -> tuple[str, str]:
    """
    根据错误类型获取错误码和用户友好的错误信息
    
    【新增 2026-04-01 小沈】
    用于 chat_stream_query.py 中从 ERROR_TYPE_MAP 获取错误信息
    
    Args:
        error_type: 错误类型标识（如 connect_error, protocol_error, timeout_error 等）
    
    Returns:
        (error_code, message) 元组
        - error_code: 5种类型之一（timeout/connect/protocol/server/network）
        - message: 用户友好的错误提示
    """
    if error_type in ERROR_TYPE_MAP:
        return ERROR_TYPE_MAP[error_type]
    else:
        # 默认返回 server 类型
        return 'server', f"服务调用失败，请稍后重试"


def classify_llm_error(error_info: str) -> str:
    """
    根据 LLM 返回的错误信息分类错误类型
    
    【新增 2026-04-01 小沈】
    用于 llm_strategies.py 中分类 LLM 返回的错误
    
    Args:
        error_info: LLM 返回的错误信息（如 "ReadTimeout", "ConnectError", ""）
    
    Returns:
        error_type: 错误类型标识，对应 ERROR_TYPE_MAP 的 key
    """
    if not error_info:
        # 没有具体错误信息，按空响应处理
        return 'empty_response'
    
    error_lower = error_info.lower()
    
    # 按优先级匹配
    if 'timeout' in error_lower or 'timed out' in error_lower:
        return 'timeout_error'
    elif 'connect' in error_lower:
        return 'connect_error'
    elif 'read' in error_lower:
        return 'read_error'
    elif 'write' in error_lower:
        return 'write_error'
    elif 'protocol' in error_lower:
        return 'protocol_error'
    elif 'proxy' in error_lower:
        return 'proxy_error'
    elif 'network' in error_lower or 'dns' in error_lower or 'refused' in error_lower:
        return 'network_error'
    else:
        return 'unknown'


def resolve_http_error_type(error_message: str) -> Optional[str]:
    """
    从错误消息字符串中解析并返回 HTTP 错误类型标识
    
    【重构 2026-04-10 小沈】
    从 chat_stream_query.py 迁移到此模块，符合单一职责原则
    
    优先级匹配原则：
    1. 优先使用原始HTTP错误码（429、500等）- 保留API返回的真实信息
    2. 没有错误码时，才从语义推断 - 作为备用方案
    
    Args:
        error_message: 原始错误消息字符串
    
    Returns:
        HTTP 错误类型标识（如 'api_error_429', 'api_error_500' 等）
        如果无法解析，返回 None
    """
    if not error_message:
        return None
    
    msg_lower = error_message.lower()
    
    # 1. 优先匹配数字错误码（原始HTTP状态码），保留API返回的真实信息
    if "429" in error_message:
        return 'api_error_429'
    elif "503" in error_message:
        return 'api_error_503'
    elif "500" in error_message:
        return 'api_error_500'
    elif "502" in error_message:
        return 'api_error_502'
    elif "504" in error_message:
        return 'api_error_504'
    elif "401" in error_message:
        return 'api_error_401'
    elif "403" in error_message:
        return 'api_error_403'
    elif "400" in error_message:
        return 'api_error_400'
    
    # 2. 没有数字错误码时，才从语义推断
    elif "rate limit" in msg_lower or "too many requests" in msg_lower:
        return 'api_error_429'
    elif "limit_error" in msg_lower:
        return 'api_error_429'
    elif "auth" in msg_lower or "unauthorized" in msg_lower:
        return 'api_error_401'
    elif "forbidden" in msg_lower:
        return 'api_error_403'
    
    return None
