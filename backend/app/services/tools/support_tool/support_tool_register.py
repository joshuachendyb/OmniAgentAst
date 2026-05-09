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


返回数据说明：
- code: 状态码
- data: exists(bool), db_type(str)""",

    "get_table_schema": """获取数据库表结构信息。

使用场景：
- 当用户需要查看表结构时使用
- 当用户在操作表前需要了解字段信息时使用


返回数据说明：
- code: 状态码
- data: columns, primary_key等信息""",

    "begin_transaction": """开始数据库事务。

使用场景：
- 当用户需要在数据库操作前开始事务时使用
- 当用户需要保证数据操作的原子性时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.transaction_id: 事务ID(str)
- message: 结果消息""",

    "commit_transaction": """提交数据库事务。

使用场景：
- 当用户需要提交事务使操作生效时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.transaction_id: 事务ID(str)
- message: 结果消息""",

    "rollback_transaction": """回滚数据库事务。

使用场景：
- 当用户需要撤销事务中的操作时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.transaction_id: 事务ID(str)
- message: 结果消息""",


    "check_network_connectivity": """检查网络连通性。

使用场景：
- 当用户需要确认网络是否可用时使用
- 当用户在执行网络操作前需要验证连通性时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.connected: 网络是否连通(bool)
- data.host: 连通的测试主机(str，连通时)
- data.latency_ms: 延迟毫秒数(float，连通时)
- message: 结果消息""",

    "validate_url": """验证URL格式是否正确。

使用场景：
- 当用户需要确认URL格式是否有效时使用
- 当用户在发送网络请求前需要验证URL时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.valid: URL是否有效(bool)
- data.scheme: 协议类型(str)
- data.netloc: 网络位置(str)
- data.path: 路径(str)
- data.error: 错误信息(str，异常时)
- message: 结果消息""",
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

    tools_to_register = [
        ("check_db_exists", check_db_exists, CheckDbExistsInput),
        ("get_table_schema", get_table_schema, GetTableSchemaInput),
        ("begin_transaction", begin_transaction, BeginTransactionInput),
        ("commit_transaction", commit_transaction, CommitTransactionInput),
        ("rollback_transaction", rollback_transaction, RollbackTransactionInput),
        ("check_network_connectivity", check_network_connectivity, CheckNetworkConnectivityInput),
        ("validate_url", validate_url, ValidateUrlInput),
    ]

    for name, impl, input_model in tools_to_register:
        examples = EXAMPLES.get(name, [])
        tool_registry.register(
            name=name,
            description=DESCRIPTIONS[name],
            category=ToolCategory.SUPPORT_TOOL,
            implementation=impl,
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[support_tool_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__}, examples: {len(examples)}个"
        )


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False
if not _initialized:
    _register_support_tool_tools()
    _initialized = True

__all__ = [
    "check_db_exists",
    "get_table_schema",
    "begin_transaction",
    "commit_transaction",
    "rollback_transaction",
    "check_network_connectivity",
    "validate_url",
]
