# -*- coding: utf-8 -*-
"""
Document Schema - 文档工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容

【2026-06-20 小健】删除非document的Schema(QuerySqlInput等6个),已在dataanalysis_schema.py中
"""

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict, Literal, Union

class ReadPdfInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.pdf)")


class ReadDocxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.docx/.doc)")


class ReadPptxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.pptx)")


class ReadXlsxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.xlsx/.csv/.xls)")


_PARAGRAPHS_DESC = "正文内容。3种格式: str=纯文本, list=[str|dict,...]混合内容, dict={\"title\":\"标题\",\"content\":[...]}. dict元素支持:\ntype=heading/h1~h5(标题),type=paragraph(段落),type=table(表格,需rows字段)"


class WriteDocxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.docx)")
    title: Optional[str] = Field(default=None, description="文档标题")
    paragraphs: Optional[Union[str, List, Dict]] = Field(default=None, description=_PARAGRAPHS_DESC)


class WriteXlsxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.xlsx)")
    data: Optional[Union[Dict[str, Any], List]] = Field(default=None, description="写入的数据。支持3格式: dict格式{\"headers\":[\"列1\"],\"rows\":[[\"a\"]]}, list of list格式[[\"列1\",\"列2\"],[\"a\",\"b\"]](首行做headers), list of dict格式[{\"列1\":\"a\"}](key做headers)")
    sheet_name: str = Field(default="Sheet1", description="工作表名")


class WritePdfInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.pdf)")
    title: Optional[str] = Field(default=None, description="文档标题")
    paragraphs: Optional[Union[str, List, Dict]] = Field(default=None, description=_PARAGRAPHS_DESC)


_SLIDE_DESC = "幻灯片列表。每项Dict支持: type(0=封面/1=内容/2=两栏), title(标题), subtitle(副标题,仅封面), content(str纯文本或list混合内容,支持str段落和dict type=paragraph/bullets), tables(独立表格List[List[List]])"
class WritePptxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.pptx)")
    slides: Optional[List[Dict]] = Field(default=None, description=_SLIDE_DESC)


__all__ = [
    "ReadPdfInput",
    "ReadDocxInput",
    "ReadPptxInput",
    "ReadXlsxInput",
    "WriteDocxInput",
    "WriteXlsxInput",
    "WritePdfInput",
    "WritePptxInput",
]
