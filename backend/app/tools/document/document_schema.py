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
    sheet_name: Optional[str] = Field(
        default=None,
        description="工作表名（仅.xlsx格式有效）。None=读取所有工作表，指定名称=读取单个工作表。CSV/XLS格式忽略此参数"
    )


_PARAGRAPHS_DESC = "正文内容。3种格式: str=纯文本, list=[str|dict,...]混合内容, dict={\"title\":\"标题\",\"content\":[...]}. dict元素支持:\ntype=heading/h1~h5(标题),type=paragraph(段落),type=table(表格,需rows字段)"


class WriteDocxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.docx)")
    title: Optional[str] = Field(default=None, description="文档标题（显示在文档开头）")
    content: Optional[str] = Field(
        default=None, 
        description="""正文内容(Markdown格式字符串)。语法说明：
- 标题：# 一级标题  ## 二级标题  ### 三级标题  #### 四级标题  ##### 五级标题
- 段落：直接写文本，空行分隔段落
- 无序列表：- 列表项  或  * 列表项
- 有序列表：1. 第一项  2. 第二项  （数字会自动重新编号）
- 表格：| 列1 | 列2 |  （Markdown表格语法，第一行为表头）
示例：\"# 报告标题\\n\\n第一段内容\\n\\n## 数据表格\\n\\n| 项目 | 数值 |\\n|------|------|\\n| A | 100 |\\n\\n## 章节\\n\\n- 要点1\\n- 要点2\"

与table_data互斥，优先使用content"""
    )
    table_data: Optional[List[List[str]]] = Field(
        default=None,
        description="""表格数据(二维数组)。格式：[["列1", "列2"], ["A", "B"], ["C", "D"]]
第一行为表头，后续为数据行。用于纯表格文档，与content互斥。如果content有值，此参数忽略"""
    )


class WriteXlsxInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.xlsx)")
    data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="""写入的数据。对象数组格式:[{"列1":"a","列2":"b"},{"列1":"c","列2":"d"}]
- key做列名，value做单元格内容
- 自动合并所有对象的key作为表头（列顺序按首次出现顺序）
- 不同对象的key可以不同，缺失的列自动填空

示例：
- [{"姓名":"张三","年龄":25},{"姓名":"李四","年龄":30}] → 表头:姓名,年龄 | 数据:张三,25 | 李四,30
- [{"A":"1"},{"B":"2"}] → 表头:A,B | 数据:1,空 | 空,2"""
    )
    sheet_name: str = Field(default="Sheet1", description="工作表名")


class WritePdfInput(BaseModel):
    file_name: str = Field(..., description="文件名+路径(.pdf)")
    title: Optional[str] = Field(default=None, description="文档标题（显示在文档开头）")
    content: Optional[str] = Field(
        default=None, 
        description="""正文内容(Markdown格式字符串)。语法说明：
- 标题：# 一级标题  ## 二级标题  ### 三级标题  #### 四级标题
- 段落：直接写文本，空行分隔段落
- 无序列表：- 列表项  或  * 列表项
- 有序列表：1. 第一项  2. 第二项  （数字会自动重新编号）
- 表格：| 列1 | 列2 |  （Markdown表格语法，第一行为表头）
示例：\"# 报告标题\\n\\n第一段内容\\n\\n## 数据表格\\n\\n| 项目 | 数值 |\\n|------|------|\\n| A | 100 |\\n\\n## 章节\\n\\n- 要点1\\n- 要点2\"

与table_data互斥，优先使用content"""
    )
    table_data: Optional[List[List[str]]] = Field(
        default=None,
        description="""表格数据(二维数组)。格式：[["列1", "列2"], ["A", "B"], ["C", "D"]]
第一行为表头，后续为数据行。用于纯表格文档，与content互斥。如果content有值，此参数忽略"""
    )


_SLIDE_DESC = """幻灯片列表。每项Dict包含：
- title（必填）：标题
- subtitle（可选）：副标题（仅封面页type=0或"cover"时显示）
- type（可选）：布局类型，0/"cover"=封面页，1/"content"=内容页，2/"two"=两栏页，默认1
- content（可选）：正文内容，支持3种格式：
  1. 字符串：纯文本
  2. 列表：["段落1", "段落2"] 或 [{"type":"paragraph","text":"段落"}, {"type":"bullets","items":["要点1","要点2"]}]
  3. 字典：{"type":"bullets","items":["要点1","要点2"]}
- tables（可选）：表格列表，每个表格为二维数组 [["列1","列2"],["A","B"]]

示例：
[
  {"type":"cover","title":"封面","subtitle":"副标题"},
  {"title":"目录","content":["一、背景","二、方案","三、总结"]},
  {"title":"数据","tables":[[["项目","数值"],["A","100"],["B","200"]]]}
]"""
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
