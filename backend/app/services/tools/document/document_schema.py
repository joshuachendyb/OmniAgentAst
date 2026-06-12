# -*- coding: utf-8 -*-
"""
Document 工具参数 Schema 定义

职责:
定义 document 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict, Literal, Union


class ReadDocumentInput(BaseModel):
    file_path: str = Field(..., description="文档路径。仅支持: .pdf/.docx/.xlsx/.pptx/.csv/.tsv/.json;旧版 .doc/.xls 自动转换为PDF后读取。⚠️ 纯文本(.txt/.py/.json/.md等)请使用 read_text_file 工具")
    pages: Optional[str] = Field(default=None, description="PDF页码范围(如'1-3,5',仅PDF有效)")
    extract_tables: bool = Field(default=False, description="是否提取表格(PDF/DOCX有效)")
    sheet_name: Optional[str] = Field(default=None, description="Excel工作表名(仅XLSX有效)")
    max_rows: int = Field(default=1000, ge=1, le=10000, description="最大读取行数(XLSX/CSV有效)")
    header: bool = Field(default=True, description="第一行是否为表头(XLSX/CSV有效)")
    encoding: str = Field(default="utf-8", description="文件编码(仅CSV有效)")
    delimiter: Optional[str] = Field(default=None, description="CSV分隔符(仅CSV有效,None=自动选择逗号)")


class WriteDocumentInput(BaseModel):
    file_path: str = Field(..., description="输出路径。仅支持办公格式: .docx/.xlsx/.pdf/.pptx。⚠️ 不支持 .txt!写入文本文件请使用 write_text_file 工具")
    content: Optional[str] = Field(default=None, description="正文内容(DOCX/PDF有效)")
    paragraphs: Optional[List[str]] = Field(default=None, description="段落列表(DOCX/PDF有效)")
    title: Optional[str] = Field(default=None, description="文档标题(DOCX/PDF/PPTX有效)")
    table_data: Optional[List] = Field(default=None, description="表格数据二维数组(DOCX/PDF有效)")
    data: Optional[Union[Dict[str, Any], List]] = Field(default=None, description="写入的数据。XLSX格式: dict={\"headers\": [\"列1\",\"列2\"], \"rows\": [[\"a\",\"b\"]]}或list=[[\"a\",\"b\"]]自动推断headers;DOCX格式: {\"title\": \"标题\", \"content\": [{\"type\": \"paragraph\", \"text\": \"段落内容\"}]};PDF暂不支持写入")
    sheet_name: str = Field(default="Sheet1", description="Excel工作表名(XLSX有效)")
    slides: Optional[List[Dict[str, str]]] = Field(default=None, description="PPT幻灯片列表(PPTX有效)")


class ConvertDocumentInput(BaseModel):
    input_path: str = Field(..., description="输入文件路径。支持.docx/.doc/.xlsx/.xls/.pptx/.ppt/.odt/.ods格式")
    output_format: Literal["pdf"] = Field(default="pdf", description="目标格式。可选值:pdf")
    output_path: Optional[str] = Field(default=None, description="输出文件保存路径,含文件名和扩展名。如 D:/output.pdf。不填则自动在原文件同目录生成同名文件,扩展名为目标格式")
