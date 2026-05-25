# -*- coding: utf-8 -*-
"""
统一错误处理模块

从 chat_stream.py 拆分出来
职责：统一的错误处理
Author: 小沈 - 2026-03-22
"""

import json
from typing import Any, Dict, List, Optional

from app.chat_stream.chat_helpers import create_timestamp
from app.constants import ERROR_TYPE_MAP, HTTPX_EXCEPTION_TO_ERROR_KEY


# 替换 P3g-P3n 8 个 if/elif 的数据表
HTTP_STATUS_MAP_ENTRIES: List[Dict[str, Any]] = [
    {"codes": ["503"], "keywords": ["无可用渠道"],
     "code": "API_CHANNEL_UNAVAILABLE", "msg_key": "api_error_503", "retryable": False},
    {"codes": ["429"], "keywords": ["rate limit", "limit_error", "配额"],
     "code": "RATE_LIMIT_EXCEEDED", "msg_key": "api_error_429", "retryable": True, "retry_after": 30},
    {"codes": ["401"], "keywords": ["认证", "unauthorized"],
     "code": "AUTH_FAILED", "msg_key": "api_error_401", "retryable": False},
    {"codes": ["403"], "keywords": ["forbidden"],
     "code": "FORBIDDEN", "msg_key": "api_error_403", "retryable": False},
    {"codes": ["400"], "keywords": [],
     "code": "BAD_REQUEST", "msg_key": "api_error_400", "retryable": False},
    {"codes": ["500"], "keywords": [],
     "code": "SERVER_ERROR", "msg_key": "api_error_500", "retryable": True, "retry_after": 10},
    {"codes": ["502"], "keywords": ["bad gateway"],
     "code": "BAD_GATEWAY", "msg_key": "api_error_502", "retryable": True, "retry_after": 10},
    {"codes": ["504"], "keywords": [],
     "code": "GATEWAY_TIMEOUT", "msg_key": "api_error_504", "retryable": True, "retry_after": 15},
]


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


