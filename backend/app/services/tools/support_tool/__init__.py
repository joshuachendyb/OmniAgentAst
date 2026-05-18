# -*- coding: utf-8 -*-
"""
Support Tool 模块 - 已废弃，功能已迁移

【2026-05-18 小沈】support_tool 分类已全面废弃：
- check_network_connectivity/validate_url → toolhelper/network_helper.py
- check_db_exists → toolhelper/db_helper.py
- get_table_schema → database/database_tools.py (get_db_schema)
- begin/commit/rollback_transaction → 已弃用(execute_sql可执行全部SQL含事务)

本模块仅保留向后兼容包装器，不再注册任何LLM工具。
"""

from app.services.tools.support_tool.support_tool_register import (
    _register_support_tool_tools,
)

__all__ = [
    "_register_support_tool_tools",
]
