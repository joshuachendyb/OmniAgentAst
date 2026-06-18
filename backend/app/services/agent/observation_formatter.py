# -*- coding: utf-8 -*-
"""
observation_formatter — 工具结果格式化为LLM observation文本

原名: tool_result_formatter.py (与 utils/tool_result_formatter.py 同名造成混淆)
重命名: 2026-06-08 小欧 — SRP: 本模块只负责格式化LLM observation，不负责截断/格式化通用逻辑

提供两条输出路径:
- format_llm_observation(): 给LLM看的observation文本

设计原则:
- 工具自控:通过llm_data字段控制给LLM的数据量,格式化层不做业务截断
- 安全兜底:仅在data极端大时防json.dumps OOM
"""

import json
from typing import Any, Dict, Optional

from app.constants import SUCCESS_CODE, LLM_SAFE_LIMIT


def _prevent_json_oom(data: Any, limit: int) -> Any:
    """防JSON序列化OOM:仅防 json.dumps OOM,非业务截断 — 小沈 2026-05-27"""
    if isinstance(data, dict):
        if len(data) > limit:
            keys = list(data.keys())[:limit]
            return {k: data[k] for k in keys}
    elif isinstance(data, list):
        if len(data) > limit:
            return data[:limit]
    return data


def _get_failure_hint(tool_name: str, tool_params: Optional[dict] = None, result: Optional[dict] = None) -> str:
    """工具执行失败时获取替代建议 — 小健 2026-05-24

    优先从tool_registry获取工具自定义提示,
    无自定义提示时按错误类型返回差异化建议。

    重写 EXC-20: 异常分类 (ImportError/AttributeError/JSON)
    更新 小沈 2026-06-11: 按result.code分类返回差异化提示
    """
    # 1. 优先从tool_registry获取自定义提示
    try:
        from app.tools.registry import tool_registry
        meta = tool_registry.get_tool(tool_name)
        if meta and hasattr(meta, 'get_failure_hint'):
            hint = meta.get_failure_hint(tool_params)
            if hint:
                return hint
    except (ImportError, AttributeError, json.JSONDecodeError, TypeError) as e:
        from app.utils.logger import logger as _logger
        _logger.debug(f"[_get_failure_hint] 工具提示获取失败: {e}")

    # 2. 按错误码返回差异化提示
    if result:
        code = result.get("code", "")
        if isinstance(code, str):
            hints = {
                "ERR_FILE_NOT_FOUND": "文件或目录不存在,请检查路径是否正确。",
                "ERR_PERMISSION_DENIED": "权限不足,请检查文件访问权限。",
                "ERR_TIMEOUT": "操作超时,请稍后重试或检查网络连接。",
                "ERR_NETWORK": "网络连接失败,请检查网络状态后重试。",
                "ERR_INVALID_PARAMS": "参数格式不正确,请检查参数类型和格式。",
            }
            for prefix, hint in hints.items():
                if code.startswith(prefix):
                    return hint

    # 3. 兜底通用提示
    return "请尝试其他可用工具,不要重复调用同一失败操作。"


def extract_status(result: dict) -> str:
    """从工具统一返回格式提取Agent消费的status字段 — 小健 2026-05-21

    映射规则:
      SUCCESS        → "success"
      WARNING_*      → "warning"
      ERR_* / 其他   → "error"
      code缺失/None   → "error"
    """
    code = result.get("code")
    if code == SUCCESS_CODE:
        return "warning" if result.get("warning") else "success"
    elif isinstance(code, str) and code.startswith("WARNING_"):
        return "warning"
    else:
        return "error"


def build_execution_result_dict(execution_result: Dict[str, Any]) -> Dict[str, Any]:
    """从工具返回结果构建统一格式dict — 小健 2026-05-24

    【修复P0-4 2026-06-08 小沈】删除StepFactory引用，直接调用Step构造函数
    """
    _status = extract_status(execution_result)
    return {
        "status": _status,
        "summary": execution_result.get("message", ""),
        "data": execution_result.get("data"),
        "retry_count": execution_result.get("retry_count", 0),
        "code": execution_result.get("code", SUCCESS_CODE),
        "warning": execution_result.get("warning"),
        "attachment": execution_result.get("attachment"),
        "next_actions": execution_result.get("next_actions"),
        "return_direct": execution_result.get("return_direct", False),
        "error_message": execution_result.get("error_message", ""),
    }


