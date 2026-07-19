# -*- coding: utf-8 -*-
"""
DATAANALYSIS Register — 数据分析工具注册点

【2026-06-18 小欧】从 document/ 独立为 dataanalysis/ 目录
【2026-06-18 小健】添加TOOL_DEPENDENCIES常量管理工具依赖
【2026-07-20 小欧】加描述规范:工具描述保持简洁不冗余,能力详情与默认支持能力只写在 schema 类 docstring,禁止在 register 工具描述里重复

6个工具:
- analyze_data    — 数据统计分析 (依赖: pandas)
- filter_data     — 数据筛选过滤 (依赖: pandas)
- generate_chart  — 图表可视化 (依赖: pandas, matplotlib)
- query_sql       — SQL只读查询 (依赖: pandas)
- execute_sql     — SQL写操作 (无第三方依赖)
- get_db_schema   — 数据库结构查询 (无第三方依赖)
"""

from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory
from app.logger import logger

# 数据分析工具依赖配置 — 小健 2026-06-18
# 每个工具对应的第三方依赖包列表
TOOL_DEPENDENCIES = {
    "analyze_data": ["pandas"],
    "filter_data": ["pandas"],
    "generate_chart": ["pandas", "matplotlib"],
    "query_sql": ["pandas"],
    "execute_sql": [],  # 使用内置sqlite3
    "get_db_schema": [],  # 使用内置sqlite3
}


from app.tools.dataanalysis.dataanalysis_schema import (
    AnalyzeDataInput,
    FilterDataInput,
    GenerateChartInput,
    QuerySqlInput,
    ExecuteSqlInput,
    GetDbSchemaInput,
)

from app.tools.dataanalysis.analyze_data import analyze_data
from app.tools.dataanalysis.filter_data import filter_data
from app.tools.dataanalysis.generate_chart import generate_chart
from app.tools.dataanalysis.query_sql import query_sql
from app.tools.dataanalysis.execute_sql import execute_sql
from app.tools.dataanalysis.get_db_schema import get_db_schema

# 【描述规范】2026-07-20 北京老陈 — 工具描述(本 DESCRIPTIONS 字典)保持简洁、不冗余:
# 能力详情与默认支持的能力只写在对应 Schema 类的 docstring 里(会进入 JSON Schema 发给 LLM);
# 本字典仅作一句话路由/适用场景说明,严禁重复 schema docstring 内容。
DESCRIPTIONS = {
    "analyze_data": """对数据集进行统计分析,支持均值/最值/计数等描述性统计和分组统计。适用场景:需要分析数据分布特征、获取统计数据时使用。""",

    "filter_data": """按条件筛选数据,支持多条件组合和排序取前N条。适用场景:需要从数据集中筛选特定条件的记录时使用。""",

    "generate_chart": """生成数据可视化图表,支持柱状图、折线图、饼图、散点图。适用场景:需要将数据以图表形式呈现、生成报告配图时使用。""",

    "query_sql": """执行只读SQL查询,支持SQLite/MySQL/PostgreSQL。适用场景:需要查询数据库数据、分析数据时使用。""",

    "execute_sql": """执行写操作SQL,高风险操作自动拦截,支持预演模式。适用场景:需要修改数据库数据、创建或修改表结构时使用。需谨慎操作。""",

    "get_db_schema": """获取数据库表结构,包括字段名、类型、约束和索引。适用场景:需要了解数据库结构、查看字段定义时使用。""",
}

EXAMPLES = {
    "analyze_data": [
        {"data": "[{\"name\": \"A\", \"value\": 10}, {\"name\": \"B\", \"value\": 20}]"},
        {"path": "D:/data/users.csv", "group_by": "city"},
    ],
    "filter_data": [
        {"data": "[{\"name\": \"A\", \"age\": 25}, {\"name\": \"B\", \"age\": 35}]", "conditions": [{"column": "age", "operator": "gt", "value": 30}]},
        {"path": "D:/data/users.csv", "conditions": [{"column": "city", "operator": "eq", "value": "北京"}], "sort_by": "age", "top_n": 10},
    ],
    "generate_chart": [
        {"data": "{\"labels\": [\"A\", \"B\"], \"values\": [10, 20]}", "chart_type": "bar", "title": "\u9500\u552e\u7edf\u8ba1"},
        {"data": "{\"labels\": [\"1\u6708\", \"2\u6708\"], \"values\": [100, 200]}", "chart_type": "line", "output_path": "D:/output/chart.png"},
    ],
    "query_sql": [
        {"sql": "SELECT * FROM users LIMIT 10", "db_path": "D:/data/app.db"},
        {"sql": "SELECT * FROM users", "connection_type": "mysql", "connection_string": "user:pass@host:3306/dbname"},
    ],
    "execute_sql": [
        {"sql": "INSERT INTO logs (msg) VALUES ('test')", "db_path": "D:/data/app.db"},
        {"sql": "DELETE FROM temp_data WHERE created_at < '2024-01-01'", "db_path": "D:/data/app.db", "dry_run": True},
    ],
    "get_db_schema": [
        {"db_path": "D:/data/app.db"},
        {"db_path": "D:/data/app.db", "table_name": "users"},
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
            dependencies=TOOL_DEPENDENCIES.get(name, []),
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
