# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 复核schema docstring规范,WriteDocx/WritePdf保留既有docstring,其余工具默认行为均已在Field中体现,无需新增
# 2026-07-21 - 小欧 - 补schema参数对齐(修BUG):
#   1. ReadPdfInput 补 page/pages 字段
#   2. ReadDocxInput 补 offset/limit/tail 字段
#   3. ReadPptxInput 补 slide 字段
#   说明: 工具函数已在5259ef2ed新增上述
#   翻页参数,但schema漏更新致LLM看不到
#   且tool_retry_engine校验拒收(非法参数)
# 2026-07-21 - 小欧 - 修pages字段类型不安全(KISS-DIRECT): Optional[Any]→Optional[Union[int,str,List[int]]], 与运行时_parse_pdf_pages接受类型对齐, Pydantic层即拦截非法类型
# 2026-07-21 - 小欧 - ReadDocxInput.limit description 引用 OBS_READTEXT_MAX_ROWS 常量, 加建议不超过上限说明
# 2026-07-21 - 小欧 - 入参即信任: ReadDocxInput.limit 加 ge=1,le=1000, 支撑LLM指定1000以内段落数
# 2026-07-25 - 小欧 - description去冗余+Field精简
# 2026-07-26 - 小沈 - 欧阳报告: WriteDocxInput/WritePdfInput validator放宽, content+table_data都空时默认""而非报错
# 2026-07-26 - 小沈 - Bug #6 DRY: 抽取_DocContentOrTableMixin消除WriteDocxInput/WritePdfInput的_check_content_or_table重复代码
# 2026-07-28 - 小欧 - description精确化: write_pptx.path/write_docx.path/write_xlsx.path/write_pdf.path 全部加"必填"标注
# 2026-07-31 - 小欧 - ReadPdfInput 补 page/pages 互斥校验(model_validator): 二者同时指定时报 ValueError, 与运行时逻辑对齐(Pydantic 层即拦截非法组合); 移除未使用 Literal 导入
# 2026-08-07 - 小欧 - WriteXlsxInput 新增 append_mode 字段(追加模式): True=文件已存在时末尾追加, False=默认覆盖; 与 write_xlsx 实现层同步 — 小欧 2026-08-07
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

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Any, List, Dict, Union  # 2026-07-31 小欧: 移除未使用 Literal

class ReadPdfInput(BaseModel):
    path: str = Field(..., description="文件名+路径(.pdf)")
    page: Optional[int] = Field(default=None, description="1-based; 与pages互斥，二选一；不传则读取默认前几页")
    pages: Optional[Union[int, str, List[int]]] = Field(default=None, description="1-based; 与page互斥")

    @model_validator(mode="after")
    def _check_page_pages_mutually_exclusive(self):
        if self.page is not None and self.pages is not None:
            raise ValueError("page 和 pages 互斥，不能同时指定")
        return self


class ReadDocxInput(BaseModel):
    path: str = Field(..., description="文件名+路径(.docx) — 不支持.doc格式")
    offset: Optional[int] = Field(default=None, description="1-based; 须配合limit使用")
    limit: Optional[int] = Field(default=None, ge=1, le=1000, description="与tail互斥")
    tail: Optional[int] = Field(default=None, description="与offset/limit互斥")


class ReadPptxInput(BaseModel):
    path: str = Field(..., description="文件名+路径(.pptx) — 不支持.ppt格式")
    slide: Optional[int] = Field(default=None, description="1-based; 不传则读取全部幻灯片")


class ReadXlsxInput(BaseModel):
    path: str = Field(..., description="文件名+路径(.xlsx/.csv) —不支持.xls格式")
    sheet_name: Optional[str] = Field(
        default=None,
        description="工作表名（仅.xlsx格式有效）。None=读取所有工作表，指定名称=读取单个工作表。CSV/XLS格式忽略此参数"
    )



class _DocContentOrTableMixin:
    """content/table_data互斥校验 — DRY (WriteDocxInput/WritePdfInput共用) — 小沈 2026-07-26"""
    @model_validator(mode="after")
    def _check_content_or_table(self):
        if self.content and self.table_data:
            raise ValueError("content和table_data互斥,只能传入其中一个")
        if not self.content and not self.table_data:
            self.content = ""  # 都为空时默认空文档(欧阳报告) — 小沈 2026-07-26
        return self


