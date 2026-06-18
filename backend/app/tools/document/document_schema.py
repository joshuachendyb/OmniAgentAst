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
"""
# Merged schema - 小欧 2026-06-18

from pydantic import BaseModel, Field
from typing import Optional, Any, List, Dict, Literal, Union
from typing import Optional, Literal
from typing import Optional, Dict, Any, List, Union, Literal

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


class QuerySqlInput(BaseModel):
    sql: str = Field(
        ...,
        description="SQL 查询语句。工具强制只读:仅允许 SELECT/SHOW/DESCRIBE/PRAGMA/WITH/EXPLAIN,写入操作返回错误。必填参数"
    )
    limit: int = Field(
        default=50, ge=1, le=10000,
        description="最大返回行数,防止上下文爆炸。默认为50"
    )
    timeout: int = Field(
        default=15000, ge=1000, le=120000,
        description="超时毫秒数。默认为15000(15秒)"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例:user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径(必填)。示例:D:/data/app.db"
    )


class ExecuteSqlInput(BaseModel):
    sql: str = Field(
        ...,
        description="SQL 写入语句。支持 INSERT/UPDATE/DELETE/DDL。必填参数"
    )
    dry_run: bool = Field(
        default=False,
        description="预检模式。True=仅校验语法不执行,返回syntax_valid=True。默认False。注意:检测到危险操作(DROP/TRUNCATE/ALTER/DELETE无WHERE等)时工具自动拦截返回WARNING,与dry_run无关"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=120000,
        description="超时毫秒数。默认为30000(30秒)"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例:user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径(必填)。示例:D:/data/app.db"
    )


class GetDbSchemaInput(BaseModel):
    db_name: Optional[str] = Field(
        default=None,
        description="目标数据库名称。默认为当前连接数据库"
    )
    table_name: Optional[str] = Field(
        default=None,
        description="指定表名,仅获取该表结构。不传则获取全库所有表结构。与filter_pattern互斥,table_name优先"
    )
    filter_pattern: Optional[str] = Field(
        default=None,
        description="表名过滤模式,支持SQL LIKE语法如user%"
    )
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串。示例:user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径(必填)。示例:D:/data/app.db"
    )



class GenerateChartInput(BaseModel):
    data: Dict[str, Any] = Field(
        ...,
        description="图表数据(JSON 格式)。如 {\"labels\": [\"A\", \"B\", \"C\"], \"values\": [10, 20, 30]}"
    )
    chart_type: Optional[Literal["bar", "line", "pie", "scatter"]] = Field(
        default="bar",
        description="图表类型。可选值:bar(柱状图)/line(折线图)/pie(饼图)/scatter(散点图)。默认为bar"
    )
    title: Optional[str] = Field(
        default=None,
        description="图表标题,显示在图的正上方。建议使用能概括数据内容的简短标题,不填则不显示标题"
    )
    x_label: Optional[str] = Field(
        default=None,
        description="X轴标签(可选)。不传则不显示X轴标签,pie图表忽略此参数"
    )
    y_label: Optional[str] = Field(
        default=None,
        description="Y轴标签(可选)。不传则不显示Y轴标签,pie图表忽略此参数"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="输出图片路径(可选)。不传则自动生成临时路径如<temp>/chart_<时间戳>.png"
    )


class AnalyzeDataInput(BaseModel):
    data: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="要分析的数据。可以是数组或CSV/XLSX/XLS文件路径"
    )
    operations: Optional[List[str]] = Field(
        default=None,
        description="分析操作(可选)。默认执行全部(mean/sum/count/min/max/std)"
    )
    group_by: Optional[str] = Field(
        default=None,
        description="分组统计的列名。按该列的值对数据进行分组,对每组分别统计。不填则对所有数据整体统计"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序的列名。按此列的值对结果升序排列。需搭配 top_n 使用以只获取前N条。不填则不排序"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="只返回排序后的前N条结果。需搭配 sort_by 指定排序列。不填则返回全部结果"
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="最大读取行数(data为文件路径时有效)。None=全部读取"
    )


class FilterDataInput(BaseModel):
    data: Union[str, List[Dict[str, Any]]] = Field(
        ...,
        description="要筛选的数据。可以是数组或CSV/Excel文件路径"
    )
    conditions: List[Dict[str, Any]] = Field(
        ...,
        description="筛选条件列表。每个条件: {\"column\": \"列名\", \"operator\": \"操作符\", \"value\": 值}。操作符: eq/ne/gt/gte/lt/lte/in/contains/not_contains"
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="最大读取行数(data为文件路径时有效)。None=全部读取"
    )
    select_columns: Optional[List[str]] = Field(
        default=None,
        description="选择返回的列(可选)。如 [\"name\", \"age\"]"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序的列名。按此列的值对结果升序排列。需搭配 top_n 使用以只获取前N条。不填则不排序"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="只返回排序后的前N条结果。需搭配 sort_by 指定排序列。不填则返回全部结果"
    )


__all__ = [
    "QuerySqlInput",
    "ExecuteSqlInput",
    "GetDbSchemaInput",
]
