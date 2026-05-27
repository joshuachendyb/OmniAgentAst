# -*- coding: utf-8 -*-
"""
工具结果统一默认值常量 + Agent层结果工厂

DRY原则：create_tool_result/create_error_tool_result 委托到 _response.py 的
build_success/build_error，不再重复构建逻辑。Agent层特有字段
(error_message, error_type, metadata) 在此追加。

三层职责边界：
  _response.py          → 工具层：构建返回dict基础结构（code/data/message + 可选字段）
  tool_result_utils.py  → Agent层：在工具层基础上追加Agent消费字段
  tool_result_formatter.py → 格式化层：LLM observation / 前端SSE / extract_status

Author: 小沈 - 2026-05-27
"""

from typing import Any, Dict, Optional

from app.services.tools._response import build_success, build_error


def create_tool_result(
    code: str = "SUCCESS",
    data: Any = None,
    message: str = "执行成功",
    retry_count: int = 0,
    metadata: Optional[Dict[str, Any]] = None,
    error_message: str = "",
    error_type: str = "",
    return_direct: bool = False,
) -> Dict[str, Any]:
    """
    创建标准工具结果字典（Agent层工厂）

    委托到 _response.build_success 构建，追加Agent层特有字段。

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
    result = build_success(
        data=data,
        message=message,
        retry_count=retry_count,
        return_direct=return_direct,
    )
    result["code"] = code
    if metadata:
        result["metadata"] = metadata
    if error_message:
        result["error_message"] = error_message
    if error_type:
        result["error_type"] = error_type
    return result


def create_error_tool_result(
    code: str = "ERROR",
    data: Any = None,
    message: str = "执行失败",
    retry_count: int = 0,
    error_message: str = "",
    error_type: str = "unknown",
    return_direct: bool = False,
) -> Dict[str, Any]:
    """
    创建错误工具结果字典（Agent层工厂）

    委托到 _response.build_error 构建，追加Agent层特有字段。

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
    result = build_error(
        code=code,
        message=message,
        data=data,
        retry_count=retry_count,
        return_direct=return_direct,
    )
    result["metadata"] = {"error_type": error_type}
    if error_message:
        result["error_message"] = error_message
    result["error_type"] = error_type
    return result


DEFAULT_TOOL_RESULT: Dict[str, Any] = create_tool_result()
DEFAULT_ERROR_RESULT: Dict[str, Any] = create_error_tool_result()
DEFAULT_TIMEOUT_RESULT: Dict[str, Any] = create_error_tool_result(
    code="TIMEOUT", message="执行超时", error_message="执行超时", error_type="timeout"
)
DEFAULT_PARAM_ERROR_RESULT: Dict[str, Any] = create_error_tool_result(
    code="ERR_INVALID_PARAMS", message="参数错误", error_message="无效参数", error_type="invalid_params"
)
DEFAULT_TOOL_NOT_FOUND_RESULT: Dict[str, Any] = create_error_tool_result(
    code="ERR_TOOL_NOT_FOUND", message="工具未找到", error_message="工具未找到", error_type="tool_not_found"
)
DEFAULT_PERMISSION_ERROR_RESULT: Dict[str, Any] = create_error_tool_result(
    code="ERR_PERMISSION_DENIED", message="权限不足", error_message="权限不足", error_type="permission_denied"
)


__all__ = [
    "DEFAULT_TOOL_RESULT",
    "DEFAULT_ERROR_RESULT",
    "DEFAULT_TIMEOUT_RESULT",
    "DEFAULT_PARAM_ERROR_RESULT",
    "DEFAULT_TOOL_NOT_FOUND_RESULT",
    "DEFAULT_PERMISSION_ERROR_RESULT",
    "create_tool_result",
    "create_error_tool_result",
]
