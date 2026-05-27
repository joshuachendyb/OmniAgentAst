# -*- coding: utf-8 -*-
"""
工具结果统一默认值常量

提供统一的结果字典默认值，消除17处散布的硬编码默认值
Author: 小沈 - 2026-05-27
"""

from typing import Any, Dict

# 工具执行结果统一默认值常量
DEFAULT_TOOL_RESULT: Dict[str, Any] = {
    "code": "SUCCESS",
    "data": None,
    "message": "执行成功",
    "retry_count": 0,
    "metadata": {},
    "error_message": "",
    "error_type": "",
    "return_direct": False
}

# 错误结果默认值
DEFAULT_ERROR_RESULT: Dict[str, Any] = {
    "code": "ERROR",
    "data": None,
    "message": "执行失败",
    "retry_count": 0,
    "metadata": {"error_type": "unknown"},
    "error_message": "未知错误",
    "error_type": "unknown",
    "return_direct": False
}

# 超时错误结果
DEFAULT_TIMEOUT_RESULT: Dict[str, Any] = {
    "code": "TIMEOUT",
    "data": None,
    "message": "执行超时",
    "retry_count": 0,
    "metadata": {"error_type": "timeout"},
    "error_message": "执行超时",
    "error_type": "timeout",
    "return_direct": False
}

# 参数错误结果
DEFAULT_PARAM_ERROR_RESULT: Dict[str, Any] = {
    "code": "ERR_INVALID_PARAMS",
    "data": None,
    "message": "参数错误",
    "retry_count": 0,
    "metadata": {"error_type": "invalid_params"},
    "error_message": "无效参数",
    "error_type": "invalid_params",
    "return_direct": False
}

# 未找到工具错误结果
DEFAULT_TOOL_NOT_FOUND_RESULT: Dict[str, Any] = {
    "code": "ERR_TOOL_NOT_FOUND",
    "data": None,
    "message": "工具未找到",
    "retry_count": 0,
    "metadata": {"error_type": "tool_not_found"},
    "error_message": "工具未找到",
    "error_type": "tool_not_found",
    "return_direct": False
}

# 权限错误结果
DEFAULT_PERMISSION_ERROR_RESULT: Dict[str, Any] = {
    "code": "ERR_PERMISSION_DENIED",
    "data": None,
    "message": "权限不足",
    "retry_count": 0,
    "metadata": {"error_type": "permission_denied"},
    "error_message": "权限不足",
    "error_type": "permission_denied",
    "return_direct": False
}


def create_tool_result(
    code: str = "SUCCESS",
    data: Any = None,
    message: str = "执行成功",
    retry_count: int = 0,
    metadata: Dict[str, Any] = None,
    error_message: str = "",
    error_type: str = "",
    return_direct: bool = False
) -> Dict[str, Any]:
    """
    创建标准工具结果字典
    
    Args:
        code: 结果码（SUCCESS/ERROR/...）
        data: 返回数据
        message: 结果消息
        retry_count: 重试次数
        metadata: 元数据
        error_message: 错误消息
        error_type: 错误类型
        return_direct: 是否直接返回
    
    Returns:
        标准工具结果字典
    """
    result = DEFAULT_TOOL_RESULT.copy()
    result.update({
        "code": code,
        "data": data,
        "message": message,
        "retry_count": retry_count,
        "metadata": metadata or {},
        "error_message": error_message,
        "error_type": error_type,
        "return_direct": return_direct
    })
    return result


def create_error_tool_result(
    code: str = "ERROR",
    data: Any = None,
    message: str = "执行失败",
    retry_count: int = 0,
    error_message: str = "",
    error_type: str = "unknown",
    return_direct: bool = False
) -> Dict[str, Any]:
    """
    创建错误工具结果字典
    
    Args:
        code: 错误码
        data: 返回数据
        message: 结果消息
        retry_count: 重试次数
        error_message: 错误消息
        error_type: 错误类型
        return_direct: 是否直接返回
    
    Returns:
        错误工具结果字典
    """
    result = DEFAULT_ERROR_RESULT.copy()
    result.update({
        "code": code,
        "data": data,
        "message": message,
        "retry_count": retry_count,
        "metadata": {"error_type": error_type},
        "error_message": error_message,
        "error_type": error_type,
        "return_direct": return_direct
    })
    return result


__all__ = [
    "DEFAULT_TOOL_RESULT",
    "DEFAULT_ERROR_RESULT",
    "DEFAULT_TIMEOUT_RESULT",
    "DEFAULT_PARAM_ERROR_RESULT",
    "DEFAULT_TOOL_NOT_FOUND_RESULT",
    "DEFAULT_PERMISSION_ERROR_RESULT",
    "create_tool_result",
    "create_error_tool_result"
]