# -*- coding: utf-8 -*-
"""
DATABASE Register - Database Tools Registration Point

[Architecture Standard] 2026-04-29 Xiao Shen
[更新 2026-05-14 小健] 从support_tool移入5个数据库事务工具

[Tool List] (8 tools)
1. query_sql - Execute read-only SQL query
2. execute_sql - Execute write SQL
3. get_db_schema - Get database schema
4. check_db_exists - 检查数据库是否存在（从support_tool移入）
5. get_table_schema - 获取表结构（从support_tool移入）
6. begin_transaction - 开始事务（从support_tool移入）
7. commit_transaction - 提交事务（从support_tool移入）
8. rollback_transaction - 回滚事务（从support_tool移入）

Created: 2026-04-29
"""

from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.database.database_schema import (
    QuerySqlInput,
    ExecuteSqlInput,
    GetDbSchemaInput,
)

from app.services.tools.database.database_tools import (
    query_sql,
    execute_sql,
    get_db_schema,
)

# 【2026-05-14 小健】从support_tool移入的5个数据库事务工具
from app.services.tools.support_tool.support_tool_schema import (
    CheckDbExistsInput,
    GetTableSchemaInput,
    BeginTransactionInput,
    CommitTransactionInput,
    RollbackTransactionInput,
)
from app.services.tools.support_tool.support_tool_tools import (
    check_db_exists,
    get_table_schema,
    begin_transaction,
    commit_transaction,
    rollback_transaction,
)

# Tool descriptions（中文，与schema/tools一致）- 小健 2026-05-05修正
DATABASE_TOOL_DESCRIPTIONS = {
    "query_sql": """执行只读SQL查询（SELECT/SHOW/DESCRIBE），返回结果集。

【使用场景】
- 当用户需要查询数据库数据时使用
- 当用户需要分析表数据时使用
- 当需要执行只读操作时使用


【重要】强制只读，写操作返回错误。超时自动触发EXPLAIN分析。

【返回数据】
- code: SUCCESS / ERR_READ_ONLY_VIOLATION / ERR_DB_CONNECTION / ERR_SQL_EXEC
- data: { columns, rows, total }
- message: 操作结果消息

【示例】
- 简单查询: {"sql": "SELECT * FROM users LIMIT 10"}
- JSON输出: {"sql": "SELECT id, name FROM orders", "output_format": "json"}
- SQLite: {"sql": "SELECT * FROM users", "connection_type": "sqlite", "db_path": "D:/data/app.db"}""",

    "execute_sql": """执行写操作SQL（INSERT/UPDATE/DELETE/DDL）。

【使用场景】
- 当用户需要修改数据库数据时使用
- 当用户需要执行CREATE TABLE等DDL时使用
- 当需要执行写操作时使用


【重要】仅支持单语句自动提交。高风险操作（DROP/TRUNCATE）自动拦截。

【返回数据】
- code: SUCCESS / WARNING / ERR_DB_CONNECTION / ERR_SQL_EXEC / ERR_EXEC_FAILED
- data: { affected_rows, sql }
- message: 操作结果消息

【示例】
- 插入: {"sql": "INSERT INTO logs (msg) VALUES ('test')"}
- 预演: {"sql": "DELETE FROM temp_logs", "dry_run": true}
- SQLite: {"sql": "INSERT INTO users (name) VALUES ('test')", "connection_type": "sqlite", "db_path": "D:/data/app.db"}""",

    "get_db_schema": """获取数据库结构元数据，包括表名、字段、类型、索引、外键。

【使用场景】
- 当用户需要查看数据库表结构时使用
- 当用户需要理解表设计时
- 当用户需要生成DDL时使用


【重要】include_details=true时最多返回20个表，防止上下文爆炸。

【返回数据】
- code: SUCCESS / ERR_DB_CONNECTION / ERR_SQL_EXEC / ERR_SCHEMA_FAILED
- data: { tables: [{name, columns, indexes}], total }
- message: 操作结果消息

【示例】
- 所有表: {}
- 过滤: {"filter_pattern": "user%"}
- JSON: {"include_details": True, "output_format": "json"}
- SQLite: {"filter_pattern": "orders%", "connection_type": "sqlite", "db_path": "D:/data/app.db"}""",

    # 【2026-05-14 小健】从support_tool移入
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

【重要】此工具不需要任何参数，不要传递任何参数！直接调用即可。

使用场景：
- 当用户需要在数据库操作前开始事务时使用
- 当用户需要保证数据操作的原子性时使用

使用示例：
- 正确：{}  # 无参数，直接调用
- 错误：{"name": "xxx"}  # 不要传任何参数！

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
}

