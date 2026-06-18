# -*- coding: utf-8 -*-
"""
DATAANALYSIS Register — 数据分析工具注册点

【2026-06-18 小欧】从 document/ 独立为 dataanalysis/ 目录

6个工具:
- analyze_data    — 数据统计分析
- filter_data     — 数据筛选过滤
- generate_chart  — 图表可视化
- query_sql       — SQL只读查询
- execute_sql     — SQL写操作
- get_db_schema   — 数据库结构查询
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.tools.dataanalysis.dataanalysis_schema import (
    AnalyzeDataInput,
    FilterDataInput,
    GenerateChartInput,
)

from app.tools.dataanalysis.dataanalysis_tools import (
    analyze_data,
    filter_data,
    generate_chart,
)

# Merged into dataanalysis_schema
    QuerySqlInput,
    ExecuteSqlInput,
    GetDbSchemaInput,
)

from app.tools.dataanalysis.database_tools import (
    query_sql,
    execute_sql,
    get_db_schema,
)

DESCRIPTIONS = {
    "analyze_data": """对数据集进行统计分析。支持直接传入数据列表或CSV/Excel文件路径。可指定统计操作(mean/sum/max/min/count/std/var/median等)、分组字段和对多个数值列进行分析。需要安装pandas库。适用场景:需要获取数据的均值/总和/最值等描述性统计、分析数据分布特征时使用。""",

    "filter_data": """按条件筛选/过滤数据。支持多条件组合,条件含column/operator(eq/ne/gt/gte/lt/lte/in/contains)/value。支持排序(sort_by/descending)、取前N条(top_n)和分页(offset/limit)。数据源可为数据列表或CSV/Excel文件路径。适用场景:需要从数据集中筛选出满足特定条件的记录、排序并取TopN时使用。""",

    "generate_chart": """使用matplotlib生成数据可视化图表。支持柱状图(bar)、折线图(line)、饼图(pie)、散点图(scatter)。可指定图表标题、X轴/Y轴标签、图例位置和输出路径。默认保存到系统临时目录。适用场景:需要将数据以图表形式可视化呈现、生成报告配图时使用。""",

    "query_sql": """执行只读SQL查询。支持SELECT/SHOW/DESCRIBE/EXPLAIN/WITH/PRAGMA语句,强制只读,写操作返回错误。超时自动触发EXPLAIN分析。支持SQLite/MySQL/PostgreSQL三种数据库。SQLite可不传db_path,默认连接应用数据库(~/.omniagent/chat_history.db)。适用场景:需要查询/分析数据库数据、获取表结构信息、分析查询执行计划时使用。""",

    "execute_sql": """执行写操作SQL。支持INSERT/UPDATE/DELETE/CREATE/ALTER/DROP/TRUNCATE等语句。仅支持单语句,自动提交事务。高风险操作(DROP/TRUNCATE)需确认安全级别。支持dry_run=TRUE预演模式。支持SQLite/MySQL/PostgreSQL三种数据库。SQLite可不传db_path,默认连接应用数据库(~/.omniagent/chat_history.db)。适用场景:需要修改数据库数据、创建或修改表结构时使用。""",

    "get_db_schema": """获取数据库结构元数据。返回数据库中的表名、字段名/类型/约束、索引和外键信息。支持按表名精确匹配或按模式(filter_pattern,支持SQL LIKE通配符)过滤。支持SQLite/MySQL/PostgreSQL三种数据库。SQLite可不传db_path,默认连接应用数据库(~/.omniagent/chat_history.db)。适用场景:需要了解数据库表结构、查看字段定义和索引、生成DDL脚本时使用。""",
}

EXAMPLES = {
    "analyze_data": [
        {"data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}]},
        {"data": "D:/data/users.csv", "operations": ["mean", "max"]},
    ],
    "filter_data": [
        {"data": [{"name": "A", "age": 25}, {"name": "B", "age": 35}], "conditions": [{"column": "age", "operator": "gt", "value": 30}]},
        {"data": "D:/data/users.csv", "conditions": [{"column": "city", "operator": "eq", "value": "\u5317\u4eac"}], "sort_by": "age", "top_n": 10},
    ],
    "generate_chart": [
        {"data": {"labels": ["A", "B"], "values": [10, 20]}, "chart_type": "bar", "title": "\u9500\u552e\u7edf\u8ba1"},
        {"data": {"labels": ["1\u6708", "2\u6708"], "values": [100, 200]}, "chart_type": "line", "output_path": "D:/output/chart.png"},
    ],
    "query_sql": [
        {"sql": "SELECT * FROM users LIMIT 10"},
        {"sql": "SELECT * FROM users", "connection_type": "sqlite", "db_path": "D:/data/app.db"},
    ],
    "execute_sql": [
        {"sql": "INSERT INTO logs (msg) VALUES ('test')"},
        {"sql": "DELETE FROM temp_data WHERE created_at < '2024-01-01'", "dry_run": True},
    ],
    "get_db_schema": [
        {"filter_pattern": "user%"},
        {"table_name": "users"},
    ],
}

TOOL_INPUT_MODELS = {
    "analyze_data": AnalyzeDataInput,
    "filter_data": FilterDataInput,
    "generate_chart": GenerateChartInput,
    "query_sql": QuerySqlInput,
    "execute_sql": ExecuteSqlInput,
    "get_db_schema": GetDbSchemaInput,
}

TOOL_IMPLEMENTATIONS = {
    "analyze_data": analyze_data,
    "filter_data": filter_data,
    "generate_chart": generate_chart,
    "query_sql": query_sql,
    "execute_sql": execute_sql,
    "get_db_schema": get_db_schema,
}

DATAANALYSIS_TOOLS = [
    "analyze_data", "filter_data", "generate_chart",
    "query_sql", "execute_sql", "get_db_schema",
]


def _register_dataanalysis_tools():
    """注册6个数据处理工具到DATAANALYSIS分类 — 小欧 2026-06-18"""
    for name, func in TOOL_IMPLEMENTATIONS.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DATAANALYSIS,
            implementation=func,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            needs_confirmation=(name == "execute_sql"),
        )
        logger.debug(
            f"[dataanalysis_register] \u5df2\u6ce8\u518c\u5de5\u5177: {name}, "
            f"Pydantic\u6a21\u578b: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}\u4e2a"
        )


__all__ = [
    "_register_dataanalysis_tools",
    "analyze_data",
    "filter_data",
    "generate_chart",
    "query_sql",
    "execute_sql",
    "get_db_schema",
]
