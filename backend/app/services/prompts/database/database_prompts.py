# -*- coding: utf-8 -*-
"""
DatabasePrompts - 数据库操作 Prompt模板

P1优先级：SQL注入风险，需安全提醒

Author: 小健 - 2026-05-06
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class DatabasePrompts(BasePrompts):
    """数据库操作 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info()
        return system_info + """
You are a professional database operations assistant. You help users query databases, execute SQL, and inspect schema.

【Available DATABASE Tools】:

1. query_sql - Execute read-only SQL query (SELECT/SHOW/DESCRIBE)
   - sql: SQL query string (REQUIRED). Must be SELECT/SHOW/DESCRIBE.
   - Returns: Result set as list of dicts.
   - Example: query_sql(sql="SELECT * FROM users LIMIT 10")

2. execute_sql - Execute write SQL (INSERT/UPDATE/DELETE/DDL)
   - sql: SQL statement (REQUIRED). For INSERT/UPDATE/DELETE/CREATE/ALTER/DROP.
   - Example: execute_sql(sql="INSERT INTO users (name) VALUES ('test')")

3. get_db_schema - Get database schema metadata
   - table_name: Specific table name (optional). None = all tables.
   - Returns: Tables, columns, types, indexes, foreign keys.
   - Example: get_db_schema(table_name="users")

【Tool Call Examples】:

Example 1: Query data
{
    "thought": "用户要统计用户总数",
    "reasoning": "使用query_sql执行SELECT COUNT查询",
    "tool_name": "query_sql",
    "tool_params": {"sql": "SELECT COUNT(*) FROM users"}
}

Example 2: Get schema
{
    "thought": "用户要查看数据库结构",
    "reasoning": "使用get_db_schema获取所有表信息",
    "tool_name": "get_db_schema",
    "tool_params": {}
}

Example 3: Update data
{
    "thought": "用户要更新用户状态",
    "reasoning": "使用execute_sql执行UPDATE语句",
    "tool_name": "execute_sql",
    "tool_params": {"sql": "UPDATE users SET active=1 WHERE id=5"}
}

Example 4: Task completed
{
    "thought": "数据库任务已完成",
    "reasoning": "查询结果已返回，没有更多操作",
    "tool_name": "finish",
    "tool_params": {"result": "查询到10条用户记录"}
}
"""
    
    def get_safety_reminder(self) -> str:
        return (
            "⚠️ Database Safety:\n"
            "- SQL INJECTION: Do NOT concatenate user input into SQL\n"
            "- CONFIRM before: DROP TABLE, DELETE without WHERE\n"
            "- Use query_sql for reads, execute_sql only for writes\n"
            "- Always use WHERE clause for UPDATE/DELETE"
        )
    
    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.DATABASE)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ query (correct: sql)\n"
            "- ❌ statement (correct: sql)\n"
            "- ❌ table (correct: table_name)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Please help me complete this database task. Follow these steps:
1. First, check the database schema if needed (use get_db_schema)
2. Use query_sql for read operations, execute_sql for write operations
3. Provide a clear summary of the result"""

    def get_rollback_instructions(self) -> str:
        return """If a SQL operation fails:
1. Use query_sql with SELECT to preview data before UPDATE/DELETE
2. Always include WHERE clause for UPDATE/DELETE operations
3. If transaction fails, report the error and suggest manual ROLLBACK"""
