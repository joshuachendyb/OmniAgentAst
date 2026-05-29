"""
统一工具返回结构定义 — 小健 2026-05-21

【分层规范 - 小健 2026-05-27】
本文件属于【工具层】，职责：构建返回dict基础结构（code/data/message + 可选字段）

三层职责边界（严格遵守）：
  _response.py (工具层)
    → 提供 build_success / build_error / build_warning
    → 工具函数、helper函数 直接使用这三个函数
    → 禁止使用 agent/tool_result_utils.py 的 create_xxx 函数

  tool_result_utils.py (Agent层)
    → 提供 create_tool_result / create_error_tool_result / create_warning_tool_result
    → Agent编排层使用（tool_executor、tool_retry_engine等）
    → 委托工具层构建，追加Agent层特有字段（error_type、metadata等）

  tool_result_formatter.py (格式化层)
    → LLM observation / 前端SSE / extract_status 格式化
    → 禁止构建结果，只消费和格式化

违反后果：层级混乱，职责不清，代码审查打回

设计原则:
  1. 必填字段(code/data/message)始终写入，可选字段仅非默认值时写入
  2. build_success/build_error/build_warning 三个函数对称完整

字段规范:
  必填(3个): code, data, message
  可选(5个): warning, llm_data, next_actions, retry_count, return_direct

使用示例:
  # 最简成功
  return build_success({"path": fp}, f"写入成功: {fp}")

  # 带llm_data
  return build_success(data, msg, llm_data={"摘要": "..."})

  # 带next_actions
  return build_success(data, msg, next_actions=build_next_actions([...]))

  # 错误
  return build_error(ERR_FILE_NOT_FOUND, f"文件不存在: {fp}")

  # 警告(成功但有风险)
  return build_warning("WARNING_xxx", "警告消息", data=...)
"""
from app.constants import ERR_FILE_NOT_FOUND, SUCCESS_CODE
from typing import Any, Dict, Optional, List

# 必填字段 — 始终写入
_REQUIRED_FIELDS = ("code", "data", "message")

# 可选字段 — 仅非默认值时写入
# 格式: (字段名, 默认值)
_OPTIONAL_FIELDS = {
    "warning": None,
    "llm_data": None,
    "next_actions": None,
    "retry_count": 0,
    "return_direct": False,
    "attachment": None,
}


def build_success(
    code: str = SUCCESS_CODE,
    data: Any = None,
    message: str = "执行成功",
    warning: Optional[str] = None,
    llm_data: Optional[Dict[str, Any]] = None,
    next_actions: Optional[List[Dict[str, str]]] = None,
    retry_count: int = 0,
    return_direct: bool = False,
    attachment: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构建成功响应

    Args:
        data: 结构化返回数据(给前端)
        message: 人类可读的结果描述
        warning: 可选警告信息(成功但有风险时)
        llm_data: 可选给LLM的精简数据(控制上下文占用)
        next_actions: 可选推荐后续操作列表
        retry_count: 可选重试次数(默认0不写入)
        return_direct: 可选是否直接返回前端(默认False不写入)
        attachment: 可选二进制附件(base64图片/文件等，前端渲染)

    Returns:
        统一格式的dict
    """
    result: Dict[str, Any] = {
        "code": SUCCESS_CODE,
        "data": data,
        "message": message,
    }

    _add_optionals(result, warning=warning, llm_data=llm_data,
                   next_actions=next_actions, retry_count=retry_count,
                   return_direct=return_direct, attachment=attachment)

    result.update(extra)

    return result


def build_error(
    code: str,
    message: str,
    data: Any = None,
    warning: Optional[str] = None,
    llm_data: Optional[Dict[str, Any]] = None,
    next_actions: Optional[List[Dict[str, str]]] = None,
    attachment: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构建错误响应

    Args:
        code: 错误码，必须符合三段式: ERR_MODULE_OPERATION_DETAIL
        message: 错误描述
        data: 可选附加错误数据(如校验详情)
        warning: 可选附加警告
        llm_data: 可选给LLM的错误摘要
        next_actions: 可选推荐恢复操作
        attachment: 可选二进制附件

    Returns:
        统一格式的dict
    """
    result: Dict[str, Any] = {
        "code": code,
        "data": data,
        "message": message,
    }

    _add_optionals(result, warning=warning, llm_data=llm_data,
                   next_actions=next_actions, attachment=attachment)

    result.update(extra)

    return result


def build_warning(
    code: str,
    message: str,
    data: Any = None,
    llm_data: Optional[Dict[str, Any]] = None,
    next_actions: Optional[List[Dict[str, str]]] = None,
    attachment: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构建警告响应(部分成功/有风险)

    警告code以WARNING_开头，Agent视为成功但需注意

    Args:
        code: 警告码，以WARNING_开头
        message: 警告描述
        data: 部分成功的数据
        llm_data: 可选给LLM的数据
        next_actions: 可选推荐操作
        attachment: 可选二进制附件

    Returns:
        统一格式的dict
    """
    result: Dict[str, Any] = {
        "code": code,
        "data": data,
        "message": message,
    }

    _add_optionals(result, llm_data=llm_data,
                   next_actions=next_actions, attachment=attachment)

    result.update(extra)

    return result


def _add_optionals(result: Dict[str, Any], **kwargs: Any) -> None:
    """仅写入非默认值的可选字段 — 内部函数"""
    for field_name, default_value in _OPTIONAL_FIELDS.items():
        if field_name in kwargs:
            value = kwargs[field_name]
            if value != default_value:
                result[field_name] = value



