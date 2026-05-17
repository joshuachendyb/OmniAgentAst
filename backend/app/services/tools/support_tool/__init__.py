# -*- coding: utf-8 -*-
"""
Support Tool 模块 - 支撑工具（公共函数 + LLM可调用Tool）

【更新 2026-05-14 小健】5个数据库事务工具已移到database分类注册，
但函数实现仍在本模块(support_tool_tools.py)中作为公共基础设施。
【更新 2026-05-17 小沈】check_db_exists已迁移到toolhelper/db_helper.py；
get_table_schema和3个事务函数已弃用，仅保留向后兼容。
"""

from app.services.tools.support_tool.support_tool_register import *
from app.services.tools.support_tool.support_tool_tools import (
    # 【2026-05-17 小沈 已弃用-兼容】check_db_exists 实现已迁移到 toolhelper/db_helper.py
    check_db_exists,
    # 【2026-05-17 小沈 已弃用】请使用 database_tools.get_db_schema(table_name=...) 代替
    get_table_schema,
    # 【2026-05-17 小沈 已弃用】事务控制工具已从 database 分类移除
    begin_transaction,
    commit_transaction,
    rollback_transaction,
    # 仍在support_tool分类注册的2个工具
    check_network_connectivity,
    validate_url,
)

__all__ = [
    "_register_support_tool_tools",
    "check_db_exists",
    "get_table_schema",
    "begin_transaction",
    "commit_transaction",
    "rollback_transaction",
    "check_network_connectivity",
    "validate_url",
]
