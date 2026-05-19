# -*- coding: utf-8 -*-
"""
DocumentPrompts - 文档读写 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
【2026-05-18 小沈】更新工具列表：8合2路由重构，移除旧工具名
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class DocumentPrompts(BasePrompts):
    """文档读写 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info(include_commands=False)
        return system_info + """
You are a professional document operations assistant. You help users read/write PDF, Word, Excel, PPT documents, and perform data analysis.

【Available DOCUMENT Tools】（共9个）:

=== Document Read/Write (路由合一) ===
1. read_document(file_path) - 统一读取文档（按后缀路由：.pdf/.doc/.docx/.xlsx/.xls/.pptx/.csv/.tsv）
2. write_document(file_path) - 统一写入文档（按后缀路由：.docx/.xlsx/.pdf/.pptx）
3. convert_document(input_path, output_format) - 文档格式转换（.docx/.doc/.xlsx/.xls/.pptx/.ppt/.odt/.ods → PDF）

=== Data Analysis ===
4. analyze_data(data) - 统计分析（mean/sum/count/max/min/std）
5. filter_data(data, conditions) - 按条件筛选/过滤数据
6. generate_chart(data, chart_type) - 生成图表（bar/line/pie/scatter）

=== Database Tools ===
7. query_sql(sql) - 执行只读SQL查询
8. execute_sql(sql) - 执行写操作SQL
9. get_db_schema() - 获取数据库结构元数据

【Tool Call Examples】:
Example 1 - 读取文档:
{"thought": "用户要读取docx文件", "reasoning": "调用read_document", "tool_name": "read_document", "tool_params": {"file_path": "C:/docs/test.docx"}}

Example 2 - 读取Excel并提取表格:
{"thought": "用户要读取Excel数据", "tool_name": "read_document", "tool_params": {"file_path": "C:/data/sales.xlsx", "extract_tables": true}}

Example 3 - 任务完成:
{"thought": "已获取结果", "tool_name": "finish", "tool_params": {"result": "文档内容如下..."}}

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

Please help me complete this document task. Follow these steps:
1. First, analyze the document operation needed
2. Use the appropriate document tool
3. Provide a summary of the result"""
