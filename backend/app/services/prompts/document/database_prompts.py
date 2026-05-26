# -*- coding: utf-8 -*-
"""
DatabasePrompts - 数据库操作 Prompt模板

P1优先级：SQL注入风险，需安全提醒

Author: 小健 - 2026-05-06
"""
from datetime import datetime

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class DatabasePrompts(BasePrompts):
    """数据库操作 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info(include_commands=False)
        return system_info + """
You are a professional database operations assistant. You help users query databases, execute SQL, and inspect schema.

【Available DATABASE Tools — 共3个】:

1. query_sql - Execute read-only SQL query
   - When to use: SELECT/SHOW/DESCRIBE read operations
   - Returns: result set as list of dicts
   - Examples:
     * query_sql(sql="SELECT * FROM users LIMIT 10")

2. execute_sql - Execute write SQL
   - When to use: INSERT/UPDATE/DELETE/DDL operations
   - Returns: affected_rows, last_insert_id, error
   - Examples:
     * execute_sql(sql="INSERT INTO users (name) VALUES ('test')")
     * execute_sql(sql="DROP TABLE temp", dry_run=True)

3. get_db_schema - Get database schema metadata
   - When to use: user asks about table structure, columns, indexes
   - Returns: tables, columns, types, indexes, foreign keys
   - Examples:
     * get_db_schema(table_name="users")

【Tool Call Examples】:
Example 1: 查询数据
{"thought": "用户要统计用户总数", "reasoning": "使用query_sql执行SELECT COUNT查询", "tool_name": "query_sql", "tool_params": {"sql": "SELECT COUNT(*) FROM users"}}

Example 2: 获取数据库结构
{"thought": "用户要查看数据库结构", "reasoning": "使用get_db_schema获取所有表信息", "tool_name": "get_db_schema", "tool_params": {}}

Example 3: 更新数据
{"thought": "用户要更新用户状态", "reasoning": "使用execute_sql执行UPDATE语句", "tool_name": "execute_sql", "tool_params": {"sql": "UPDATE users SET active=1 WHERE id=5"}}

Example 4: 任务完成
{"thought": "数据库任务已完成", "reasoning": "查询结果已返回", "tool_name": "finish", "tool_params": {"result": "查询到10条用户记录"}}
"""
    
    def get_safety_reminder(self) -> str:
        return (
            "⚠️ Database Safety:\n"
            "- SQL INJECTION: Do NOT concatenate user input into SQL\n"
            "- CONFIRM before: DROP TABLE, DELETE without WHERE"
        )
    
    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.DOCUMENT)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ query (correct: sql)\n"
            "- ❌ statement (correct: sql)\n"
            "- ❌ table (correct: table_name)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此数据库任务，按以下步骤：
1. 检查数据库结构（需要时使用get_db_schema）
2. 使用query_sql读或execute_sql写
3. 用中文报告查询结果"""

    def get_rollback_instructions(self) -> str:
        return """If a SQL operation fails:
1. Use query_sql with SELECT to preview data before UPDATE/DELETE
2. Always include WHERE clause for UPDATE/DELETE operations
3. If transaction fails, report the error and suggest manual ROLLBACK"""

