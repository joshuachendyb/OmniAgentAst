# -*- coding: utf-8 -*-
"""
Document Register - 文档读写工具注册点

【架构规范】2026-05-02 小沈
- document_register.py 作为文档工具的注册点
- 实际工具实现在 document_tools.py 中
- 使用 registry.py 的 tool_registry.register() 显式注册

【重构 2026-05-18 小健】
- 8个旧工具合并为 read_document + write_document
- analyze_data/filter_data/generate_chart 从 data_analysis_register 迁入
- 共6个LLM工具
【2026-05-18 小沈】Database工具迁入（query_sql/execute_sql/get_db_schema）

【工具列表】（共9个）
1. read_document - 统一读取文档（按后缀路由）
2. write_document - 统一写入文档（按后缀路由）
3. convert_document - 文档格式转换
4. analyze_data - 对数据集进行统计分析（迁入）
5. filter_data - 按条件筛选/过滤数据（迁入）
6. generate_chart - 生成数据可视化图表（迁入）
7. query_sql - 执行只读SQL查询（迁入）
8. execute_sql - 执行写操作SQL（迁入）
9. get_db_schema - 获取数据库结构元数据（迁入）

【注册说明】
- 使用 Pydantic 模型注册，自动生成 OpenAI Schema
- 导入 document_register 时自动触发注册

创建时间: 2026-05-02
更新时间: 2026-05-18 小健
"""

import logging
from app.services.tools.registry import ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.document.document_schema import (
    ReadDocumentInput,
    WriteDocumentInput,
    ConvertDocumentInput,
)

from app.services.tools.document.document_tools import (
    read_document,
    write_document,
    convert_document,
)

from app.services.tools.document.data_analysis_schema import (
    AnalyzeDataInput,
    FilterDataInput,
    GenerateChartInput,
)

from app.services.tools.document.data_analysis_tools import (
    analyze_data,
    filter_data,
    generate_chart,
)

from app.services.tools.document.database_schema import (
    QuerySqlInput,
    ExecuteSqlInput,
    GetDbSchemaInput,
)
from app.services.tools.document.database_tools import (
    query_sql,
    execute_sql,
    get_db_schema,
)

DESCRIPTIONS = {
    "read_document": """统一读取文档内容，按文件后缀自动路由到对应解析器（PDF/DOCX/XLSX/PPTX/CSV/TSV）。

【使用场景】
- 当用户需要读取任意格式文档内容时使用
- Agent无需判断文件格式，工具自动按后缀选择解析器
- 支持提取表格、图片、演讲备注等

【支持的格式】
- .pdf → PDF解析（支持页码范围、提取表格/图片）
- .docx/.doc → Word解析（支持提取表格）
- .xlsx/.xls → Excel解析（支持指定工作表、最大行数）
- .pptx → PPT解析（支持提取演讲备注）
- .csv/.tsv → CSV解析（支持分隔符、编码、use_pandas返回dtypes）

【use_pandas参数】
- False（默认）：使用标准库/openpyxl，快速轻量
- True：使用pandas，返回dtypes等元数据，适合数据分析

【返回数据】
- code: SUCCESS / ERR_FILE_NOT_FOUND / ERR_UNSUPPORTED_FORMAT
- data: 文档内容（格式因文件类型而异）
- message: 操作结果消息""",

    "write_document": """统一写入文档，按文件后缀自动路由到对应写入器（DOCX/XLSX/PDF/PPTX）。

【使用场景】
- 当用户需要生成任意格式文档时使用
- Agent无需判断输出格式，工具自动按后缀选择写入器
- 支持标题、段落、表格、幻灯片等

【支持的格式】
- .docx → Word写入（支持标题、段落、表格）
- .xlsx → Excel写入（支持表头+行数据）
- .pdf → PDF写入（支持标题、段落、表格）
- .pptx → PPT写入（支持标题、幻灯片列表）

【返回数据】
- code: SUCCESS / ERR_UNSUPPORTED_FORMAT
- data: { file_path }
- message: 操作结果消息""",

    "convert_document": """文档格式转换（docx/xlsx/pptx → PDF）。
 
【使用场景】
- 当用户需要将Word/Excel/PPT转换为PDF时使用
- 当用户说"把这个docx转成pdf"时使用
- 当用户需要分享不可编辑的文档时使用
 
 
【返回数据】
- code: SUCCESS / ERR_CONVERT_DOCUMENT / ERR_NO_LIBREOFFICE
- data: { input_path, output_path }
- message: 操作结果消息
 
【重要】需要安装LibreOffice（https://www.libreoffice.org/download/）""",

    "analyze_data": """对数据集进行统计分析，返回描述性统计信息。

使用场景：
- 当用户需要对数据进行统计分析时使用
- 当用户想要获取数据的均值、总和、最大值、最小值等统计信息时使用
- 当用户需要进行数据分组分析时使用


【重要】需要安装 pandas 库

返回数据说明：
- code: 状态码（SUCCESS/ERR_ANALYZE_DATA/ERR_NO_PANDAS）
- data: 统计分析结果（包含row_count、columns、statistics/grouped_statistics等）
- message: 操作结果消息""",

    "filter_data": """按条件筛选/过滤数据，支持多条件组合。

使用场景：
- 当用户说"筛选年龄大于30的记录"时使用
- 当用户说"找出销售额前10的产品"时使用
- 当用户说"只看北京的数据"时使用
- 当用户需要按条件过滤数据时使用


返回数据说明：
- code: 状态码（SUCCESS/ERR_FILTER_DATA）
- data: 包含columns、rows、row_count、original_count、filtered_count
- message: 操作结果消息""",

    "generate_chart": """使用 matplotlib 生成数据可视化图表。

使用场景：
- 当用户需要将数据可视化展示时使用
- 当用户想要生成柱状图、折线图、饼图等图表时使用
- 当用户需要生成报告中的图表时使用


【重要】需要安装 matplotlib 库（pip install matplotlib）

返回数据说明：
- code: 状态码（SUCCESS/ERR_GENERATE_CHART/ERR_NO_MATPLOTLIB）
- data: 输出图片路径
- message: 操作结果消息""",

    # 【2026-05-18 小沈】Database工具描述（从database_register迁入）
    "query_sql": """执行只读SQL查询（SELECT/SHOW/DESCRIBE），返回结果集。

【使用场景】
- 当用户需要查询数据库数据时使用
- 当用户需要分析表数据时使用
- 当需要执行只读操作时使用


【重要】强制只读，写操作返回错误。超时自动触发EXPLAIN分析。

【返回数据】
- code: SUCCESS / ERR_READ_ONLY_VIOLATION / ERR_DB_CONNECTION / ERR_SQL_EXEC
- data: { columns, rows, total }
- message: 操作结果消息""",

    "execute_sql": """执行写操作SQL（INSERT/UPDATE/DELETE/DDL）。

【使用场景】
- 当用户需要修改数据库数据时使用
- 当用户需要执行CREATE TABLE等DDL时使用
- 当需要执行写操作时使用


【重要】仅支持单语句自动提交。高风险操作（DROP/TRUNCATE）自动拦截。

【返回数据】
- code: SUCCESS / WARNING / ERR_DB_CONNECTION / ERR_SQL_EXEC / ERR_EXEC_FAILED
- data: { affected_rows, sql }
- message: 操作结果消息""",

    "get_db_schema": """获取数据库结构元数据，包括表名、字段、类型、索引、外键。

【使用场景】
- 当用户需要查看数据库表结构时使用
- 当用户需要理解表设计时
- 当用户需要生成DDL时使用


【重要】include_details=true时最多返回20个表，防止上下文爆炸。

【返回数据】
- code: SUCCESS / ERR_DB_CONNECTION / ERR_SQL_EXEC / ERR_SCHEMA_FAILED
- data: { tables: [{name, columns, indexes}], total }
- message: 操作结果消息""",
}

