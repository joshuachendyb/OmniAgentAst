# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-12 - 小欧 - 新建: A4 工具门面 facade 包(方案4.4.3步骤1)。list_tools/execute_tool 组装调用, 供 API 层薄适配。
"""
services/tool — 工具门面(facade)

职责(方案4.4.3, 小欧 2026-08-12): API 层只调 services 层, 不直接接触 tools/safety;
facade 复用 tool_executor 统一执行入口 + tool_safety_checker 安全预检, 消除工具执行双路径。
"""
from .tool_facade import list_tools, execute_tool

__all__ = ["list_tools", "execute_tool"]