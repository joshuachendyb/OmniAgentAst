# -*- coding: utf-8 -*-
"""
Tools 模块 - 按意图类型组织的工具集

拆分后 __init__.py 极简导出 — 小沈 2026-05-29
其余符号请从对应子模块直接导入:
  ToolCategory/ToolMetadata → app.services.tools.tool_types
  resolve_category → app.services.tools.tool_types
  get_* → app.services.tools.tool_queries
  to_openai_tools/generate_param_reminder/get_all_tools_* → app.services.tools.tool_description
"""

from app.services.tools.registry import tool_registry, register_tool, ToolRegistry
from app.services.tools.lazy_loader import ensure_tools_registered


__all__ = [
    "tool_registry",
    "register_tool",
    "ToolRegistry",
    "ensure_tools_registered",
]
