# -*- coding: utf-8 -*-
"""
Document 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【2026-05-18 小沈】删除旧Schema（ReadPdfInput等8个废弃模型）

职责：
定义 document 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict


class ReadDocumentInput(BaseModel):
    """read_document 工具的输入参数 — 小健 2026-05-18"""
    file_path: str = Field(..., description="文档路径。支持 .pdf/.doc/.docx/.xlsx/.xls/.pptx/.csv/.tsv")
    pages: Optional[str] = Field(default=None, description="PDF页码范围（如'1-3,5'，仅PDF有效）")
    extract_tables: bool = Field(default=False, description="是否提取表格（PDF/DOCX有效）")
    extract_images: bool = Field(default=False, description="是否提取图片（仅PDF有效）")
    extract_notes: bool = Field(default=False, description="是否提取演讲备注（仅PPTX有效）")
    sheet_name: Optional[str] = Field(default=None, description="Excel工作表名（仅XLSX有效）")
    max_rows: int = Field(default=1000, ge=1, le=10000, description="最大读取行数（XLSX/CSV有效）")
    header: bool = Field(default=True, description="第一行是否为表头（XLSX/CSV有效）")
    use_pandas: bool = Field(default=False, description="是否使用pandas读取CSV")
    encoding: str = Field(default="utf-8", description="文件编码（仅CSV有效）")
    delimiter: str = Field(default=",", description="CSV分隔符（仅CSV有效）")


class WriteDocumentInput(BaseModel):
    """write_document 工具的输入参数 — 小健 2026-05-18"""
    file_path: str = Field(..., description="输出路径。支持 .docx/.xlsx/.pdf/.pptx")
    content: Optional[str] = Field(default=None, description="正文内容（DOCX/PDF有效）")
    paragraphs: Optional[List[str]] = Field(default=None, description="段落列表（DOCX/PDF有效）")
    title: Optional[str] = Field(default=None, description="文档标题（DOCX/PDF/PPTX有效）")
    table_data: Optional[List] = Field(default=None, description="表格数据二维数组（DOCX/PDF有效）")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Excel数据{headers, rows}（XLSX有效）")
    sheet_name: str = Field(default="Sheet1", description="Excel工作表名（XLSX有效）")
    slides: Optional[List[Dict[str, str]]] = Field(default=None, description="PPT幻灯片列表（PPTX有效）")


class ConvertDocumentInput(BaseModel):
    """convert_document 工具的输入参数 - 小沈 2026-05-05"""
    input_path: str = Field(..., description="输入文件路径")
    output_format: str = Field(default="pdf", description="目标格式。可选值：pdf")
    output_path: Optional[str] = Field(default=None, description="输出文件路径")
