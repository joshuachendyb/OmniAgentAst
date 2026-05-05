# -*- coding: utf-8 -*-
"""
Document Register - 文档读写工具注册点

【架构规范】2026-05-02 小沈
- document_register.py 作为文档工具的注册点
- 实际工具实现在 document_tools.py 中
- 使用 registry.py 的 tool_registry.register() 显式注册

【工具列表】（共8个）
1. read_pdf - 读取PDF文件
2. read_docx - 读取Word文档
3. read_xlsx - 读取Excel文件
4. write_docx - 写入Word文档
5. write_xlsx - 写入Excel文件
6. read_pptx - 读取PPT幻灯片
7. write_pdf - 写入PDF文档
8. convert_document - 文档格式转换

【注册说明】
- 使用 Pydantic 模型注册，自动生成 OpenAI Schema
- 导入 document_register 时自动触发注册

创建时间: 2026-05-02
更新时间: 2026-05-04
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadXlsxInput,
    WriteDocxInput,
    WriteXlsxInput,
    ReadPptxInput,
    WritePdfInput,
    WritePptxInput,
    ConvertDocumentInput,
)

from app.services.tools.document.document_tools import (
    read_pdf,
    read_docx,
    read_xlsx,
    write_docx,
    write_xlsx,
    read_pptx,
    write_pdf,
    convert_document,
    write_pptx,
)

DESCRIPTIONS = {
    "read_pdf": """读取 PDF 文件并提取文本内容。

【使用场景】
- 当用户需要读取 PDF 文档内容时使用
- 当用户想要从 PDF 中提取文字信息时使用
- 当用户需要分析 PDF 文档内容时使用
- 当用户需要提取 PDF 中的表格数据时使用

【参数说明】
- file_path：PDF 文件路径（必填）
- pages：要读取的页面（可选），如 "1-5" 或 "1,3,5"
- extract_images：是否提取图片（可选），默认 false
- extract_tables：是否提取表格（可选），默认 false

【返回数据】
- code: SUCCESS / ERR_READ_PDF / ERR_NO_PDFPLUMBER
- data: { text, page_count, pages_read, tables? }
- message: 操作结果消息

【依赖库】pdfplumber（pip install pdfplumber）""",

    "read_docx": """读取 Word 文档并提取文本内容。

【使用场景】
- 当用户需要读取 Word 文档内容时使用
- 当用户想要从 Word 文档中提取文字信息时使用
- 当用户需要分析 Word 文档内容时使用
- 当用户需要提取 Word 文档中的表格时使用

【参数说明】
- file_path：Word 文件路径（必填）
- extract_tables：是否提取表格（可选），默认 false

【返回数据】
- code: SUCCESS / ERR_READ_DOCX / ERR_NO_DOCX
- data: { text, paragraph_count, tables?, table_count? }
- message: 操作结果消息

【依赖库】python-docx（pip install python-docx）""",

    "read_xlsx": """读取 Excel 文件并提取表格数据。

【使用场景】
- 当用户需要读取 Excel 表格数据时使用
- 当用户想要从 Excel 中提取数据进行分析时使用
- 当用户需要查看 Excel 文件内容时使用
- 当用户需要读取指定工作表时使用

【参数说明】
- file_path：Excel 文件路径（必填）
- sheet_name：工作表名称（可选），默认第一个
- max_rows：最大读取行数（可选），默认 1000
- header：第一行是否为表头（可选），默认 true
- index_col：第一列是否为索引（可选），默认 false

【返回数据】
- code: SUCCESS / ERR_READ_XLSX / ERR_NO_OPENPYXL
- data: { headers, rows, row_count, sheet_names }
- message: 操作结果消息

【依赖库】openpyxl（pip install openpyxl）""",

    "write_docx": """写入 Word 文档。

【使用场景】
- 当用户需要生成 Word 报告时使用
- 当用户需要导出文档时使用
- 当用户需要创建带表格的文档时使用

【参数说明】
- file_path：输出文件路径（必填）
- content：正文内容（可选）
- paragraphs：段落列表（可选），如 ["第一段", "第二段"]
- title：文档标题（可选）
- table_data：表格数据二维数组（可选），如 [["列1", "列2"], ["值1", "值2"]]

【返回数据】
- code: SUCCESS / ERR_WRITE_DOCX / ERR_NO_DOCX
- data: { file_path }
- message: 操作结果消息

【依赖库】python-docx（pip install python-docx）""",

    "write_xlsx": """写入 Excel 文件。

【使用场景】
- 当用户需要生成 Excel 报表时使用
- 当用户需要导出数据为 Excel 时使用
- 当用户需要创建带表头的数据表时使用

【参数说明】
- file_path：输出文件路径（必填）
- data：数据字典（必填），格式 {"headers": [...], "rows": [[...], [...]]}
- sheet_name：工作表名称（可选），默认 "Sheet1"

【返回数据】
- code: SUCCESS / ERR_WRITE_XLSX / ERR_NO_OPENPYXL
- data: { file_path, row_count }
- message: 操作结果消息

【依赖库】openpyxl（pip install openpyxl）""",

    "read_pptx": """读取 PPT 幻灯片。

【使用场景】
- 当用户需要读取 PPT 内容时使用
- 当用户需要提取 PPT 文字时使用
- 当用户需要提取演讲备注时使用

【参数说明】
- file_path：PPT 文件路径（必填）
- extract_notes：是否提取演讲备注（可选），默认 false

【返回数据】
- code: SUCCESS / ERR_READ_PPTX / ERR_NO_PPTX
- data: { slide_count, slides: [{ slide_num, text }], notes? }
- message: 操作结果消息

