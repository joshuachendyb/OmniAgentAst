"""
统一工具返回结构定义 — 小健 2026-05-21

【两层规范 - 小健 2026-06-17】三层→两层简化,删除tool_result_factory中间层
本文件属于【工具层】,职责:构建返回dict基础结构(code/data/message + 可选字段)
以及判断返回状态的查询函数(is_success/is_error)。

【Phase 1 2026-06-20 小欧】新增 builder 注册机制 + build_result 三字段格式:
  - register_builder(tool_name, fn): 注册 builder
  - _default_builder(tool_name, data, other_data): 默认 builder（兜底）
  - build_result(tool_name, data, other_data, **extra): 统一出口
  - is_success/is_error 新增新格式判断（旧函数保留过渡期）

两层职责边界:
  tool_response.py (构建层) ← 本文件
    → 提供 build_success / build_error / build_warning / is_success / is_error (旧)
    → 提供 register_builder / _default_builder / build_result / is_success / is_error (新)
    → 工具函数、helper函数、Agent编排层 统一使用这些函数
    → 通过 **extra 支持任意扩展字段(error_type/metadata等)

  tool_result_formatter.py (格式化层)
    → LLM observation / 前端SSE / extract_status 格式化
    → 禁止构建结果,只消费和格式化
"""
from app.constants import SUCCESS_CODE
from typing import Any, Callable, Dict, Optional, List

# ── 旧格式 ──────────────────────────────────────────────

# 必填字段 — 始终写入
_REQUIRED_FIELDS = ("code", "data", "message")

# 可选字段 — 仅非默认值时写入
# 格式: (字段名, 默认值)
_OPTIONAL_FIELDS = {
    "warning": None,
    "llm_data": None,
    "retry_count": 0,
    "return_direct": False,
    "attachment": None,
}


def build_success(
    data: Any = None,
    message: str = "执行成功",
    warning: Optional[str] = None,
    llm_data: Optional[Dict[str, Any]] = None,
    retry_count: int = 0,
    return_direct: bool = False,
    attachment: Optional[Dict[str, Any]] = None,
    code: Optional[str] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构建成功响应

    Args:
        data: 结构化返回数据(给前端)
        message: 人类可读的结果描述
        warning: 可选警告信息(成功但有风险时)
        llm_data: 可选给LLM的精简数据(控制上下文占用)
        retry_count: 可选重试次数(默认0不写入)
        return_direct: 可选是否直接返回前端(默认False不写入)
        attachment: 可选二进制附件(base64图片/文件等,前端渲染)

    Returns:
        统一格式的dict
    """
    result: Dict[str, Any] = {
        "code": SUCCESS_CODE,
        "data": data,
        "message": message,
    }

    _add_optionals(result, warning=warning, llm_data=llm_data,
                   retry_count=retry_count,
                   return_direct=return_direct, attachment=attachment)

    result.update(extra)

    return result


def build_error(
    code: str,
    message: str,
    data: Any = None,
    warning: Optional[str] = None,
    llm_data: Optional[Dict[str, Any]] = None,
    attachment: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构建错误响应

    Args:
        code: 错误码,必须符合三段式: ERR_MODULE_OPERATION_DETAIL
        message: 错误描述
        data: 可选附加错误数据(如校验详情)
        warning: 可选附加警告
        llm_data: 可选给LLM的错误摘要
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
                   attachment=attachment)

    result.update(extra)

    return result


def build_warning(
    code: str,
    message: str,
    data: Any = None,
    llm_data: Optional[Dict[str, Any]] = None,
    attachment: Optional[Dict[str, Any]] = None,
    **extra: Any,
) -> Dict[str, Any]:
    """构建警告响应(部分成功/有风险)

    警告code以WARNING_开头,Agent视为成功但需注意

    Args:
        code: 警告码,以WARNING_开头
        message: 警告描述
        data: 部分成功的数据
        llm_data: 可选给LLM的数据
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
                   attachment=attachment)

    result.update(extra)

    return result


def _add_optionals(result: Dict[str, Any], **kwargs: Any) -> None:
    """仅写入非默认值的可选字段 — 内部函数"""
    for field_name, default_value in _OPTIONAL_FIELDS.items():
        if field_name in kwargs:
            value = kwargs[field_name]
            if value != default_value:
                result[field_name] = value


