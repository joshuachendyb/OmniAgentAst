# -*- coding: utf-8 -*-
"""
DataAnalysis Schema - 数据分析工具参数模型

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

【2026-06-20 小健】提取_DbConnectionMixin基类,3个SQL Schema共用连接参数(DRY)
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, List, Union, Literal


class _DbConnectionMixin(BaseModel):
    """数据库连接参数混入基类 — 小健 2026-06-20 DRY:3个SQL Schema共用"""
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。默认为sqlite"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL 连接字符串(connection_type=mysql/postgresql时必填)。示例:user:pass@host:port/dbname"
    )
    db_path: Optional[str] = Field(
        default=None,
        description="SQLite 数据库文件路径(connection_type=sqlite时必填)。示例:D:/data/app.db"
    )

class GenerateChartInput(BaseModel):
    data: str = Field(
        ...,
        description="""数据文件路径(绝对路径)。

【支持格式】
- CSV文件: D:/data/sales.csv
- Excel文件: D:/data/sales.xlsx

【文件要求】
- 至少2列数据
- 第1列作为labels（横轴标签）
- 第2列作为values（纵轴数值）

【示例】
- CSV文件: data="D:/data/sales.csv"
- Excel文件: data="D:/data/report.xlsx" """
    )
    chart_type: Optional[Literal["bar", "line", "pie", "scatter"]] = Field(
        default="bar",
        description="图表类型。可选值:bar(柱状图)/line(折线图)/pie(饼图)/scatter(散点图)。默认为bar"
    )
    title: Optional[str] = Field(
        default=None,
        description="图表标题,显示在图的正上方。建议使用能概括数据内容的简短标题,不填则不显示标题"
    )
    output_path: Optional[str] = Field(
        default=None,
        description="""输出图片路径(绝对路径,可选)。

- 不传: 默认在数据文件同目录生成 chart_<时间戳>.png
- 传入: 使用指定路径

示例: D:/output/chart.png"""
    )


class AnalyzeDataInput(BaseModel):
    '''file_path和data参数互斥,只能传入其中一个'''
    file_path: Optional[str] = Field(
        default=None,
        description="数据文件路径(绝对路径)。支持CSV/XLSX格式。严禁与data参数同时使用。示例:D:/data/sales.csv"
    )
    data: Optional[str] = Field(
        default=None,
        description="JSON字符串形式的数组数据。严禁与file_path参数同时使用。示例:'[{\"name\":\"A\",\"value\":10}]'"
    )
    operations: Optional[List[str]] = Field(
        default=None,
        description="统计操作列表。可选值: mean(均值)/sum(求和)/count(计数)/min(最小值)/max(最大值)/std(标准差)。不填则使用全部统计操作"
    )
    group_by: Optional[str] = Field(
        default=None,
        description="分组统计的列名。按该列的值对数据进行分组,对每组分别统计。不填则对所有数据整体统计"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序的列名,按此列升序排列。不填则不排序"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="只返回前N条结果。不填则返回全部"
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="最大读取行数。对于大文件,可以限制读取的行数以提高性能"
    )

    @model_validator(mode="after")
    def _check_file_path_or_data(self):
        if self.file_path and self.data:
            raise ValueError("file_path和data参数互斥,只能传入其中一个")
        if not self.file_path and not self.data:
            raise ValueError("file_path和data参数必须传入其中一个")
        return self


class FilterDataInput(BaseModel):
    '''file_path和data参数互斥,只能传入其中一个'''
    file_path: Optional[str] = Field(
        default=None,
        description="数据文件路径(绝对路径)。支持CSV/XLSX格式。严禁与data参数同时传入。示例:D:/data/users.csv"
    )
    data: Optional[str] = Field(
        default=None,
        description="JSON字符串形式的数组数据。严禁与file_path参数同时传入。示例:'[{\"name\":\"A\",\"age\":25}]'"
    )
    conditions: List[Dict[str, Any]] = Field(
        ..., description="筛选条件列表。每个条件: {\"column\": \"列名\", \"operator\": \"操作符\", \"value\": 值}。操作符: eq/ne/gt/gte/lt/lte/in/contains/not_contains"
    )
    select_columns: Optional[List[str]] = Field(
        default=None,
        description="选择返回的列(可选)。如 [\"name\", \"age\"]"
    )
    max_rows: Optional[int] = Field(
        default=None,
        description="最大读取行数。对于大文件,可以限制读取的行数以提高性能"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序的列名,按此列升序排列。不填则不排序"
    )
    top_n: Optional[int] = Field(
        default=None,
        description="只返回前N条结果。不填则返回全部"
    )

    @model_validator(mode="after")
    def _check_file_path_or_data(self):
        if self.file_path and self.data:
            raise ValueError("file_path和data参数互斥,只能传入其中一个")
        if not self.file_path and not self.data:
            raise ValueError("file_path和data参数必须传入其中一个")
        return self


class QuerySqlInput(_DbConnectionMixin):
    sql: str = Field(
        ...,
        description="SQL 查询语句。工具强制只读:仅允许 SELECT/SHOW/DESCRIBE/PRAGMA/WITH/EXPLAIN,写入操作返回错误。必填参数"
    )


class ExecuteSqlInput(_DbConnectionMixin):
    sql: str = Field(
        ...,
        description="SQL 写入语句。支持 INSERT/UPDATE/DELETE/DDL。必填参数"
    )
    dry_run: bool = Field(
        default=False,
        description="预检模式。True=仅校验语法不执行,返回syntax_valid=True。默认False。注意:检测到危险操作(DROP/TRUNCATE/ALTER/DELETE无WHERE等)时工具自动拦截返回WARNING,与dry_run无关"
    )


class GetDbSchemaInput(_DbConnectionMixin):
    table_name: Optional[str] = Field(
        default=None,
        description="指定表名,仅获取该表结构。不传则获取全库所有表结构"
    )



__all__ = [
    "GenerateChartInput",
    "AnalyzeDataInput",
    "FilterDataInput",
    "QuerySqlInput",
    "ExecuteSqlInput",
    "GetDbSchemaInput",
]
