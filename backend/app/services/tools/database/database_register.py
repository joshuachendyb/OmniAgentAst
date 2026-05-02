# -*- coding: utf-8 -*-
"""
DATABASE Register - 数据库工具注册点

【架构规范】2026-04-29 小沈

【工具列表】（共3个）
1. query_sql - 执行只读SQL查询
2. execute_sql - 执行写操作SQL
3. get_db_schema - 获取数据库表结构

创建时间: 2026-04-29
"""

import logging
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

# 工具描述
DATABASE_TOOL_DESCRIPTIONS = {
    "query_sql": "执行只读SQL查询（SELECT/SHOW/DESCRIBE），不支持写操作，返回查询结果集。适合查询数据、查看表内容、统计记录数",
    "execute_sql": "执行写操作SQL（INSERT/UPDATE/DELETE/DDL），包含危险操作检测和dryRun预览模式。适合插入数据、更新记录、创建表结构",
    "get_db_schema": "获取数据库表结构元数据，包括表名、字段、类型、索引、外键等信息。适合查看数据库结构、了解表设计",
}

# 模型映射
DATABASE_TOOL_INPUT_MODELS = {
    "query_sql": QuerySqlInput,
    "execute_sql": ExecuteSqlInput,
    "get_db_schema": GetDbSchemaInput,
}

# 使用示例
DATABASE_TOOL_EXAMPLES = {
    "query_sql": [
        {"sql": "SELECT * FROM users LIMIT 10"},
        {"sql": "SELECT name, email FROM orders WHERE status = 'pending'", "limit": 50},
    ],
    "execute_sql": [
        {"sql": "INSERT INTO logs (msg) VALUES ('test')"},
        {"sql": "DELETE FROM temp_data WHERE created_at < '2024-01-01'", "dry_run": True},
    ],
    "get_db_schema": [
        {},
        {"filter_pattern": "user%"},
        {"include_details": True, "output_format": "json"},
    ],
}


def _register_database_tools():
    """
    【2026-04-29 小沈】按文档5.1设计注册所有数据库工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    【小健 2026-04-29】强制要求：此函数在新增工具时必须在TOOL_INPUT_MODELS中添加映射，并传入input_model参数
    """
    # 统一的工具映射 - 注册名与实际函数名一致
    tool_methods = {
        "query_sql": query_sql,
        "execute_sql": execute_sql,
        "get_db_schema": get_db_schema,
    }

    # 注册所有工具
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
            f"[database_register] 已注册工具: {name}, "
            f"使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


# 触发注册
_register_database_tools()
