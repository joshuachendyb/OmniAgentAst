# -*- coding: utf-8 -*-
"""
Document 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.3节 Tool 80-82 定义

职责：
定义 document 分类的工具参数 Pydantic 模型。

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Any


class ReadPdfInput(BaseModel):
    """read_pdf 工具的输入参数（Tool 80）"""
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
    """read_docx 工具的输入参数（Tool 81）"""
    file_path: str = Field(
        ...,
        description="Word 文件路径。如 D:/documents/report.docx"
    )
    extract_tables: Optional[bool] = Field(
        default=False,
        description="是否提取表格（可选）。Agent根据query判断，如\"提取表格\"→true"
    )


class ReadXlsxInput(BaseModel):
    """read_xlsx 工具的输入参数（Tool 82）"""
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
        description="最大读取行数（可选）。Agent根据文件大小自动调整，大文件→500，小文件→2000"
    )
    header: Optional[bool] = Field(
        default=True,
        description="第一行是否为表头（可选）。默认 True"
    )
    index_col: Optional[bool] = Field(
        default=False,
        description="第一列是否为索引（可选）。默认 False"
    )


class WriteDocxInput(BaseModel):
    """write_docx 工具的输入参数 - 小沈 2026-05-04"""
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
    """write_xlsx 工具的输入参数 - 小沈 2026-05-04"""
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
        description="工作表名称"
    )


class ReadPptxInput(BaseModel):
    """read_pptx 工具的输入参数 - 小沈 2026-05-04"""
    file_path: str = Field(
        ...,
        description="PPT 文件路径。如 D:/documents/presentation.pptx"
    )
    extract_notes: Optional[bool] = Field(
        default=False,
        description="是否提取演讲备注"
    )
