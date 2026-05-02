# -*- coding: utf-8 -*-
"""
Support Tool Register - 支撑工具显式注册

【架构规范】2026-05-02 小沈
【更新时间】2026-05-02 小沈 - 从@register_tool装饰器改为显式注册
【更新时间】2026-05-02 小沈 - 将4个使用input_schema的工具改为使用Pydantic模型

================================================================================
一、注册方式
================================================================================
使用 tool_registry.register() 逐一注册，category=ToolCategory.SUPPORT_TOOL

================================================================================
二、包含工具（7个）
================================================================================
- check_db_exists: 检查数据库是否存在（input_model）
- get_table_schema: 获取表结构（input_model）
- begin_transaction: 开始事务（input_model）
- commit_transaction: 提交事务（input_model）
- rollback_transaction: 回滚事务（input_model）
- check_network_connectivity: 检查网络连通性（input_model）
- validate_url: 验证URL格式（input_model）

Author: 小沈 - 2026-05-02
"""

import logging

from app.services.tools.registry import tool_registry, ToolCategory
from app.services.tools.support_tool.support_tool_schema import (
    CheckDbExistsInput,
    GetTableSchemaInput,
    ValidateUrlInput,
    BeginTransactionInput,
    CommitTransactionInput,
    RollbackTransactionInput,
    CheckNetworkConnectivityInput,
)
from app.services.tools.support_tool.support_tool_tools import (
    check_db_exists,
    get_table_schema,
    begin_transaction,
    commit_transaction,
    rollback_transaction,
    check_network_connectivity,
    validate_url,
)

logger = logging.getLogger(__name__)

DESCRIPTIONS = {
    "check_db_exists": """检查数据库文件是否存在且可连接。

使用场景：
- 当用户需要确认数据库是否存在时使用
- 当用户在操作数据库前需要验证时使用

参数说明：
- db_path：数据库文件路径

返回数据说明：
- code: 状态码
- data: exists(bool), db_type(str)""",

    "get_table_schema": """获取数据库表结构信息。

使用场景：
- 当用户需要查看表结构时使用
- 当用户在操作表前需要了解字段信息时使用

参数说明：
- db_path：数据库文件路径
- table_name：表名称

返回数据说明：
- code: 状态码
- data: columns, primary_key等信息""",

    "begin_transaction": """开始数据库事务。

使用场景：
- 当用户需要在数据库操作前开始事务时使用
- 当用户需要保证数据操作的原子性时使用

【重要】返回事务ID，用于后续commit/rollback""",

    "commit_transaction": """提交数据库事务。

使用场景：
- 当用户需要提交事务使操作生效时使用

参数说明：
- transaction_id：事务ID""",

    "rollback_transaction": """回滚数据库事务。

使用场景：
- 当用户需要撤销事务中的操作时使用

参数说明：
- transaction_id：事务ID""",

    "check_network_connectivity": """检查网络连通性。

使用场景：
- 当用户需要确认网络是否可用时使用
- 当用户在执行网络操作前需要验证连通性时使用

【重要】返回网络是否可用及延迟信息""",

    "validate_url": """验证URL格式是否正确。

使用场景：
- 当用户需要确认URL格式是否有效时使用
- 当用户在发送网络请求前需要验证URL时使用

参数说明：
- url：要验证的URL

【重要】返回URL是否有效及解析信息""",
}

EXAMPLES = {
    "check_db_exists": [{"db_path": "D:/data/app.db"}],
    "get_table_schema": [{"db_path": "D:/data/app.db", "table_name": "users"}],
    "begin_transaction": [{}],
    "commit_transaction": [{"transaction_id": "abc12345"}],
    "rollback_transaction": [{"transaction_id": "abc12345"}],
    "check_network_connectivity": [{}],
    "validate_url": [{"url": "https://example.com"}],
}


def _register_support_tool_tools():
    """注册所有支撑工具 - 小沈 2026-05-02"""

    tool_registry.register(
        name="check_db_exists",
        description=DESCRIPTIONS["check_db_exists"],
        category=ToolCategory.SUPPORT_TOOL,
        implementation=check_db_exists,
        input_model=CheckDbExistsInput,
        examples=EXAMPLES["check_db_exists"],
    )

    tool_registry.register(
        name="get_table_schema",
        description=DESCRIPTIONS["get_table_schema"],
        category=ToolCategory.SUPPORT_TOOL,
        implementation=get_table_schema,
        input_model=GetTableSchemaInput,
        examples=EXAMPLES["get_table_schema"],
    )

    tool_registry.register(
        name="begin_transaction",
        description=DESCRIPTIONS["begin_transaction"],
        category=ToolCategory.SUPPORT_TOOL,
        implementation=begin_transaction,
        input_model=BeginTransactionInput,
        examples=EXAMPLES["begin_transaction"],
    )

    tool_registry.register(
        name="commit_transaction",
        description=DESCRIPTIONS["commit_transaction"],
        category=ToolCategory.SUPPORT_TOOL,
        implementation=commit_transaction,
        input_model=CommitTransactionInput,
        examples=EXAMPLES["commit_transaction"],
    )

    tool_registry.register(
        name="rollback_transaction",
        description=DESCRIPTIONS["rollback_transaction"],
        category=ToolCategory.SUPPORT_TOOL,
        implementation=rollback_transaction,
        input_model=RollbackTransactionInput,
        examples=EXAMPLES["rollback_transaction"],
    )

    tool_registry.register(
        name="check_network_connectivity",
        description=DESCRIPTIONS["check_network_connectivity"],
        category=ToolCategory.SUPPORT_TOOL,
        implementation=check_network_connectivity,
        input_model=CheckNetworkConnectivityInput,
        examples=EXAMPLES["check_network_connectivity"],
    )

    tool_registry.register(
        name="validate_url",
        description=DESCRIPTIONS["validate_url"],
        category=ToolCategory.SUPPORT_TOOL,
        implementation=validate_url,
        input_model=ValidateUrlInput,
        examples=EXAMPLES["validate_url"],
    )

    logger.info(f"[support_tool_register] 已注册 {7} 个支撑工具")


_register_support_tool_tools()

__all__ = [
    "check_db_exists",
    "get_table_schema",
    "begin_transaction",
    "commit_transaction",
    "rollback_transaction",
    "check_network_connectivity",
    "validate_url",
]