EXAMPLES = {
    "read_document": [
        {"file_path": "D:/documents/report.pdf"},
        {"file_path": "D:/documents/report.pdf", "pages": "1-3", "extract_tables": True},
        {"file_path": "D:/documents/report.docx", "extract_tables": True},
        {"file_path": "D:/data/sales.xlsx", "sheet_name": "Sheet2", "max_rows": 100},
        {"file_path": "D:/documents/presentation.pptx", "extract_notes": True},
    ],
    "write_document": [
        {"file_path": "D:/output/report.docx", "title": "测试报告", "content": "这是测试内容"},
        {"file_path": "D:/output/data.xlsx", "data": {"headers": ["姓名", "年龄"], "rows": [["张三", 25], ["李四", 30]]}},
        {"file_path": "D:/output/report.pdf", "title": "测试报告", "content": "这是报告内容"},
        {"file_path": "D:/output/presentation.pptx", "title": "项目汇报"},
        {"file_path": "D:/output/slides.pptx", "title": "季度总结", "slides": [{"title": "业绩概览", "content": "本季度销售额增长20%"}]},
    ],
    "convert_document": [
        {"input_path": "D:/documents/report.docx", "output_format": "pdf"},
        {"input_path": "D:/data/sales.xlsx", "output_format": "pdf", "output_path": "D:/output/sales.pdf"},
    ],
    "analyze_data": [
        {"data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}]},
        {"data": "D:/data/users.csv", "operations": ["mean", "max"]},
    ],
    "filter_data": [
        {"data": [{"name": "A", "age": 25}, {"name": "B", "age": 35}], "conditions": [{"column": "age", "operator": "gt", "value": 30}]},
        {"data": "D:/data/users.csv", "conditions": [{"column": "city", "operator": "eq", "value": "北京"}], "sort_by": "age", "top_n": 10},
    ],
    "generate_chart": [
        {"data": {"labels": ["A", "B"], "values": [10, 20]}, "chart_type": "bar", "title": "销售统计"},
        {"data": {"labels": ["1月", "2月"], "values": [100, 200]}, "chart_type": "line", "output_path": "D:/output/chart.png"},
    ],
    # 【2026-05-18 小沈】Database工具示例
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
    "read_document": ReadDocumentInput,
    "write_document": WriteDocumentInput,
    "convert_document": ConvertDocumentInput,
    "analyze_data": AnalyzeDataInput,
    "filter_data": FilterDataInput,
    "generate_chart": GenerateChartInput,
    "query_sql": QuerySqlInput,
    "execute_sql": ExecuteSqlInput,
    "get_db_schema": GetDbSchemaInput,
}

TOOL_IMPLEMENTATIONS = {
    "read_document": read_document,
    "write_document": write_document,
    "convert_document": convert_document,
    "analyze_data": analyze_data,
    "filter_data": filter_data,
    "generate_chart": generate_chart,
    "query_sql": query_sql,
    "execute_sql": execute_sql,
    "get_db_schema": get_db_schema,
}


def _register_document_tools():
    """注册所有文档读写工具 — 小健 2026-05-18 共9个LLM工具（含Database迁入）"""
    for name, func in TOOL_IMPLEMENTATIONS.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DOCUMENT,
            implementation=func,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(
            f"[document_register] 已注册工具: {name}, "
            f"Pydantic模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


__all__ = [
    "_register_document_tools",
    "read_document",
    "write_document",
    "convert_document",
    "analyze_data",
    "filter_data",
    "generate_chart",
    "query_sql",
    "execute_sql",
    "get_db_schema",
]