【依赖库】python-pptx（pip install python-pptx）""",

    "write_pdf": """写入 PDF 文档，支持标题、段落、表格。

【使用场景】
- 当用户需要生成PDF报告时使用
- 当用户需要导出为PDF格式时使用
- 当用户需要创建包含表格的PDF文档时使用

【参数说明】
- file_path：输出PDF文件路径（必填）
- title：文档标题（可选）
- content：正文内容（可选）
- paragraphs：段落列表（可选），如 ["第一段", "第二段"]
- table_data：表格数据二维数组（可选），如 [["列1", "列2"], ["值1", "值2"]]

【返回数据】
- code: SUCCESS / ERR_WRITE_PDF / ERR_NO_REPORTLAB
- data: { file_path }
- message: 操作结果消息

【依赖库】reportlab（pip install reportlab）""",

    "convert_document": """文档格式转换（docx/xlsx/pptx → PDF）。
 
【使用场景】
- 当用户需要将Word/Excel/PPT转换为PDF时使用
- 当用户说"把这个docx转成pdf"时使用
- 当用户需要分享不可编辑的文档时使用
 
【参数说明】
- input_path：输入文件路径（必填）。支持 .docx/.doc/.xlsx/.xls/.pptx/.ppt/.odt/.ods
- output_format：目标格式（必填）。当前仅支持 "pdf"
- output_path：输出文件路径（可选）。默认与输入同目录
 
【返回数据】
- code: SUCCESS / ERR_CONVERT_DOCUMENT / ERR_NO_LIBREOFFICE
- data: { input_path, output_path }
- message: 操作结果消息
 
【重要】需要安装LibreOffice（https://www.libreoffice.org/download/）""",
    "write_pptx": """写入 PPT 幻灯片。
 
【使用场景】
- 当用户需要生成PPT演示文稿时使用
- 当用户需要创建幻灯片时使用
- 当用户需要导出PPT文件时使用
 
【参数说明】
- file_path：输出文件路径（必填）
- title：演示文稿标题（可选）
- slides：幻灯片内容列表（可选），每个元素是一个字典，包含 title 和 content
 
【返回数据】
- code: SUCCESS / ERR_WRITE_PPTX / ERR_NO_PPTX
- data: { file_path, slide_count }
- message: 操作结果消息
 
【依赖库】python-pptx（pip install python-pptx）""",
}

EXAMPLES = {
    "read_pdf": [
        {"file_path": "D:/documents/report.pdf"},
        {"file_path": "D:/documents/report.pdf", "pages": "1-3"},
        {"file_path": "D:/documents/report.pdf", "pages": "1,3,5", "extract_tables": True},
    ],
    "read_docx": [
        {"file_path": "D:/documents/report.docx"},
        {"file_path": "D:/documents/report.docx", "extract_tables": True},
    ],
    "read_xlsx": [
        {"file_path": "D:/data/report.xlsx"},
        {"file_path": "D:/data/report.xlsx", "sheet_name": "Sheet2"},
        {"file_path": "D:/data/report.xlsx", "max_rows": 100, "header": True},
    ],
    "write_docx": [
        {"file_path": "D:/output/report.docx", "title": "测试报告", "content": "这是测试内容"},
        {"file_path": "D:/output/report.docx", "paragraphs": ["第一段内容", "第二段内容"]},
        {"file_path": "D:/output/table.docx", "table_data": [["Name", "Age"], ["张三", "25"], ["李四", "30"]]},
    ],
    "write_xlsx": [
        {"file_path": "D:/output/data.xlsx", "data": {"headers": ["姓名", "年龄"], "rows": [["张三", 25], ["李四", 30]]}},
        {"file_path": "D:/output/sales.xlsx", "data": {"headers": ["产品", "销量"], "rows": [["A", 100], ["B", 200]]}, "sheet_name": "销售数据"},
    ],
    "read_pptx": [
        {"file_path": "D:/documents/presentation.pptx"},
        {"file_path": "D:/documents/presentation.pptx", "extract_notes": True},
    ],
    "write_pdf": [
        {"file_path": "D:/output/report.pdf", "title": "测试报告", "content": "这是报告内容"},
        {"file_path": "D:/output/data.pdf", "paragraphs": ["第一段", "第二段"]},
        {"file_path": "D:/output/table.pdf", "title": "数据表", "table_data": [["Name", "Age"], ["张三", "25"], ["李四", "30"]]},
    ],
    "convert_document": [
        {"input_path": "D:/documents/report.docx", "output_format": "pdf"},
        {"input_path": "D:/data/sales.xlsx", "output_format": "pdf", "output_path": "D:/output/sales.pdf"},
    ],
}

TOOL_INPUT_MODELS = {
    "read_pdf": ReadPdfInput,
    "read_docx": ReadDocxInput,
    "read_xlsx": ReadXlsxInput,
    "write_docx": WriteDocxInput,
    "write_xlsx": WriteXlsxInput,
    "read_pptx": ReadPptxInput,
    "write_pdf": WritePdfInput,
    "convert_document": ConvertDocumentInput,
}

TOOL_IMPLEMENTATIONS = {
    "read_pdf": read_pdf,
    "read_docx": read_docx,
    "read_xlsx": read_xlsx,
    "write_docx": write_docx,
    "write_xlsx": write_xlsx,
    "read_pptx": read_pptx,
    "write_pdf": write_pdf,
    "write_pptx": write_pptx,
    "convert_document": convert_document,
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
    "write_docx",
    "write_xlsx",
    "read_pptx",
    "write_pdf",
    "convert_document",
]
