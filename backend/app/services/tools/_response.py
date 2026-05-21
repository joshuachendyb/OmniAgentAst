"""
统一工具返回结构定义
所有工具函数应返回ToolResponse格式的字典
小健 2026-05-21
"""
from typing import Any, Dict, Optional

SUCCESS_CODE = "SUCCESS"

def build_success(
    data: Any,
    message: str = "操作成功",
    warning: Optional[str] = None,
    llm_data: Optional[Dict[str, Any]] = None,
    next_actions: Optional[list] = None,
    retry_count: int = 0,
    return_direct: bool = False,
) -> Dict[str, Any]:
    """构建成功响应"""
    result = {
        "code": SUCCESS_CODE,
        "data": data,
        "message": message,
        "retry_count": retry_count,
        "return_direct": return_direct,
    }
    if warning:
        result["warning"] = warning
    if llm_data:
        result["llm_data"] = llm_data
    if next_actions:
        result["next_actions"] = next_actions
    return result


def build_error(
    code: str,
    message: str,
    data: Any = None,
    warning: Optional[str] = None,
    llm_data: Optional[Dict[str, Any]] = None,
    next_actions: Optional[list] = None,
) -> Dict[str, Any]:
    """构建错误响应"""
    result = {
        "code": code,
        "data": data,
        "message": message,
    }
    if warning:
        result["warning"] = warning
    if llm_data:
        result["llm_data"] = llm_data
    if next_actions:
        result["next_actions"] = next_actions
    return result


def is_success(result: Dict[str, Any]) -> bool:
    """判断是否成功"""
    return result.get("code") == SUCCESS_CODE