def _format_next_actions(result: dict, text: str) -> str:
    """将next_actions格式化为文本追加到observation — 小健 2026-05-22"""
    next_actions = result.get('next_actions')
    if not next_actions or not isinstance(next_actions, list):
        return text
    na_lines = ["\n推荐下一步操作:"]
    for i, na in enumerate(next_actions[:5], 1):
        if isinstance(na, dict):
            tool = na.get('tool', '')
            desc = na.get('description', '')
            when = na.get('when', '')
            params = na.get('params')
            line = f"  {i}. {tool}"
            if desc:
                line += f" - {desc}"
            if when:
                line += f"({when})"
            if params:
                line += f" 参数建议: {params}"
        elif isinstance(na, tuple) and len(na) >= 2:
            line = f"  {i}. {na[0]} - {na[1]}"
        else:
            line = f"  {i}. {na}"
        na_lines.append(line)
    return text + "\n".join(na_lines)


def _extract_display_data(result: dict) -> Any:
    """提取display_data — 小沈 2026-06-08 | P1修复: or→is not None(空字典误回退) — 小欧 2026-06-11"""
    llm_data = result.get("llm_data")
    if llm_data is not None:
        return llm_data
    data = result.get("data")
    if data is None:
        from app.utils.logger import logger as _logger
        _logger.warning("[OBS-001] format_llm_observation: llm_data和data均为空")
    return data


def _build_base_text(result: dict, status: str) -> str:
    """构建基础文本 — 小沈 2026-06-08"""
    return f"Observation: {status} - {result.get('message', '')}"


def _append_warning(text: str, result: dict) -> str:
    """追加warning — 小沈 2026-06-08"""
    if result.get("warning"):
        return text + f"\n⚠ 警告: {result['warning']}"
    return text


def _append_data(text: str, display_data: Any) -> str:
    """追加data — 小沈 2026-06-08"""
    if not display_data:
        return text
    if isinstance(display_data, (dict, list)):
        display_data = _prevent_json_oom(display_data, LLM_SAFE_LIMIT)
    return text + f"\n数据: {json.dumps(display_data, ensure_ascii=False)}"


def _format_result_observation(result: dict, status: str, use_llm_data: bool = True) -> str:
    """统一格式化成功/警告结果 — 小健 2026-06-18 DRY合并"""
    text = _build_base_text(result, status)
    if status == "success":
        display_data = _extract_display_data(result) if use_llm_data else result.get("data")
        text = _append_warning(text, result)
        text = _append_data(text, display_data)
    else:
        if result.get("data"):
            data = result["data"]
            if isinstance(data, (dict, list)):
                data = _prevent_json_oom(data, LLM_SAFE_LIMIT)
            text += f"\n部分数据: {json.dumps(data, ensure_ascii=False)}"
    return _format_next_actions(result, text)


def _format_success_observation(result: dict) -> str:
    """格式化成功结果 — 小沈 2026-06-08 重构"""
    return _format_result_observation(result, "success", use_llm_data=True)


def _format_warning_observation(result: dict) -> str:
    """格式化警告结果 — 小沈 2026-06-08 重构"""
    return _format_result_observation(result, "warning", use_llm_data=False)


def _append_hint(text: str, tool_name: str, tool_params: Optional[dict], result: Optional[dict] = None) -> str:
    """追加hint — 小沈 2026-06-08"""
    if not tool_name:
        return text
    hint = _get_failure_hint(tool_name, tool_params, result)
    if hint:
        return text + f"\n{hint}"
    return text


def _format_error_observation(result: dict, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    """格式化错误结果 — 小沈 2026-06-08 重构"""
    text = f"Observation: error [{result.get('code', '')}] - {result.get('message', '')}"
    text = _append_hint(text, tool_name, tool_params, result)
    return _format_next_actions(result, text)


def format_llm_observation(result: dict, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    """格式化工具结果为LLM observation文本 — 小沈 2026-05-21
    更新 2026-05-22 小健:合入next_actions拼接逻辑(从base_react.py搬入)
    """
    code = result.get("code")

    if code == SUCCESS_CODE:
        return _format_success_observation(result)
    elif isinstance(code, str) and code.startswith("WARNING_"):
        return _format_warning_observation(result)
    else:
        return _format_error_observation(result, tool_name, tool_params)