def create_error_step(
    error_type: str,
    error_message: str,
    step_num: int,
    model: Optional[str] = None,
    provider: Optional[str] = None,
    recoverable: bool = False,
    context: Optional[Dict[str, Any]] = None,
    retry_after: Optional[int] = None
) -> Dict[str, Any]:
    """
    创建保存到数据库的 error_step
    【2026-04-15 小沈修改15.7】：按15.7.1要求使用新字段，删除旧字段

    Args:
        error_type: 错误类型（如 timeout, security, server）
        error_message: 错误信息
        step_num: 步骤序号
        model: 模型名称（可选）
        provider: 提供商（可选）
        recoverable: 是否可恢复
        context: 错误上下文（包含step/model/provider/thought_content）
        retry_after: 重试等待秒数

    Returns:
        error_step 字典
    """
    # 构建context字段
    if context is None:
        context = {
            "step": step_num,
            "model": model,
            "provider": provider,
            "thought_content": ""
        }
    
    # 【15.7修改】只保留新字段，删除旧字段code/message/retryable
    return {
        'type': 'error',
        'step': step_num,
        'error_message': error_message,
        'error_type': error_type,
        'timestamp': create_timestamp(),
        'model': model,
        'provider': provider,
        'reasoning': '',
        'is_reasoning': False,
        'recoverable': recoverable,
        'context': context,
        'retry_after': retry_after
    }


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
    创建统一的错误响应格式
    【2026-04-15 小沈修改15.7】：按15.7.1要求删除旧字段code和message
    
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
    # 【15.7修改】只输出新字段，删除旧字段code和message
    response: Dict[str, Any] = {
        'type': 'error',
        'error_type': error_type,
        'error_message': error_message,
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
    if recoverable is not None:
        response['recoverable'] = recoverable
    if retry_after is not None:
        response['retry_after'] = retry_after
    response['timestamp'] = create_timestamp()
    return f"data: {json.dumps(response, ensure_ascii=False)}\n\n"


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

    # P3: 字符串模式匹配 — 异常类型优先，消息降级
    if error_type == "TimeoutError" or "timeout" in error_msg:
        return _build_error_response("TIMEOUT", "timeout_error", retryable=True, retry_after=5)
    if error_type == "ConnectionError" or "connection" in error_msg:
        return _build_error_response("CONNECTION_ERROR", "connect_error", retryable=True, retry_after=10)
    if error_type == "HTTPError" or "http" in error_msg:
        return _build_error_response("HTTP_ERROR", "http_error", retryable=True, retry_after=10)
    if error_type == "ValueError":
        return _build_error_response("VALIDATION_ERROR", "validation_error", retryable=False)
    if "not found" in error_msg or "不存在" in error_msg:
        return _build_error_response("NOT_FOUND", "not_found", retryable=False)
    if "permission" in error_msg or "权限" in error_msg:
        return _build_error_response("PERMISSION_DENIED", "permission_denied", retryable=False)

    # P3g-P3n: HTTP 状态码/关键词 → 查 HTTP_STATUS_MAP_ENTRIES 数据表
    for entry in HTTP_STATUS_MAP_ENTRIES:
        if any(code in error_msg for code in entry["codes"]) or \
           any(kw in error_msg for kw in entry.get("keywords", [])):
            return _build_error_response(entry["code"], entry["msg_key"],
                                          entry["retryable"], entry.get("retry_after"))

    # O1: 兜底
    return _build_error_response("UNKNOWN_ERROR", "unknown_fallback", retryable=True, retry_after=5)


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
    
    【重构 小健 2026-05-24】统一引用 constants.HTTP_STATUS_TO_ERROR_TYPE 映射表
    """
    if not error_message:
        return None
    
    from app.constants import HTTP_STATUS_TO_ERROR_TYPE, API_ERROR_429, API_ERROR_401, API_ERROR_403
    
    import re
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


def is_network_or_api_error(error_message: str) -> tuple[bool, Optional[str]]:
    """判断错误是否为网络/API错误，返回(is_network, error_type) — 小健 2026-05-24
    
    用于parse_error分支决策：网络错误不注入history（重试即可），
    非网络错误注入history引导LLM修复格式。
    解析异常时静默降级为(False, None)，与原loop内联try/except行为一致。
    """
    try:
        error_type = resolve_http_error_type(error_message)
    except Exception:
        return (False, None)
    if error_type is None:
        return (False, None)
    is_network = (
        error_type.startswith("api_error_") and error_type != "api_error_400"
        or error_type in ("network", "connect", "protocol", "timeout")
    )
    return (is_network, error_type)


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
        error_message=error_message,
        model=model,
        provider=provider,
        recoverable=retryable,
        retry_after=retry_after,
        step=step_num
    )
    
    # 6. 创建 error_step（保存到数据库）
    error_step = create_error_step(
        error_type=error_type,
        error_message=error_message,
        step_num=step_num,
        model=model,
        provider=provider,
        recoverable=retryable,
        context={"step": step_num, "model": model, "provider": provider, "thought_content": ""},
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
        error_message=error_message,
        model=model,
        provider=provider,
        recoverable=retryable,
        retry_after=retry_after,
        step=step_num
    )
    
    # 3. 创建 error_step（保存到数据库）
    error_step = create_error_step(
        error_type=error_type,
        error_message=error_message,
        step_num=step_num,
        model=model,
        provider=provider,
        recoverable=retryable,
        context={"step": step_num, "model": model, "provider": provider, "thought_content": ""},
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
    timestamp: Optional[int] = None,
    status: str = "error",  # 新增参数，支持 warning/timeout/permission_denied 等状态
    execution_time_ms: int = 0  # 执行耗时（毫秒）
) -> Dict[str, Any]:
    """
    统一的工具级错误处理函数
    
    【新增 2026-04-10 小沈】
    【2026-04-16 小沈修改】：新增 status 参数，支持 warning/timeout/permission_denied 等状态
    
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
        status: 执行状态（默认 "error"，支持 warning/timeout/permission_denied 等）
        execution_time_ms: 执行耗时（毫秒，默认0）
    
    Returns:
        可直接yield的action_tool格式字典，包含：
        - type: 'action_tool'
        - step: 步骤序号
        - timestamp: 时间戳
        - tool_name: 工具名称
        - tool_params: 工具参数
        - execution_status: 执行状态（使用传入的status参数）
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
    # 【2026-04-15 小沈修改15.7】：按15.7.1要求修改字段名
    # 【2026-04-16 小沈修改】：使用传入的 status 参数而非固定 "error"
    return {
        'type': 'action_tool',
        'step': step_num,
        'timestamp': ts,
        'tool_name': tool_name,
        'tool_params': tool_params or {},
        'execution_status': status,  # 使用传入的 status 而非固定 "error"
        'summary': summary,
        'execution_result': raw_data or error_message,  # raw_data替换为execution_result
        'error_message': error_message,  # 新增字段
        'execution_time_ms': execution_time_ms,  # 新增字段（传入实际耗时）
        'action_retry_count': retry_count
    }