# Model mapping
DATABASE_TOOL_INPUT_MODELS = {
    "query_sql": QuerySqlInput,
    "execute_sql": ExecuteSqlInput,
    "get_db_schema": GetDbSchemaInput,
    # 【2026-05-14 小健】从support_tool移入
    "check_db_exists": CheckDbExistsInput,
    "get_table_schema": GetTableSchemaInput,
    "begin_transaction": BeginTransactionInput,
    "commit_transaction": CommitTransactionInput,
    "rollback_transaction": RollbackTransactionInput,
}

# Usage examples
DATABASE_TOOL_EXAMPLES = {
    "query_sql": [
        {"sql": "SELECT * FROM users LIMIT 10"},
        {"sql": "SELECT name, email FROM orders WHERE status = 'pending'", "limit": 50},
        {"sql": "SELECT * FROM logs", "timeout": 20000, "output_format": "json"},
        {"sql": "SELECT * FROM users", "connection_type": "sqlite", "db_path": "D:/data/app.db"},
    ],
    "execute_sql": [
        {"sql": "INSERT INTO logs (msg) VALUES ('test')"},
        {"sql": "DELETE FROM temp_data WHERE created_at < '2024-01-01'", "dry_run": True},
        {"sql": "UPDATE users SET status = 'active'", "affected_rows_check": True, "timeout": 30000},
        {"sql": "INSERT INTO users (name) VALUES ('test')", "connection_type": "sqlite", "db_path": "D:/data/app.db"},
    ],
    "get_db_schema": [
        {"db_name": "myapp"},
        {"filter_pattern": "user%"},
        {"include_details": True, "output_format": "json"},
        {"filter_pattern": "orders%", "connection_type": "sqlite", "db_path": "D:/data/app.db"},
    ],
    # 【2026-05-14 小健】从support_tool移入
    "check_db_exists": [{"db_path": "D:/data/app.db"}],
    "get_table_schema": [{"db_path": "D:/data/app.db", "table_name": "users"}],
    "begin_transaction": [{}],
    "commit_transaction": [{"transaction_id": "abc12345"}],
    "rollback_transaction": [{"transaction_id": "abc12345"}],
}


def _register_database_tools():
    """
    [2026-04-29 Xiao Shen] Register all database tools per doc 5.1 design
    [2026-05-14 小健] 从support_tool移入5个数据库事务工具
    Use Pydantic model for auto OpenAI Schema
    """
    tool_methods = {
        "query_sql": query_sql,
        "execute_sql": execute_sql,
        "get_db_schema": get_db_schema,
        # 【2026-05-14 小健】从support_tool移入
        "check_db_exists": check_db_exists,
        "get_table_schema": get_table_schema,
        "begin_transaction": begin_transaction,
        "commit_transaction": commit_transaction,
        "rollback_transaction": rollback_transaction,
    }

    for name, method in tool_methods.items():
        desc = DATABASE_TOOL_DESCRIPTIONS.get(name, "")
        input_model = DATABASE_TOOL_INPUT_MODELS.get(name)
        examples = DATABASE_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DATABASE,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[database_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个"
        )


# Trigger registration
# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_database_tools"]
