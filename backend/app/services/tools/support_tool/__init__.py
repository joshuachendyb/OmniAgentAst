# -*- coding: utf-8 -*-
"""
Support Tool 模块 - 支撑工具（公共函数 + LLM可调用Tool）

【架构规范】2026-05-02 小沈
【更新时间】2026-05-02 小沈

================================================================================
一、模块性质（双重身份）
================================================================================
本模块的函数具有双重身份：

1. **公共辅助函数（主要用途 90%）** - 被其他Tool函数内部调用
   - 例如：query_sql内部调用check_db_exists验证数据库存在
   - 例如：http_request内部调用validate_url验证URL格式

2. **LLM可调用Tool（次要用途 10%）** - 可被用户直接调用
   - 用户问"检查数据库是否存在" → LLM调用check_db_exists
   - 用户问"这个URL格式对不对" → LLM调用validate_url

【重要】这些函数主要作为公共基础设施供其他Tool调用，LLM直接调用场景较少。

Author: 小沈 - 2026-05-02
"""

from app.services.tools.support_tool import support_tool_register
from app.services.tools.support_tool import support_tool_tools

from app.services.tools.support_tool.support_tool_tools import (
    check_db_exists,
    get_table_schema,
    begin_transaction,
    commit_transaction,
    rollback_transaction,
    check_network_connectivity,
    validate_url,
)

__all__ = [
    "check_db_exists",
    "get_table_schema",
    "begin_transaction",
    "commit_transaction",
    "rollback_transaction",
    "check_network_connectivity",
    "validate_url",
]
