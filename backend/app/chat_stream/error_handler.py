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
    'api_error_524': ('api_error', 'AI服务已超载 (errorcode=524)，请更换模型或稍后重试'),
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
    
    import re
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
    elif "524" in error_message:
        return 'api_error_524'
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


def create_session_error_result(
    original_error: Optional[str],
    error_step_type: str,
    step_num: int,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    display_name: Optional[str] = None,
    chat_timeout: Optional[int] = None,
    max_retries: Optional[int] = None,
    retryable: bool = True,
    retry_after: int = 3
) -> tuple[str, Dict[str, Any]]:
    """
    统一的会话级错误处理函数
    
    【新增 2026-04-10 小沈】统一错误处理流程：
    1. 解析错误码（调用 resolve_http_error_type）
    2. 组装错误信息（调用 get_stream_error_info）
    3. 处理特殊情况（如 idle_timeout）
    4. 创建 error_response（yield给前端）
    5. 创建 error_step（保存到数据库）
    
    用于：
    - 聊天API超时耗尽
    - 认证/权限失败
    - 安全拦截
    - API完全不可用（429、500等）
    - 功能未实现
    
    特点：
    - 发生错误后就是最后一步
    - yield给前端 + 保存到DB + 结束会话
    
    Args:
        original_error: 原始错误消息（来自API或异常）
        error_step_type: 错误步骤类型（如 'idle_timeout', 'network_error' 等）
        step_num: 步骤序号
        model: 模型名称（可选）
        provider: 提供商（可选）
        display_name: 模型显示名称（用于idle_timeout提示）
        chat_timeout: 单次超时时间秒数（用于idle_timeout提示）
        max_retries: 最大重试次数（用于idle_timeout提示）
        retryable: 是否可重试
        retry_after: 重试等待秒数
    
    Returns:
        (error_response, error_step) 元组
        - error_response: SSE格式的错误响应字符串，用于yield给前端
        - error_step: 错误步骤字典，用于保存到数据库
    """
    # 1. 解析错误码
    resolved_error_type = resolve_http_error_type(original_error) if original_error else None
    final_error_type = resolved_error_type if resolved_error_type else error_step_type
    
    # 2. 组装错误信息
    error_type, error_message = get_stream_error_info(final_error_type, original_error)
    
    # 3. 处理特殊情况：idle_timeout 需要动态显示超时值和重试次数
    if error_step_type == 'idle_timeout' and display_name and chat_timeout and max_retries:
        error_type = 'timeout'
        total_timeout = chat_timeout * max_retries
        error_message = f"请求超时：AI模型({display_name}) {chat_timeout}秒内未返回任何内容，已重试{max_retries}次，合计{total_timeout}秒，请更换问题或稍后重试"
    
    # 4. 处理空响应情况
    if not original_error:
        error_type = 'empty_response'
        error_message = "模型未能生成有效回复，请尝试更换问题或稍后重试"
    
    # 5. 创建 error_response（yield给前端）
    error_response = create_error_response(
        error_type=error_type,
        message=error_message,
        model=model,
        provider=provider,
        retryable=retryable,
        retry_after=retry_after,
        step=step_num
    )
    
    # 6. 创建 error_step（保存到数据库）
    error_step = create_error_step(
        code='AI_CALL_ERROR',
        message=error_message,
        error_type=error_type,
        step_num=step_num,
        model=model,
        provider=provider,
        retryable=retryable,
        retry_after=retry_after
    )
    
    return error_response, error_step


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
        message=error_message,
        code=error_code,
        model=model,
        provider=provider,
        retryable=retryable,
        retry_after=retry_after,
        step=step_num
    )
    
    # 3. 创建 error_step（保存到数据库）
    error_step = create_error_step(
        code=error_code,
        message=error_message,
        error_type=error_type,
        step_num=step_num,
        model=model,
        provider=provider,
        retryable=retryable,
        retry_after=retry_after
    )
    
    return error_response, error_step


def create_tool_error_result(
    tool_name: str,
    error_message: str,
    step_num: int,
    tool_params: Optional[Dict[str, Any]] = None,
    retry_count: int = 0,
    max_retries: int = 3,
    raw_data: Any = None,
    timestamp: Optional[int] = None
) -> Dict[str, Any]:
    """
    统一的工具级错误处理函数
    
    【新增 2026-04-10 小沈】
    
    用途：文件操作失败、网络请求失败、命令执行错误
    
    特点：
    - 发生错误 ≠ 最后一步
    - LLM会收到这个作为 observation
    - LLM决定：继续循环 or 进入final
    - 复用 format_action_tool_sse() 的字段格式
    
    返回：可直接yield的action_tool格式字典
    
    Args:
        tool_name: 工具名称
        error_message: 错误消息
        step_num: 步骤序号
        tool_params: 工具参数（可选）
        retry_count: 当前重试次数（后续扩展用）
        max_retries: 最大重试次数（后续扩展用）
        raw_data: 详细错误信息（可选）
        timestamp: 时间戳（可选，不传则自动生成）
    
    Returns:
        可直接yield的action_tool格式字典，包含：
        - type: 'action_tool'
        - step: 步骤序号
        - timestamp: 时间戳
        - tool_name: 工具名称
        - tool_params: 工具参数
        - execution_status: 'error'
        - summary: 错误摘要
        - raw_data: 详细错误信息
        - action_retry_count: 重试次数
    """
    # 构建错误摘要
    can_retry = retry_count < max_retries
    if can_retry:
        summary = f"[错误] {tool_name} 执行失败: {error_message}，正在重试 ({retry_count + 1}/{max_retries})..."
    else:
        summary = f"[错误] {tool_name} 执行失败: {error_message}，已重试{max_retries}次"
    
    # 使用传入的时间戳或自动生成
    ts = timestamp if timestamp is not None else create_timestamp()
    
    # 返回dict，可直接yield
    return {
        'type': 'action_tool',
        'step': step_num,
        'timestamp': ts,
        'tool_name': tool_name,
        'tool_params': tool_params or {},
        'execution_status': 'error',  # 标记为错误
        'summary': summary,
        'raw_data': raw_data or error_message,
        'action_retry_count': retry_count
    }
