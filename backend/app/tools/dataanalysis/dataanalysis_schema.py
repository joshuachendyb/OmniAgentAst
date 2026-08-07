# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-06-20 - 小健 - 提取_DbConnectionMixin基类,3个SQL Schema共用连接参数(DRY)
# 2026-07-18 - 小欧 - AnalyzeDataInput.data+FilterDataInput.data 类型从str改为Union[str,List[Dict]](实现层coerce_json已支持list,schema对齐防假阳性WARNING)
# 2026-07-20 - 小欧 - 复核schema docstring规范,既有docstring全部保留,GetDbSchemaInput默认行为已在Field中体现,无需新增
# 2026-07-21 - 小欧 - AnalyzeDataInput/FilterDataInput.top_n description 引用 OBS_MAX_DISPLAY_ITEMS 常量, 加建议不超过上限说明
# 2026-07-21 - 小欧 - QuerySqlInput 新增 limit 字段(1~OBS_MAX_DISPLAY_ITEMS), LLM可见可设置
# 2026-07-21 - 小欧 - 入参即信任: AnalyzeDataInput + FilterDataInput top_n/max_rows 加 ge=1,le=1000; QuerySqlInput.limit le=200→1000
# 2026-07-25 - 小欧 - description去冗余: 4处默认/可选重复移除
# 2026-07-25 - 小欧 - 编辑历史归并+去冗余示例: AnalyzeDataInput/FilterDataInput.path移除示例
# 2026-07-25 - 小欧 - 删除max_rows: top_n唯一行数控制, 统计在head之前计算
# 2026-08-07 - 小欧 - ExecuteSqlInput 新增 confirm_ddl 字段(危险DDL放行开关): True=显式确认后放行裸CREATE/DROP等DDL, False=默认拦截; 与 execute_sql 实现层白名单联动 — 小欧 2026-08-07
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

"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, List, Union, Literal
from app.tools.tool_constants import OBS_MAX_DISPLAY_ITEMS


class _DbConnectionMixin(BaseModel):
    """connection_type决定使用path还是connection_string,严禁交叉传入"""
    connection_type: Literal["sqlite", "mysql", "postgresql"] = Field(
        default="sqlite",
        description="数据库类型。可选值:sqlite/mysql/postgresql。connection_type=sqlite时用path,mysql/postgresql时用connection_string"
    )
    connection_string: Optional[str] = Field(
        default=None,
        description="MySQL/PostgreSQL连接字符串(connection_type=mysql/postgresql时必填,connection_type=sqlite时严禁传入)。示例:user:pass@host:port/dbname"
    )
    path: Optional[str] = Field(
        default=None,
        description="SQLite数据库文件路径(connection_type=sqlite时必填,connection_type=mysql/postgresql时严禁传入)。示例:D:/data/app.db"
    )

    @model_validator(mode="after")
    def _check_connection_params(self):
        if self.connection_type == "sqlite":
            if not self.path:
                raise ValueError("connection_type=sqlite时path必填")
            if self.connection_string:
                raise ValueError("connection_type=sqlite时严禁传入connection_string")
        else:
            if not self.connection_string:
                raise ValueError(f"connection_type={self.connection_type}时connection_string必填")
            if self.path:
                raise ValueError(f"connection_type={self.connection_type}时严禁传入path")
        return self

class GenerateChartInput(BaseModel):

    data: Union[str, Dict[str, Any]] = Field(
        ...,
        description="""数据（两种模式任选其一）。

【模式1：文件路径】
- CSV文件: D:/data/sales.csv
- Excel文件: D:/data/sales.xlsx
- 至少2列数据，第1列=labels，第2列=values

【模式2：内联JSON】{\"labels\":[\"A\",\"B\"],\"values\":[10,20]}

【示例】
- 文件: data="D:/data/sales.csv"
- 内联: data='{"labels":["A","B"],"values":[10,20]}' """
    )
    chart_type: Optional[Literal["bar", "line", "pie", "scatter"]] = Field(
        default="bar",
        description="图表类型。可选值:bar(柱状图)/line(折线图)/pie(饼图)/scatter(散点图)"
    )
    title: Optional[str] = Field(
        default=None,
        description="图表标题,显示在图的正上方。建议使用能概括数据内容的简短标题,不填则不显示标题"
    )
    dest: Optional[str] = Field(
        default=None,
        description="""输出图片路径(绝对路径)。

- 不传: 默认在数据文件同目录生成 chart_<时间戳>.png
- 传入: 使用指定路径

示例: D:/output/chart.png"""
    )


class AnalyzeDataInput(BaseModel):
    """path和data参数互斥,只能传入其中一个 """
    path: Optional[str] = Field(
        default=None,
        description="数据文件路径(绝对路径)。支持CSV/XLSX格式。严禁与data参数同时使用"
    )
    data: Optional[Union[str, List[Dict[str, Any]]]] = Field(
        default=None,
        description="数据。支持两种格式:1.JSON字符串如'[{\"name\":\"A\",\"value\":10}]'; 2.对象数组如[{\"name\":\"A\",\"value\":10}]。严禁与path参数同时使用"
    )
    operations: Optional[List[str]] = Field(
        default=None,
        description="""统计操作列表。不填则使用全部统计操作。

【支持的操作】
- mean: 均值
- sum: 求和
- count: 计数
- min: 最小值
- max: 最大值
- std: 标准差

【默认值】不填时使用全部: ["mean", "sum", "count", "min", "max", "std"]

【示例】operations=["mean", "std"]"""
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
        ge=1, le=1000,
        description=f"只返回前N条结果，建议不超过{OBS_MAX_DISPLAY_ITEMS}条；不填则返回全部"
    )

    @model_validator(mode="after")
    def _check_file_path_or_data(self):
        if self.path and self.data:
            raise ValueError("path和data参数互斥,只能传入其中一个")
        if not self.path and not self.data:
            raise ValueError("path和data参数必须传入其中一个")
        return self


