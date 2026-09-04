# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-04 小健 - 新建: target提取逻辑从action_handler下沉到工具层(第2阶段拆分) - 小健-2026-09-04
"""
target_utils — 工具调用target字段提取

从 action_handler.py 下沉而来，action_handler 不应包含工具 schema 查询逻辑。
target 字段用于 ActionStep 结构化展示（极少截断保留完整值）。
"""
from typing import Optional, Dict, Any

from app.tools.registry import tool_registry


_TARGET_PARAM_PRIORITY = (
    "command", "sql", "url", "host", "pattern",
    "path", "dir_path", "file_path", "source_path", "query", "content",
)


def _resolve_target_field(tool_name: str) -> Optional[str]:
    """2026-08-18 小健 三堂会审: 从工具schema主参数自动推导target字段名(取代硬编码映射, DRY/OCP)
    ①显式声明tool.target_param优先(扩展点, 无需改动本函数) ②否则按_TARGET_PARAM_PRIORITY匹配真实properties
    ③兜底: 必填参数→首参数; 均未命中返回None(调用方回退为工具名)"""
    _tool = tool_registry.get_tool(tool_name)
    if _tool is None:
        return None
    _props = (_tool.input_schema or {}).get("properties") or {}
    if not _props:
        return None
    _explicit = getattr(_tool, "target_param", None)
    if _explicit and _explicit in _props:
        return _explicit
    for _cand in _TARGET_PARAM_PRIORITY:
        if _cand in _props:
            return _cand
    for _r in (_tool.input_schema or {}).get("required", []) or []:
        if _r in _props:
            return _r
    return next(iter(_props))


def _extract_target(call: Dict[str, Any]) -> str:
    """2026-08-18 小欧 - §10.3.3(2) 从工具调用入参提取展示用target(ActionStep结构化, 极少截断保留完整值; 截断收敛见observation_formatter)"""
    _name = call.get("tool_name", "")
    _params = call.get("tool_params", {}) or {}
    _field = _resolve_target_field(_name)
    if not _field:
        return _name
    _val = _params.get(_field, "")
    return str(_val) if _val != "" else _name
