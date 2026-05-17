# -*- coding: utf-8 -*-
"""
Support Tool Register - 支撑工具显式注册（空壳）

【架构规范】2026-05-02 小沈
【更新时间】2026-05-14 小健 - 5个数据库事务工具移到database分类
【更新时间】2026-05-17 小沈 - 2个LLM工具(check_network_connectivity, validate_url)
             迁移到 toolhelper/network_helper.py，support_tool分类不再注册任何LLM工具

================================================================================
一、注册方式
================================================================================
_register_support_tool_tools() 为空操作，不再注册任何LLM工具

================================================================================
二、工具迁移记录
================================================================================
- check_network_connectivity → toolhelper/network_helper.py (_check_network)
- validate_url → toolhelper/network_helper.py (_validate_url)
- check_db_exists → toolhelper/db_helper.py (2026-05-17)
- get_table_schema → database_register.py (2026-05-14)
- begin_transaction/commit_transaction/rollback_transaction → 已弃用 (2026-05-14)

Author: 小沈 - 2026-05-02
"""

import logging

logger = logging.getLogger(__name__)


def _register_support_tool_tools():
    """注册支撑工具 - 小沈 2026-05-02, 小健 2026-05-14移除数据库工具
    【2026-05-17 小沈】2个网络LLM工具已迁移到toolhelper/network_helper.py，本函数为空操作
    """
    logger.info("[support_tool_register] support_tool分类不再注册任何LLM工具（已迁移到toolhelper）")


_initialized = False

__all__ = [
    "_register_support_tool_tools",
]
