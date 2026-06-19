# -*- coding: utf-8 -*-
"""
Document Register - 文档操作工具注册点（仅DOCUMENT分类）

【2026-06-18 小欧】DATAANALYSIS 6个工具已迁出到 dataanalysis/ 独立目录
【2026-06-18 小健】添加TOOL_DEPENDENCIES常量管理工具依赖

【工具列表】(共9个) → DOCUMENT分类:
1. read_pdf - 读取PDF文档 (依赖: pdfplumber)
2. read_docx - 读取Word文档 (依赖: python-docx)
3. read_pptx - 读取PPT文档 (依赖: python-pptx)
4. read_xlsx - 读取Excel文档 (依赖: pandas, openpyxl)
5. write_docx - 写入Word文档 (依赖: python-docx)
6. write_xlsx - 写入Excel文档 (依赖: pandas, openpyxl)
7. write_pdf - 写入PDF文档 (依赖: reportlab, pdfplumber)
8. write_pptx - 写入PPT文档 (依赖: python-pptx)

创建时间: 2026-05-02
更新时间: 2026-06-18 小健
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

# 文档工具依赖配置 — 小健 2026-06-18
# 注意：pip包名与import名不一致时必须用字典格式指定import_name
TOOL_DEPENDENCIES = {
    "read_pdf": ["pdfplumber"],
    "read_docx": [
        {"import_name": "docx", "pip_package": "python-docx"},
    ],
    "read_pptx": [{"import_name": "pptx", "pip_package": "python-pptx"}],
    "read_xlsx": [
        "pandas",
        "openpyxl",
        "xlrd",
    ],
    "write_docx": [{"import_name": "docx", "pip_package": "python-docx"}],
    "write_xlsx": ["pandas", "openpyxl"],
    "write_pdf": ["reportlab", "pdfplumber"],
    "write_pptx": [{"import_name": "pptx", "pip_package": "python-pptx"}],
}


from app.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadPptxInput,
    ReadXlsxInput,
    WriteDocxInput,
    WriteXlsxInput,
    WritePdfInput,
    WritePptxInput,
)

from app.tools.document.document_tools import (
    read_pdf,
    read_docx,
    read_pptx,
    read_xlsx,
    write_docx,
    write_xlsx,
    write_pdf,
    write_pptx,
)

DESCRIPTIONS = {
    "read_pdf": """读取PDF(.pdf)文件内容。自动提取文本、表格和图片。适用场景:需要读取PDF文档内容时使用。""",
    "read_docx": """读取Word(.docx/.doc)文档内容。自动提取文本和表格。适用场景:需要读取Word文档内容时使用。""",
    "read_pptx": """读取PPT(.pptx)演示文稿内容。自动提取每页文本和备注。适用场景:需要读取PPT内容时使用。""",
    "read_xlsx": """读取Excel(.xls/.xlsx/.csv)文件。自动检测编码和分隔符,自动识别表头。适用场景:需要读取表格数据时使用。""",
    "write_docx": """写入Word(.docx)文档。支持3参数: file_name/title/paragraphs。paragraphs支持3格式: str=纯文本, list=[str|dict,...]混合内容(str=段落,dict支持type=heading/h1~h5/paragraph/table), dict={"title":"标题","content":[...]}结构化文档。适用场景:需要生成Word报告、导出文档时使用。""",
    "write_xlsx": """写入Excel(.xlsx)文件。data参数支持dict(headers+rows)或list自动推断headers。可指定工作表名。适用场景:需要导出数据到Excel表格时使用。""",
    "write_pdf": """写入PDF(.pdf)文件。支持3参数: file_name/title/paragraphs。paragraphs支持3格式: str=纯文本, list=[str|dict,...]混合内容(str=段落,dict支持type=heading/h1~h5/paragraph/table), dict={"title":"标题","content":[...]}结构化文档。适用场景:需要生成PDF报告、归档文档时使用。""",
    "write_pptx": """写入PPT(.pptx)演示文稿。支持2参数: file_name/slides。slides列表每项支持: type(0=封面/1=内容/2=两栏), title(标题), subtitle(副标题仅封面), content(str纯文本或list混合内容支持str段落和dict type=paragraph/bullets), tables(独立表格)。适用场景:需要生成PPT演示文稿时使用。""",

}

EXAMPLES = {
    "read_pdf": [
        {"file_name": "D:/documents/report.pdf"},
    ],
    "read_docx": [
        {"file_name": "D:/documents/report.docx"},
        {"file_name": "D:/documents/report.doc"},
    ],
    "read_pptx": [
        {"file_name": "D:/documents/presentation.pptx"},
    ],
    "read_xlsx": [
        {"file_name": "D:/data/sales.xlsx"},
        {"file_name": "D:/data/sales.xls"},
        {"file_name": "D:/data/sales.csv"},
    ],
    "write_docx": [
        {"file_name": "D:/output/report.docx", "title": "\u6d4b\u8bd5\u62a5\u544a", "paragraphs": "\u8fd9\u662f\u6d4b\u8bd5\u5185\u5bb9"},
        {"file_name": "D:/output/report_structured.docx", "paragraphs": {"title": "\u7ed3\u6784\u5316\u62a5\u544a", "content": [{"type": "h1", "text": "\u7b2c\u4e00\u7ae0"}, {"type": "paragraph", "text": "\u6b63\u6587\u5185\u5bb9"}, {"type": "table", "rows": [["\u52171", "\u52172"], ["a", "b"]]}]}},
    ],
    "write_xlsx": [
        {"file_name": "D:/output/data.xlsx", "data": {"headers": ["\u59d3\u540d", "\u5e74\u9f84"], "rows": [["\u5f20\u4e09", 25], ["\u674e\u56db", 30]]}},
    ],
    "write_pdf": [
        {"file_name": "D:/output/report.pdf", "title": "\u6d4b\u8bd5\u62a5\u544a", "paragraphs": "\u8fd9\u662f\u62a5\u544a\u5185\u5bb9"},
        {"file_name": "D:/output/structured_report.pdf", "paragraphs": [{"type": "h1", "text": "\u7b2c\u4e00\u7ae0"}, "\u6b63\u6587\u5185\u5bb9"]},
    ],
    "write_pptx": [
        {"file_name": "D:/output/cover.pptx", "slides": [{"type": "cover", "title": "\u9879\u76ee\u6c47\u62a5", "subtitle": "\u5c0f\u7ec4"}]},
        {"file_name": "D:/output/slides.pptx", "slides": [{"title": "\u4e1a\u7ee9\u6982\u89c8", "content": ["\u672c\u5b63\u5ea6\u9500\u552e\u989d\u589e\u957f20%", {"type": "bullets", "items": ["\u652f\u51fa\u63a7\u5236", "\u5ba2\u6237\u589e\u957f"]}]}]},
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
}


def _register_document_tools():
    """注册8个文档操作工具到DOCUMENT分类 — 小欧 2026-06-19"""
    
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
            dependencies=TOOL_DEPENDENCIES.get(name, []),
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
]
