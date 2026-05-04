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

# Tool descriptions
DATABASE_TOOL_DESCRIPTIONS = {
    "query_sql": "Execute read-only SQL query (SELECT/SHOW/DESCRIBE), returns result set.\n\nScenarios:\n- When user needs to query database data\n- When user wants to analyze table data\n\nParams:\n- sql: SELECT query statement\n- limit: result row limit (optional), default 50\n- timeout: timeout ms (optional), default 15000\n- output_format: output format (optional), default table\n\n[Important] Force read-only. Auto-trigger EXPLAIN on timeout\n\nExamples:\n- Simple: {\"sql\": \"SELECT * FROM users LIMIT 10\"}\n- JSON: {\"sql\": \"SELECT id, name FROM orders\", \"output_format\": \"json\"}",
    "execute_sql": "Execute write SQL (INSERT/UPDATE/DELETE/DDL).\n\nScenarios:\n- When user needs to modify database data\n- When user wants to execute CREATE TABLE\n\nParams:\n- sql: write SQL statement\n- dry_run: dry run mode (optional), default false\n- timeout: timeout ms (optional), default 30000\n- affected_rows_check: check affected rows (optional), default true\n\n[Important] Only supports single-statement auto-commit. High-risk ops auto-blocked\n\nExamples:\n- Insert: {\"sql\": \"INSERT INTO logs (msg) VALUES ('test')\"}\n- Dry run: {\"sql\": \"DELETE FROM temp_logs\", \"dry_run\": true}",
    "get_db_schema": "Get database schema metadata, including table names, fields, types, indexes, foreign keys.\n\nScenarios:\n- When user needs to view database table structure\n- When user wants to understand table design\n- When user needs DDL generation\n\nParams:\n- db_name: target database name (optional)\n- filter_pattern: table filter pattern (optional), supports SQL LIKE\n- include_details: include details (optional), default false\n- output_format: output format (optional), default markdown\n\n[Important] If include_details=true, max 20 tables to prevent context explosion\n\nExamples:\n- All tables: {}\n- Filter: {\"filter_pattern\": \"user%\"}\n- JSON: {\"include_details\": true, \"output_format\": \"json\"}",
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
    ],
    "execute_sql": [
        {"sql": "INSERT INTO logs (msg) VALUES ('test')"},
        {"sql": "DELETE FROM temp_data WHERE created_at < '2024-01-01'", "dry_run": True},
        {"sql": "UPDATE users SET status = 'active'", "affected_rows_check": True, "timeout": 30000},
    ],
    "get_db_schema": [
        {"db_name": "myapp"},
        {"filter_pattern": "user%"},
        {"include_details": True, "output_format": "json"},
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
            f"[database_register] Registered tool: {name}, "
            f"Pydantic model: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}"
        )


# Trigger registration
_register_database_tools()