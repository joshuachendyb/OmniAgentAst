# -*- coding: utf-8 -*-
"""
Document Register - 文档操作工具注册点（仅DOCUMENT分类）

【2026-06-18 小欧】DATAANALYSIS 6个工具已迁出到 dataanalysis/ 独立目录

【工具列表】(共9个) → DOCUMENT分类:
1. read_pdf - 读取PDF文档
2. read_docx - 读取Word文档
3. read_pptx - 读取PPT文档
4. read_xlsx - 读取Excel文档
5. write_docx - 写入Word文档
6. write_xlsx - 写入Excel文档
7. write_pdf - 写入PDF文档
8. write_pptx - 写入PPT文档
9. convert_document - 文档格式转换

创建时间: 2026-05-02
更新时间: 2026-06-18 小欧
"""

from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.services.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadPptxInput,
    ReadXlsxInput,
    WriteDocxInput,
    WriteXlsxInput,
    WritePdfInput,
    WritePptxInput,
    ConvertDocumentInput,
)

from app.services.tools.document.document_tools import (
    read_pdf,
    read_docx,
    read_pptx,
    read_xlsx,
    write_docx,
    write_xlsx,
    write_pdf,
    write_pptx,
    convert_document,
)

DESCRIPTIONS = {
    "read_pdf": """读取PDF(.pdf)文件内容。支持页码范围选择(pages参数,如'1-3,5')和表格提取(extract_tables)。适用场景:需要读取PDF文档内容、提取表格数据时使用。""",
    "read_docx": """读取Word(.docx)文档内容。支持表格提取(extract_tables)。自动降级处理.doc格式(转PDF后读取)。适用场景:需要读取Word文档内容、提取文本和表格时使用。""",
    "read_pptx": """读取PPT(.pptx)演示文稿内容。提取每页幻灯片的文本和备注。适用场景:需要读取PPT内容、提取演讲稿时使用。""",
    "read_xlsx": """读取Excel(.xlsx)/CSV/TSV/JSON数据文件。支持指定工作表、最大行数、编码和分隔符。自动降级处理.xls格式(转PDF后读取)。适用场景:需要读取表格数据、分析数据集时使用。""",
    "write_docx": """写入Word(.docx)文档。支持标题(title)/正文(content)/段落(paragraphs)/表格(table_data)/结构化内容(data)。适用场景:需要生成Word报告、导出文档时使用。""",
    "write_xlsx": """写入Excel(.xlsx)文件。data参数支持dict(headers+rows)或list自动推断headers。可指定工作表名。适用场景:需要导出数据到Excel表格时使用。""",
    "write_pdf": """写入PDF(.pdf)文件。支持标题(title)/正文(content)/段落(paragraphs)/表格(table_data)。适用场景:需要生成PDF报告、归档文档时使用。""",
    "write_pptx": """写入PPT(.pptx)演示文稿。支持标题(title)和幻灯片列表(slides)。适用场景:需要生成PPT演示文稿时使用。""",
    "convert_document": """将Office文档转换为PDF格式。支持Word(.docx/.doc→PDF)、Excel(.xlsx/.xls→PDF)、PPT(.pptx/.ppt→PDF)以及OpenDocument格式(.odt/.ods→PDF)。需要系统安装LibreOffice。适用场景:需要将文档转为PDF进行分发、归档或打印时使用。""",
}

EXAMPLES = {
    "read_pdf": [
        {"file_path": "D:/documents/report.pdf"},
        {"file_path": "D:/documents/report.pdf", "pages": "1-3", "extract_tables": True},
    ],
    "read_docx": [
        {"file_path": "D:/documents/report.docx"},
        {"file_path": "D:/documents/report.docx", "extract_tables": True},
    ],
    "read_pptx": [
        {"file_path": "D:/documents/presentation.pptx"},
    ],
    "read_xlsx": [
        {"file_path": "D:/data/sales.xlsx", "sheet_name": "Sheet2", "max_rows": 100},
        {"file_path": "D:/data/sales.csv", "encoding": "gbk"},
    ],
    "write_docx": [
        {"file_path": "D:/output/report.docx", "title": "\u6d4b\u8bd5\u62a5\u544a", "content": "\u8fd9\u662f\u6d4b\u8bd5\u5185\u5bb9"},
        {"file_path": "D:/output/report_structured.docx", "data": {"title": "\u7ed3\u6784\u5316\u62a5\u544a", "content": [{"type": "h1", "text": "\u7b2c\u4e00\u7ae0"}, {"type": "paragraph", "text": "\u6b63\u6587\u5185\u5bb9"}, {"type": "table", "rows": [["\u52171", "\u52172"], ["a", "b"]]}]}},
    ],
    "write_xlsx": [
        {"file_path": "D:/output/data.xlsx", "data": {"headers": ["\u59d3\u540d", "\u5e74\u9f84"], "rows": [["\u5f20\u4e09", 25], ["\u674e\u56db", 30]]}},
    ],
    "write_pdf": [
        {"file_path": "D:/output/report.pdf", "title": "\u6d4b\u8bd5\u62a5\u544a", "content": "\u8fd9\u662f\u62a5\u544a\u5185\u5bb9"},
    ],
    "write_pptx": [
        {"file_path": "D:/output/presentation.pptx", "title": "\u9879\u76ee\u6c47\u62a5"},
        {"file_path": "D:/output/slides.pptx", "title": "\u5b63\u5ea6\u603b\u7ed3", "slides": [{"title": "\u4e1a\u7ee9\u6982\u89c8", "content": "\u672c\u5b63\u5ea6\u9500\u552e\u989d\u589e\u957f20%"}]},
    ],
    "convert_document": [
        {"input_path": "D:/documents/report.docx", "output_format": "pdf"},
        {"input_path": "D:/data/sales.xlsx", "output_format": "pdf", "output_path": "D:/output/sales.pdf"},
    ],
}

TOOL_IMPLEMENTATIONS = {
    "read_pdf": read_pdf,
    "read_docx": read_docx,
    "read_pptx": read_pptx,
    "read_xlsx": read_xlsx,
    "write_docx": write_docx,
    "write_xlsx": write_xlsx,
    "write_pdf": write_pdf,
    "write_pptx": write_pptx,
    "convert_document": convert_document,
}

TOOL_INPUT_MODELS = {
    "read_pdf": ReadPdfInput,
    "read_docx": ReadDocxInput,
    "read_pptx": ReadPptxInput,
    "read_xlsx": ReadXlsxInput,
    "write_docx": WriteDocxInput,
    "write_xlsx": WriteXlsxInput,
    "write_pdf": WritePdfInput,
    "write_pptx": WritePptxInput,
    "convert_document": ConvertDocumentInput,
}


def _register_document_tools():
    """注册9个文档操作工具到DOCUMENT分类 — 小欧 2026-06-18"""

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
        logger.debug(
            f"[document_register] \u5df2\u6ce8\u518c\u5de5\u5177: {name}, "
            f"Pydantic\u6a21\u578b: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}\u4e2a"
        )


__all__ = [
    "_register_document_tools",
    "read_pdf",
    "read_docx",
    "read_pptx",
    "read_xlsx",
    "write_docx",
    "write_xlsx",
    "write_pdf",
    "write_pptx",
    "convert_document",
]
