# -*- coding: utf-8 -*-
"""
DATABASE Register - Database Tools Registration Point

[Architecture Standard] 2026-04-29 Xiao Shen

[Tool List] (3 tools)
1. query_sql - Execute read-only SQL query
2. execute_sql - Execute write SQL
3. get_db_schema - Get database schema

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

# Tool descriptions（中文，与schema/tools一致）- 小健 2026-05-05修正
DATABASE_TOOL_DESCRIPTIONS = {
    "query_sql": """执行只读SQL查询（SELECT/SHOW/DESCRIBE），返回结果集。

【使用场景】
- 当用户需要查询数据库数据时使用
- 当用户需要分析表数据时使用
- 当需要执行只读操作时使用

【参数说明】
- sql: SQL查询语句（必填）。仅支持SELECT/SHOW/DESCRIBE等只读操作
- limit: 结果行数限制（可选）。默认50，防止上下文爆炸
- timeout: 超时毫秒数（可选）。默认15000，超5秒自动触发EXPLAIN
- output_format: 输出格式（可选）。默认table（人类可读），可选json（结构化）
- connection_type: 数据库类型（可选）。默认sqlite，可选mysql/postgresql
- connection_string: MySQL/PostgreSQL连接字符串（可选）。如 user:pass@host:port/dbname
- db_path: SQLite数据库文件路径（可选）。如 D:/data/app.db

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

【参数说明】
- sql: SQL写操作语句（必填）。支持INSERT/UPDATE/DELETE/DDL
- dry_run: 预演模式（可选）。默认False，DDL或危险操作自动强制True
- timeout: 超时毫秒数（可选）。默认30000，写操作严格监控
- affected_rows_check: 影响行数检查（可选）。默认True，影响>10000行需确认
- connection_type: 数据库类型（可选）。默认sqlite，可选mysql/postgresql
- connection_string: MySQL/PostgreSQL连接字符串（可选）
- db_path: SQLite数据库文件路径（可选）

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

【参数说明】
- db_name: 目标数据库名（可选）。默认None读取当前连接
- filter_pattern: 表名过滤模式（可选）。支持SQL LIKE语法，如 user%
- include_details: 包含详细信息（可选）。默认False，为True时最多20个表防上下文爆炸
- output_format: 输出格式（可选）。默认markdown，可选json/sql_ddl
- connection_type: 数据库类型（可选）。默认sqlite，可选mysql/postgresql
- connection_string: MySQL/PostgreSQL连接字符串（可选）
- db_path: SQLite数据库文件路径（可选）

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
}

# Model mapping
DATABASE_TOOL_INPUT_MODELS = {
    "query_sql": QuerySqlInput,
    "execute_sql": ExecuteSqlInput,
    "get_db_schema": GetDbSchemaInput,
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
}


def _register_database_tools():
    """
    [2026-04-29 Xiao Shen] Register all database tools per doc 5.1 design
    Use Pydantic model for auto OpenAI Schema
    """
    tool_methods = {
        "query_sql": query_sql,
        "execute_sql": execute_sql,
        "get_db_schema": get_db_schema,
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
_initialized = False
if not _initialized:
    _register_database_tools()
    _initialized = True