class WriteDocxInput(_DocContentOrTableMixin, BaseModel):
    """content和table_data互斥,只能传入其中一个"""
    path: str = Field(..., min_length=1, description="输出文件完整路径(.docx),必填")
    title: Optional[str] = Field(default=None, description="文档标题（显示在文档开头）")
    content: Optional[str] = Field(
        default=None,
        description="""正文内容(Markdown格式字符串)。语法说明：
- 标题：# 一级标题  ## 二级标题  ### 三级标题  #### 四级标题  ##### 五级标题
- 段落：直接写文本，空行分隔段落
- 无序列表：- 列表项  或  * 列表项
- 有序列表：1. 第一项  2. 第二项  （数字会自动重新编号）
- 表格：| 列1 | 列2 |  （Markdown表格语法，第一行为表头）

与table_data互斥,严禁同时传入"""
    )
    table_data: Optional[List[List[str]]] = Field(
        default=None,
        description="""表格数据(二维数组)。格式：[["列1", "列2"], ["A", "B"], ["C", "D"]]
第一行为表头，后续为数据行。用于纯表格文档。与content互斥"""
    )


class WriteXlsxInput(BaseModel):
    path: str = Field(..., description="输出文件完整路径(.xlsx),必填")
    data: Optional[List[Dict[str, Any]]] = Field(
        default=None, 
        description="""写入的数据。对象数组格式:[{"列1":"a","列2":"b"},{"列1":"c","列2":"d"}]
- key做列名，value做单元格内容
- 自动合并所有对象的key作为表头（列顺序按首次出现顺序）
- 不同对象的key可以不同，缺失的列自动填空"""
    )
    sheet_name: str = Field(default="Sheet1", description="工作表名")
    # append_mode 追加模式 — 小欧 2026-08-07
    append_mode: bool = Field(
        default=False,
        description="""追加模式。
- True: 文件已存在时在末尾追加行（保留已有内容/格式）；不存在则新建
- False: 默认整篇覆盖
【注意】追加时 data 的列名需与已有表头一致，不一致将返回错误"""
    )


class WritePdfInput(_DocContentOrTableMixin, BaseModel):
    """content和table_data互斥,只能传入其中一个"""
    path: str = Field(..., min_length=1, description="输出文件完整路径(.pdf),必填")
    title: Optional[str] = Field(default=None, description="文档标题（显示在文档开头）")
    content: Optional[str] = Field(
        default=None,
        description="""正文内容(Markdown格式字符串)。语法说明：
- 标题：# 一级标题  ## 二级标题  ### 三级标题  #### 四级标题
- 段落：直接写文本，空行分隔段落
- 无序列表：- 列表项  或  * 列表项
- 有序列表：1. 第一项  2. 第二项  （数字会自动重新编号）
- 表格：| 列1 | 列2 |  （Markdown表格语法，第一行为表头）

与table_data互斥,严禁同时传入"""
    )
    table_data: Optional[List[List[str]]] = Field(
        default=None,
        description="""表格数据(二维数组)。格式：[["列1", "列2"], ["A", "B"], ["C", "D"]]
第一行为表头，后续为数据行。用于纯表格文档。与content互斥"""
    )


_SLIDE_DESC = """幻灯片列表。每项Dict包含：
- title（必填）：标题
- subtitle（可选）：副标题（仅封面页type=0或"cover"时显示）
- type（可选）：布局类型，0/"cover"=封面页，1/"content"=内容页，2/"two"=两栏页，默认1
- content（可选）：正文内容，支持3种格式：
  1. 字符串：纯文本
  2. 列表：["段落1", "段落2"] 或 [{"type":"paragraph","text":"段落"}, {"type":"bullets","items":["要点1","要点2"]}]
  3. 字典：{"type":"bullets","items":["要点1","要点2"]}
- tables（可选）：表格列表，每个表格为二维数组 [["列1","列2"],["A","B"]]"""
class WritePptxInput(BaseModel):
    path: str = Field(..., description="输出文件完整路径(.pptx),必填")
    # slides允许List[Dict]或JSON字符串(LLM常把list序列化为字符串传入) — 小欧 2026-07-12 修问题4反序列化
    slides: Optional[Union[List[Dict], str]] = Field(default=None, description=_SLIDE_DESC)


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
