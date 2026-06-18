# -*- coding: utf-8 -*-
"""
Document 工具参数 Schema 定义

职责:
定义 document 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict, Literal, Union


class ReadPdfInput(BaseModel):
    file_path: str = Field(..., description="PDF文件路径(.pdf)")
    pages: Optional[str] = Field(default=None, description="页码范围(如'1-3,5')")
    extract_tables: bool = Field(default=False, description="是否提取表格")


class ReadDocxInput(BaseModel):
    file_path: str = Field(..., description="Word文档路径(.docx)")
    extract_tables: bool = Field(default=False, description="是否提取表格")


class ReadPptxInput(BaseModel):
    file_path: str = Field(..., description="PPT文件路径(.pptx)")


class ReadXlsxInput(BaseModel):
    file_path: str = Field(..., description="Excel/CSV/TSV/JSON文件路径(.xlsx/.xls/.csv/.tsv/.json)")
    sheet_name: Optional[str] = Field(default=None, description="Excel工作表名(仅XLSX有效)")
    max_rows: int = Field(default=1000, ge=1, le=10000, description="最大读取行数")
    header: bool = Field(default=True, description="第一行是否为表头")
    encoding: str = Field(default="utf-8", description="文件编码(仅CSV有效)")
    delimiter: Optional[str] = Field(default=None, description="CSV分隔符(仅CSV有效)")


class WriteDocxInput(BaseModel):
    file_path: str = Field(..., description="输出Word文档路径(.docx)")
    content: Optional[str] = Field(default=None, description="正文内容")
    paragraphs: Optional[List[str]] = Field(default=None, description="段落列表")
    title: Optional[str] = Field(default=None, description="文档标题")
    table_data: Optional[List] = Field(default=None, description="表格数据二维数组")
    data: Optional[Union[Dict[str, Any], List]] = Field(default=None, description="结构化内容")


class WriteXlsxInput(BaseModel):
    file_path: str = Field(..., description="输出Excel路径(.xlsx)")
    data: Optional[Union[Dict[str, Any], List]] = Field(default=None, description="写入的数据。dict={\"headers\":[\"列1\"],\"rows\":[[\"a\"]]}或list自动推断headers")
    sheet_name: str = Field(default="Sheet1", description="工作表名")


class WritePdfInput(BaseModel):
    file_path: str = Field(..., description="输出PDF路径(.pdf)")
    title: Optional[str] = Field(default=None, description="文档标题")
    content: Optional[str] = Field(default=None, description="正文内容")
    paragraphs: Optional[List[str]] = Field(default=None, description="段落列表")
    table_data: Optional[List] = Field(default=None, description="表格数据二维数组")


class WritePptxInput(BaseModel):
    file_path: str = Field(..., description="输出PPT路径(.pptx)")
    title: Optional[str] = Field(default=None, description="文档标题")
    slides: Optional[List[Dict[str, str]]] = Field(default=None, description="幻灯片列表")


class ConvertDocumentInput(BaseModel):
    input_path: str = Field(..., description="输入文件路径。支持.docx/.doc/.xlsx/.xls/.pptx/.ppt/.odt/.ods格式")
    output_format: Literal["pdf"] = Field(default="pdf", description="目标格式。可选值:pdf")
    output_path: Optional[str] = Field(default=None, description="输出文件保存路径,含文件名和扩展名。如 D:/output.pdf。不填则自动在原文件同目录生成同名文件,扩展名为目标格式")