class FilterDataInput(BaseModel):
    """path和data参数互斥,只能传入其中一个 """
    path: Optional[str] = Field(
        default=None,
        description="数据文件路径(绝对路径)。支持CSV/XLSX格式。严禁与data参数同时传入"
    )
    data: Optional[Union[str, List[Dict[str, Any]]]] = Field(
        default=None,
        description="数据。支持两种格式:1.JSON字符串如'[{\"name\":\"A\",\"age\":25}]'; 2.对象数组如[{\"name\":\"A\",\"age\":25}]。严禁与path参数同时传入"
    )
    conditions: List[Dict[str, Any]] = Field(
        ..., 
        description="""筛选条件列表。每个条件: {"column": "列名", "operator": "操作符", "value": 值}

【支持的操作符】
- eq: 等于 (value: 任意值)
- ne: 不等于 (value: 任意值)
- gt: 大于 (value: 数值)
- gte: 大于等于 (value: 数值)
- lt: 小于 (value: 数值)
- lte: 小于等于 (value: 数值)
- in: 包含于 (value: 列表)
- contains: 字符串包含 (value: 字符串)
- not_contains: 字符串不包含 (value: 字符串)

【示例】
[{"column": "age", "operator": "gte", "value": 25}]
[{"column": "name", "operator": "contains", "value": "张"}]"""
    )
    select_columns: Optional[List[str]] = Field(
        default=None,
        description="选择返回的列。如 [\"name\", \"age\"]"
    )
    sort_by: Optional[str] = Field(
        default=None,
        description="排序的列名,按此列升序排列。不填则不排序"
    )
    top_n: Optional[int] = Field(
        default=None,
        ge=1, le=1000,
        description=f"只返回前N条结果，建议不超过{OBS_MAX_DISPLAY_ITEMS}条；不填则返回全部"
    )

    @model_validator(mode="after")
    def _check_path_or_data(self):
        if self.path and self.data:
            raise ValueError("path和data参数互斥,只能传入其中一个")
        if not self.path and not self.data:
            raise ValueError("path和data参数必须传入其中一个")
        return self


class QuerySqlInput(_DbConnectionMixin):
    """SQL查询语句（单条，只读,严禁多条语句）。

【重要限制】
- 一次只能执行一条SELECT语句
- 不支持分号分隔的多条语句
- 强制只读：仅允许 SELECT/SHOW/DESCRIBE/PRAGMA/WITH/EXPLAIN
- 写入操作（INSERT/UPDATE/DELETE/DDL）会返回错误

"""
    sql: str = Field(
        ...,
        description="""SQL查询语句（单条，只读,严禁多条语句）
【示例】
✅ 正确: SELECT * FROM users WHERE age > 25
✅ 正确: SELECT name, COUNT(*) FROM orders GROUP BY name
❌ 错误: SELECT * FROM users; SELECT * FROM orders
❌ 错误: INSERT INTO users ...（写入操作不允许）"""
    )
    limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=1000,
        description=f"返回行数上限，建议不超过{OBS_MAX_DISPLAY_ITEMS}条，超限部分需分页"
    )


class ExecuteSqlInput(_DbConnectionMixin):
    """SQL写入语句（单条,严禁多条语句）。

【重要限制】
- 一次只能执行一条SQL语句
- 不支持分号分隔的多条语句
- 多条语句请多次调用execute_sql

【支持的语句】
- INSERT: 插入数据
- UPDATE: 更新数据
- DELETE: 删除数据
- DDL: CREATE/ALTER/DROP（危险操作会拦截）

【常见错误避免】
1. UNIQUE约束失败: 插入前先用query_sql检查是否存在
2. 外键约束失败: 确保引用的记录存在
3. 语法错误: 检查SQL语法

"""
    sql: str = Field(
        ...,
        description="""SQL写入语句（单条）严禁多条语句。
【示例】
✅ 正确: INSERT INTO users (id, name) VALUES (1, 'Alice')
❌ 错误: INSERT INTO users ...; INSERT INTO orders ...
如需执行多条语句，请多次调用execute_sql"""
    )
    dry_run: bool = Field(
        default=False,
        description="""预检模式。

【功能】
- True: 仅校验SQL语法，不执行
- False: 实际执行SQL

【返回】
- syntax_valid=True: 语法正确
- syntax_valid=False: 语法错误

【注意】危险操作（DROP/TRUNCATE/ALTER/DELETE无WHERE等）会自动拦截返回WARNING，与dry_run无关"""
    )
    # confirm_ddl 危险DDL放行开关 — 小欧 2026-08-07
    confirm_ddl: bool = Field(
        default=False,
        description="""危险DDL放行开关。
【功能】
- True: 允许执行裸 CREATE TABLE / DROP TABLE（无 IF EXISTS）等被拦截的 DDL
- False: 默认拦截（保持安全护栏）
【注意】仅在确认需要修改表结构时设为 True，操作会记录审计日志"""
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
