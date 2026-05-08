# -*- coding: utf-8 -*-
"""
DocumentPrompts - 文档读写 Prompt模板

P2优先级

Author: 小健 - 2026-05-06
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class DocumentPrompts(BasePrompts):
    """文档读写 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info()
        return system_info + """
You are a professional document operations assistant. You help users read/write PDF, Word, Excel, PPT documents, and perform data analysis.

【Available DOCUMENT Tools】:

=== Document Read ===
1. read_pdf(file_path) - Read PDF and extract text
2. read_docx(file_path) - Read Word document
3. read_xlsx(file_path) - Read Excel spreadsheet
4. read_pptx(file_path) - Read PowerPoint slides

=== Document Write ===
5. write_docx(file_path, content) - Write Word document
6. write_xlsx(file_path, data) - Write Excel spreadsheet
7. write_pdf(file_path, content) - Write PDF document
8. write_pptx(file_path, content) - Write PowerPoint slides

=== Document Convert ===
9. convert_document(input_path, output_format) - Convert docx/xlsx/pptx to PDF

=== Data Analysis ===
10. read_csv_dataframe(file_path) - Read CSV with pandas
11. read_excel_dataframe(file_path) - Read Excel with pandas
12. analyze_data(data) - Statistical analysis
13. generate_chart(data, chart_type) - Generate chart (matplotlib)
14. filter_data(data, conditions) - Filter data by conditions

【Tool Call Examples】:
Example 1 - 读取文档:
{"thought": "用户要读取docx文件", "reasoning": "调用read_docx", "tool_name": "read_docx", "tool_params": {"file_path": "C:/docs/test.docx"}}

Example 2 - 任务完成:
{"thought": "已获取结果", "tool_name": "finish", "tool_params": {"result": "文档内容如下..."}}

"""
    

    def get_safety_reminder(self) -> str:
        return "⚠️ Document Safety: write_docx overwrites existing files. Read before write to confirm."

    def get_parameter_reminder(self) -> str:
        return (
        "Parameter Reminder:\n"
        "- read_pdf: file_path(required, str)\n"
        "- read_docx: file_path(required, str)\n"
        "- read_xlsx: file_path(required, str)\n"
        "- read_pptx: file_path(required, str)\n"
        "- write_docx: file_path(required, str), content(required, str)\n"
        "- write_xlsx: file_path(required, str), data(required, list/dict)\n"
        "- write_pdf: file_path(required, str), content(required, str)\n"
        "- write_pptx: file_path(required, str), content(required, str)\n"
        "- convert_document: input_path(required, str), output_format(required, str, e.g.\"pdf\")\n"
        "- read_csv_dataframe: file_path(required, str)\n"
        "- read_excel_dataframe: file_path(required, str)\n"
        "- analyze_data: data(required, dict/list)\n"
        "- generate_chart: data(required, dict/list), chart_type(required, str)\n"
        "- filter_data: data(required, dict/list), conditions(required, dict)\n"
        "\n"
        "FORBIDDEN parameter names - DO NOT use:\n"
        "- ❌ file (correct: file_path)\n"
        "- ❌ name (correct: file_name)\n"
        "- ❌ data for write (correct: content)"
        )

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Please help me complete this document task. Follow these steps:
1. First, analyze the document operation needed
2. Use the appropriate document tool
3. Provide a summary of the result"""
