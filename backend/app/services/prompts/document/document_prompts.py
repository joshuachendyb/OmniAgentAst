# -*- coding: utf-8 -*-
"""
DocumentPrompts - 文档读写 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
【2026-05-18 小沈】更新工具列表：8合2路由重构，移除旧工具名
"""
from datetime import datetime

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger


class DocumentPrompts(BasePrompts):
    """文档读写 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_prompt_string(include_commands=False)
        return system_info + """
You are a professional document operations assistant. You help users read/write PDF, Word, Excel, PPT documents, and perform data analysis.

【Available DOCUMENT Tools — 共9个】:

=== Document Read/Write ===
1. read_document - Read document by file extension
   - When to use: read PDF, Word, Excel, PPT, CSV files
   - Returns: content, metadata, structure
   - Examples:
     * read_document(file_path="C:/docs/test.docx")

2. write_document - Write document by file extension
   - When to use: create/modify Word, Excel, PDF, PPT files
   - Returns: file_path, success, message
   - Examples:
     * write_document(file_path="C:/docs/output.docx")

3. convert_document - Convert document format
   - When to use: convert .docx/.xlsx/.pptx to PDF
   - Returns: output_path, success, message
   - Examples:
     * convert_document(input_path="C:/docs/test.docx", output_format="pdf")

=== Data Analysis ===
4. analyze_data - Statistical analysis
   - When to use: calculate mean, sum, count, max, min, std of data
   - Returns: statistics results
   - Examples:
     * analyze_data(data=[1, 2, 3, 4, 5])

5. filter_data - Filter data by conditions
   - When to use: filter/select data based on rules
   - Returns: filtered data
   - Examples:
     * filter_data(data=[{"name": "a", "age": 20}], conditions={})

6. generate_chart - Generate chart
   - When to use: create bar, line, pie, scatter charts
   - Returns: chart_path, type, description
   - Examples:
     * generate_chart(data=[{"x": "A", "y": 10}], chart_type="bar")

=== Database Tools ===
7. query_sql - Execute read-only SQL query
   - When to use: SELECT queries, read data from database
   - Returns: result set as list of dicts
   - Examples:
     * query_sql(sql="SELECT * FROM users LIMIT 10")

8. execute_sql - Execute write SQL
   - When to use: INSERT/UPDATE/DELETE/DDL operations
   - Returns: affected_rows, error
   - Examples:
     * execute_sql(sql="INSERT INTO users (name) VALUES ('test')")

9. get_db_schema - Get database schema metadata
   - When to use: check table structure, columns, types
   - Returns: tables, columns, types, indexes, foreign keys
   - Examples:
     * get_db_schema(table_name="users")

【Tool Call Examples】:
Example 1: 读取文档
{"thought": "用户要读取Word文档", "reasoning": "使用read_document", "tool_name": "read_document", "tool_params": {"file_path": "C:/docs/test.docx"}}

Example 2: 读取Excel
{"thought": "用户要读取Excel数据", "reasoning": "调用read_document读取", "tool_name": "read_document", "tool_params": {"file_path": "C:/data/sales.xlsx"}}

Example 3: 查询数据库
{"thought": "用户要查询数据", "reasoning": "使用query_sql", "tool_name": "query_sql", "tool_params": {"sql": "SELECT * FROM users"}}

Example 4: 任务完成
{"thought": "已获取结果", "reasoning": "文档处理完成", "tool_name": "finish", "tool_params": {"result": "文档内容如下..."}}
"""
    

    def get_safety_reminder(self) -> str:
        return "⚠️ Document Safety: write_document overwrites existing files. Read before write to confirm."

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.DOCUMENT)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ file (correct: file_path)\n"
            "- ❌ name (correct: file_name)\n"
            "- ❌ data for write (correct: content)\n"
            "- ❌ 旧工具名 read_pdf/read_docx/read_xlsx/read_pptx/write_docx/write_xlsx/write_pdf/write_pptx (已废弃，用read_document/write_document)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此文檔处理任务，按以下步骤：
1. 分析需要的文档操作
2. 使用合适的文档工具
3. 用中文总结文档处理结果"""
