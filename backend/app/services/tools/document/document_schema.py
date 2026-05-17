# -*- coding: utf-8 -*-
"""
Document 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.3节 Tool 80-82 定义
【重构 2026-05-18 小健】新增 ReadDocumentInput/WriteDocumentInput，旧Schema标注弃用

职责：
定义 document 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict


class ReadDocumentInput(BaseModel):
    """read_document 工具的输入参数 — 小健 2026-05-18
    合并 read_pdf + read_docx + read_pptx + read_xlsx
    """
    file_path: str = Field(..., description="文档路径。支持 .pdf/.docx/.xlsx/.xls/.pptx。Agent无需判断格式，工具按后缀自动选择解析器")
    pages: Optional[str] = Field(default=None, description="PDF页码范围（如'1-3,5'，仅PDF有效）")
    extract_tables: bool = Field(default=False, description="是否提取表格（PDF/DOCX有效）")
    extract_images: bool = Field(default=False, description="是否提取图片（仅PDF有效）")
    extract_notes: bool = Field(default=False, description="是否提取演讲备注（仅PPTX有效）")
    sheet_name: Optional[str] = Field(default=None, description="Excel工作表名（仅XLSX有效）")
    max_rows: int = Field(default=1000, ge=1, le=10000, description="最大读取行数（仅XLSX有效）")
    header: bool = Field(default=True, description="第一行是否为表头（仅XLSX有效）")


class WriteDocumentInput(BaseModel):
    """write_document 工具的输入参数 — 小健 2026-05-18
    合并 write_docx + write_xlsx + write_pdf + write_pptx
    """
    file_path: str = Field(..., description="输出路径。支持 .docx/.xlsx/.pdf/.pptx")
    content: Optional[str] = Field(default=None, description="正文内容（DOCX/PDF有效）")
    paragraphs: Optional[List[str]] = Field(default=None, description="段落列表（DOCX/PDF有效）")
    title: Optional[str] = Field(default=None, description="文档标题（DOCX/PDF/PPTX有效）")
    table_data: Optional[List] = Field(default=None, description="表格数据二维数组（DOCX/PDF有效）")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Excel数据{headers, rows}（XLSX有效）")
    sheet_name: str = Field(default="Sheet1", description="Excel工作表名（XLSX有效）")
    slides: Optional[List[Dict[str, str]]] = Field(default=None, description="PPT幻灯片列表（PPTX有效）")


# ============================================================
# 旧Schema（保留，标注弃用）— 小健 2026-05-18
# ============================================================

class ReadPdfInput(BaseModel):
    """【已弃用】请使用 ReadDocumentInput 代替 - 小健 2026-05-18
    read_pdf 工具的输入参数（Tool 80）
    """
    file_path: str = Field(
        ...,
        description="PDF 文件路径。如 D:/documents/report.pdf"
    )
    pages: Optional[str] = Field(
        default=None,
        description="要读取的页面（可选）。如\"1-5\"或\"1,3,5\"，Agent根据query推断"
    )
    extract_images: Optional[bool] = Field(
        default=False,
        description="是否提取图片（可选）。Agent根据query判断，如\"提取图片\"→true"
    )
    extract_tables: Optional[bool] = Field(
        default=False,
        description="是否提取表格（可选）。Agent根据query判断，如\"提取表格\"→true"
    )


class ReadDocxInput(BaseModel):
    """【已弃用】请使用 ReadDocumentInput 代替 - 小健 2026-05-18
    read_docx 工具的输入参数（Tool 81）
    """
    file_path: str = Field(
        ...,
        description="Word 文件路径。如 D:/documents/report.docx"
    )
    extract_tables: Optional[bool] = Field(
        default=False,
        description="是否提取表格（可选）。Agent根据query判断，如\"提取表格\"→true"
    )


class ReadXlsxInput(BaseModel):
    """【已弃用】请使用 ReadDocumentInput 代替 - 小健 2026-05-18
    read_xlsx 工具的输入参数（Tool 82）
    """
    file_path: str = Field(
        ...,
        description="Excel 文件路径。如 D:/data/report.xlsx"
    )
    sheet_name: Optional[str] = Field(
        default=None,
        description="工作表名称（可选）。Agent根据query推断，如\"销售表\"或\"Sheet2\"自动切换，支持中文工作表名"
    )
    max_rows: Optional[int] = Field(
        default=1000,
        description="最大读取行数。Agent根据文件大小自动调整（大文件500，小文件2000）。默认为1000"
    )
    header: Optional[bool] = Field(
        default=True,
        description="第一行是否为表头。默认为True"
    )


class WriteDocxInput(BaseModel):
    """【已弃用】请使用 WriteDocumentInput 代替 - 小健 2026-05-18
    write_docx 工具的输入参数 - 小沈 2026-05-04
    """
    file_path: str = Field(
        ...,
        description="输出文件路径。如 D:/output/report.docx"
    )
    content: Optional[str] = Field(
        default=None,
        description="正文内容"
    )
    paragraphs: Optional[list] = Field(
        default=None,
        description="段落列表。如 [\"第一段\", \"第二段\"]"
    )
    title: Optional[str] = Field(
        default=None,
        description="文档标题"
    )
    table_data: Optional[list] = Field(
        default=None,
        description="表格数据二维数组"
    )


class WriteXlsxInput(BaseModel):
    """【已弃用】请使用 WriteDocumentInput 代替 - 小健 2026-05-18
    write_xlsx 工具的输入参数 - 小沈 2026-05-04
    """
    file_path: str = Field(
        ...,
        description="输出文件路径。如 D:/output/data.xlsx"
    )
    data: dict = Field(
        ...,
        description="数据字典，包含 headers 和 rows"
    )
    sheet_name: Optional[str] = Field(
        default="Sheet1",
        description="工作表名称。默认为Sheet1"
    )


class ReadPptxInput(BaseModel):
    """【已弃用】请使用 ReadDocumentInput 代替 - 小健 2026-05-18
    read_pptx 工具的输入参数 - 小沈 2026-05-04
    """
    file_path: str = Field(
        ...,
        description="PPT 文件路径。如 D:/documents/presentation.pptx"
    )
    extract_notes: Optional[bool] = Field(
        default=False,
        description="是否提取演讲备注"
    )


class WritePdfInput(BaseModel):
    """【已弃用】请使用 WriteDocumentInput 代替 - 小健 2026-05-18
    write_pdf 工具的输入参数 - 小沈 2026-05-05
    """
    file_path: str = Field(
        ...,
        description="输出PDF文件路径。如 D:/output/report.pdf"
    )
    title: Optional[str] = Field(
        default=None,
        description="文档标题"
    )
    content: Optional[str] = Field(
        default=None,
        description="正文内容（纯文本）"
    )
    paragraphs: Optional[list] = Field(
        default=None,
        description="段落列表。如 [\"第一段\", \"第二段\"]"
    )
    table_data: Optional[list] = Field(
        default=None,
        description="表格数据二维数组。如 [[\"列1\", \"列2\"], [\"值1\", \"值2\"]]"
    )


class ConvertDocumentInput(BaseModel):
    """convert_document 工具的输入参数 - 小沈 2026-05-05"""
    input_path: str = Field(
        ...,
        description="输入文件路径。如 D:/documents/report.docx"
    )
    output_format: str = Field(
        default="pdf",
        description="目标格式。可选值：pdf。默认为pdf"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="输出文件路径。默认为与输入同目录（扩展名替换）"
    )


class WritePptxInput(BaseModel):
    """【已弃用】请使用 WriteDocumentInput 代替 - 小健 2026-05-18
    write_pptx 工具的输入参数 - 小沈 2026-05-05
    """
    file_path: str = Field(
        ...,
        description="输出PPT文件路径。如 D:/output/presentation.pptx"
    )
    title: Optional[str] = Field(
        default=None,
        description="演示文稿标题"
    )
    slides: Optional[list] = Field(
        default=None,
        description="幻灯片内容列表。每个元素是一个字典，包含 title 和 content"
    )
