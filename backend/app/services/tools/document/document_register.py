# -*- coding: utf-8 -*-
"""
Document Register - 文档读写工具注册点

【架构规范】2026-05-02 小沈
- document_register.py 作为文档工具的注册点
- 实际工具实现在 document_tools.py 中
- 使用 registry.py 的 tool_registry.register() 显式注册

【工具列表】（共3个）
1. read_pdf - 读取PDF文件
2. read_docx - 读取Word文档
3. read_xlsx - 读取Excel文件

【注册说明】
- 使用 Pydantic 模型注册，自动生成 OpenAI Schema
- 导入 document_register 时自动触发注册

创建时间: 2026-05-02
更新时间: 2026-05-02
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadXlsxInput,
)

from app.services.tools.document.document_tools import (
    read_pdf,
    read_docx,
    read_xlsx,
)

DESCRIPTIONS = {
    "read_pdf": """读取 PDF 文件并提取文本内容。

使用场景：
- 当用户需要读取 PDF 文档内容时使用
- 当用户想要从 PDF 中提取文字信息时使用
- 当用户需要分析 PDF 文档内容时使用

参数说明：
- file_path：PDF 文件路径
- pages：要读取的页面（如 "1-5" 或 "1,3,5"）
- extract_images：是否提取图片，默认 false

【重要】需要安装 pdfplumber 库（pip install pdfplumber）

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_PDF/ERR_NO_PDFPLUMBER）
- data: 包含text、page_count、pages_read的字典
- message: 操作结果消息""",

    "read_docx": """读取 Word 文档并提取文本内容。

使用场景：
- 当用户需要读取 Word 文档内容时使用
- 当用户想要从 Word 文档中提取文字信息时使用
- 当用户需要分析 Word 文档内容时使用

参数说明：
- file_path：Word 文件路径

【重要】需要安装 python-docx 库（pip install python-docx）

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_DOCX/ERR_NO_DOCX）
- data: 包含text、paragraph_count的字典
- message: 操作结果消息""",

    "read_xlsx": """读取 Excel 文件并提取表格数据。

使用场景：
- 当用户需要读取 Excel 表格数据时使用
- 当用户想要从 Excel 中提取数据进行分析时使用
- 当用户需要查看 Excel 文件内容时使用

参数说明：
- file_path：Excel 文件路径
- sheet_name：工作表名称（默认第一个）
- max_rows：最大读取行数，默认 1000

【重要】需要安装 openpyxl 库（pip install openpyxl）

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_XLSX/ERR_NO_OPENPYXL）
- data: 包含headers、rows、row_count、sheet_names的字典
- message: 操作结果消息""",
}

EXAMPLES = {
    "read_pdf": [
        {"file_path": "D:/documents/report.pdf"},
        {"file_path": "D:/documents/report.pdf", "pages": "1-3"},
    ],
    "read_docx": [
        {"file_path": "D:/documents/report.docx"},
    ],
    "read_xlsx": [
        {"file_path": "D:/data/report.xlsx"},
        {"file_path": "D:/data/report.xlsx", "sheet_name": "Sheet2"},
    ],
}

TOOL_INPUT_MODELS = {
    "read_pdf": ReadPdfInput,
    "read_docx": ReadDocxInput,
    "read_xlsx": ReadXlsxInput,
}

TOOL_IMPLEMENTATIONS = {
    "read_pdf": read_pdf,
    "read_docx": read_docx,
    "read_xlsx": read_xlsx,
}


def _register_document_tools():
    """注册所有文档读写工具 - 小沈 2026-05-02"""
    for name, func in TOOL_IMPLEMENTATIONS.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DOCUMENT,
            implementation=func,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[document_register] 已注册工具: {name}, "
            f"Pydantic模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


_register_document_tools()


__all__ = [
    "read_pdf",
    "read_docx",
    "read_xlsx",
]