def is_success(result: Dict[str, Any]) -> bool:
    """判断返回是否成功（同时支持旧格式和新格式）"""
    # 新格式：检查 llm_data.status.exec_code
    llm_data = result.get("llm_data")
    if isinstance(llm_data, dict):
        exec_code = llm_data.get("status", {}).get("exec_code", "")
        if exec_code:
            return exec_code in ("success", "warning")
    # 旧格式兜底
    code = result.get("code", "")
    return code == SUCCESS_CODE or (isinstance(code, str) and code.startswith("WARNING_"))


def is_error(result: Dict[str, Any]) -> bool:
    """判断返回是否失败（同时支持旧格式和新格式）"""
    # 新格式：检查 llm_data.status.exec_code
    llm_data = result.get("llm_data")
    if isinstance(llm_data, dict):
        exec_code = llm_data.get("status", {}).get("exec_code", "")
        if exec_code:
            return exec_code == "error"
    # 旧格式兜底
    code = result.get("code", "")
    return isinstance(code, str) and code.startswith("ERR_")


# ── 新格式：builder 注册机制 + build_result ─────────────
#  v4.1: exec_code/duration_ms/tool_params 作为直接参数；**extra 过滤保留字段 — 小欧 2026-06-20

_BUILDERS: Dict[str, Callable] = {}

# build_result 顶层保留字段，extra 遇到这些字段会被过滤
_RESERVED_TOP_KEYS: set = {"data", "llm_data", "other_data"}


def register_builder(tool_name: str, fn: Callable) -> None:
    """注册工具的 llm_data builder 函数 — 小欧 2026-06-20

    Args:
        tool_name: 工具名称
        fn: builder 函数,签名 (tool_name, data, exec_code, duration_ms, tool_params) -> llm_data dict
    """
    _BUILDERS[tool_name] = fn


def _default_builder(tool_name: str, data: Any = None,
                     exec_code: str = "success",
                     duration_ms: int = 0,
                     tool_params: Optional[Dict] = None) -> Dict[str, Any]:
    """默认 builder — 兜底逻辑 — 小欧 2026-06-20

    Args:
        tool_name: 工具名称
        data: 业务数据
        exec_code: 执行状态码 ("success"/"error"/"warning")
        duration_ms: 执行耗时（毫秒）
        tool_params: LLM 调用参数

    Returns:
        最小 llm_data dict
    """
    summary = str(data)[:200] if data is not None else "执行完成"
    return {
        "summary": summary,
        "action": {"tool": tool_name, "tool_zh": tool_name, "params": tool_params or {}},
        "target": "",
        "status": {
            "exec_code": exec_code,
            "message": "执行成功" if exec_code in ("success", "warning") else "执行失败",
            "code": SUCCESS_CODE if exec_code in ("success", "warning") else "ERR_UNKNOWN",
            "detail": "",
            "hint": "",
        },
        "duration_ms": duration_ms,
        "metrics": {},
    }


def build_result(tool_name: str, data: Any = None,
                 exec_code: str = "success",
                 duration_ms: int = 0,
                 tool_params: Optional[Dict] = None,
                 other_data: Optional[Dict] = None,
                 **extra) -> Dict[str, Any]:
    """统一构建工具返回结果（新3字段格式）— 小欧 2026-06-20

    Args:
        tool_name: 工具名称（用于查找 builder）
        data: 纯业务数据
        exec_code: 执行状态码 ("success"/"error"/"warning")
        duration_ms: 执行耗时（毫秒）
        tool_params: LLM 调用参数（直接传入 builder，不走 data）
        other_data: 控制字段输出通道 (warning/retry_count/return_direct/attachment)
        **extra: 额外字段（合并到顶层，过滤保留字段 data/llm_data/other_data）

    Returns:
        {"data": ..., "llm_data": ..., "other_data": ..., **extra}
    """
    builder = _BUILDERS.get(tool_name, _default_builder)
    llm_data = builder(tool_name, data, exec_code, duration_ms, tool_params)
    result: Dict[str, Any] = {
        "data": data,
        "llm_data": llm_data,
        "other_data": other_data or {},
    }
    for k, v in extra.items():
        if k not in _RESERVED_TOP_KEYS:
            result[k] = v
    return result






