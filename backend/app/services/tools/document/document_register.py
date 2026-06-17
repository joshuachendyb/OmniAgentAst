# -*- coding: utf-8 -*-
"""
Document Register - 文档读写+数据处理工具注册点

【架构规范】2026-05-02 小沈
- document_register.py 作为文档+数据工具的注册点
- 实际工具实现在 document_tools.py 中
- 使用 registry.py 的 tool_registry.register() 显式注册

【重构 2026-05-18 小健】
- 8个旧工具合并为 read_document + write_document
- analyze_data/filter_data/generate_chart 从 data_analysis_register 迁入
- 共6个LLM工具
【2026-05-18 小沈】Database工具迁入(query_sql/execute_sql/get_db_schema)
【2026-06-17 小沈】拆分DOC_CONTENT→DOCUMENT+DATA，按职责分类

【工具列表】(共15个)

文档操作工具(9个) → DOCUMENT分类:
1. read_pdf - 读取PDF文档
2. read_docx - 读取Word文档
3. read_pptx - 读取PPT文档
4. read_xlsx - 读取Excel文档
5. write_docx - 写入Word文档
6. write_xlsx - 写入Excel文档
7. write_pdf - 写入PDF文档
8. write_pptx - 写入PPT文档
9. convert_document - 文档格式转换

数据处理工具(6个) → DATA分类:
10. analyze_data - 数据统计分析
11. filter_data - 数据筛选过滤
12. generate_chart - 图表可视化
13. query_sql - SQL查询
14. execute_sql - SQL写操作
15. get_db_schema - 数据库结构查询

【注册说明】
- 使用 Pydantic 模型注册,自动生成 OpenAI Schema
- 文档工具注册到DOCUMENT分类，数据工具注册到DATA分类

创建时间: 2026-05-02
更新时间: 2026-06-17 小沈
"""

from app.services.tools.registry import tool_registry
from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger

from app.services.tools.document.document_schema import (
    ReadPdfInput,
    ReadDocxInput,
    ReadPptxInput,
    ReadXlsxInput,
    WriteDocxInput,
    WriteXlsxInput,
    WritePdfInput,
    WritePptxInput,
    ConvertDocumentInput,
)

from app.services.tools.document.document_tools import (
    read_pdf,
    read_docx,
    read_pptx,
    read_xlsx,
    write_docx,
    write_xlsx,
    write_pdf,
    write_pptx,
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
    "read_pdf": """读取PDF(.pdf)文件内容。支持页码范围选择(pages参数,如'1-3,5')和表格提取(extract_tables)。适用场景:需要读取PDF文档内容、提取表格数据时使用。""",

    "read_docx": """读取Word(.docx)文档内容。支持表格提取(extract_tables)。自动降级处理.doc格式(转PDF后读取)。适用场景:需要读取Word文档内容、提取文本和表格时使用。""",

    "read_pptx": """读取PPT(.pptx)演示文稿内容。提取每页幻灯片的文本和备注。适用场景:需要读取PPT内容、提取演讲稿时使用。""",

    "read_xlsx": """读取Excel(.xlsx)/CSV/TSV/JSON数据文件。支持指定工作表、最大行数、编码和分隔符。自动降级处理.xls格式(转PDF后读取)。适用场景:需要读取表格数据、分析数据集时使用。""",

    "write_docx": """写入Word(.docx)文档。支持标题(title)/正文(content)/段落(paragraphs)/表格(table_data)/结构化内容(data)。适用场景:需要生成Word报告、导出文档时使用。""",

    "write_xlsx": """写入Excel(.xlsx)文件。data参数支持dict(headers+rows)或list自动推断headers。可指定工作表名。适用场景:需要导出数据到Excel表格时使用。""",

    "write_pdf": """写入PDF(.pdf)文件。支持标题(title)/正文(content)/段落(paragraphs)/表格(table_data)。适用场景:需要生成PDF报告、归档文档时使用。""",

    "write_pptx": """写入PPT(.pptx)演示文稿。支持标题(title)和幻灯片列表(slides)。适用场景:需要生成PPT演示文稿时使用。""",

    "convert_document": """将Office文档转换为PDF格式。支持Word(.docx/.doc→PDF)、Excel(.xlsx/.xls→PDF)、PPT(.pptx/.ppt→PDF)以及OpenDocument格式(.odt/.ods→PDF)。需要系统安装LibreOffice。适用场景:需要将文档转为PDF进行分发、归档或打印时使用。""",

    "analyze_data": """对数据集进行统计分析。支持直接传入数据列表或CSV/Excel文件路径。可指定统计操作(mean/sum/max/min/count/std/var/median等)、分组字段和对多个数值列进行分析。需要安装pandas库。适用场景:需要获取数据的均值/总和/最值等描述性统计、分析数据分布特征时使用。""",

    "filter_data": """按条件筛选/过滤数据。支持多条件组合,条件含column/operator(eq/ne/gt/gte/lt/lte/in/contains)/value。支持排序(sort_by/descending)、取前N条(top_n)和分页(offset/limit)。数据源可为数据列表或CSV/Excel文件路径。适用场景:需要从数据集中筛选出满足特定条件的记录、排序并取TopN时使用。""",

    "generate_chart": """使用matplotlib生成数据可视化图表。支持柱状图(bar)、折线图(line)、饼图(pie)、散点图(scatter)。可指定图表标题、X轴/Y轴标签、图例位置和输出路径。默认保存到系统临时目录。适用场景:需要将数据以图表形式可视化呈现、生成报告配图时使用。""",

    # 【2026-05-18 小沈】Database工具描述(从database_register迁入)
    "query_sql": """执行只读SQL查询。支持SELECT/SHOW/DESCRIBE/EXPLAIN/WITH/PRAGMA语句,强制只读,写操作返回错误。超时自动触发EXPLAIN分析。支持SQLite/MySQL/PostgreSQL三种数据库。SQLite可不传db_path,默认连接应用数据库(~/.omniagent/chat_history.db)。适用场景:需要查询/分析数据库数据、获取表结构信息、分析查询执行计划时使用。""",

    "execute_sql": """执行写操作SQL。支持INSERT/UPDATE/DELETE/CREATE/ALTER/DROP/TRUNCATE等语句。仅支持单语句,自动提交事务。高风险操作(DROP/TRUNCATE)需确认安全级别。支持dry_run=TRUE预演模式。支持SQLite/MySQL/PostgreSQL三种数据库。SQLite可不传db_path,默认连接应用数据库(~/.omniagent/chat_history.db)。适用场景:需要修改数据库数据、创建或修改表结构时使用。""",

    "get_db_schema": """获取数据库结构元数据。返回数据库中的表名、字段名/类型/约束、索引和外键信息。支持按表名精确匹配或按模式(filter_pattern,支持SQL LIKE通配符)过滤。支持SQLite/MySQL/PostgreSQL三种数据库。SQLite可不传db_path,默认连接应用数据库(~/.omniagent/chat_history.db)。适用场景:需要了解数据库表结构、查看字段定义和索引、生成DDL脚本时使用。""",
}

EXAMPLES = {
    "read_pdf": [
        {"file_path": "D:/documents/report.pdf"},
        {"file_path": "D:/documents/report.pdf", "pages": "1-3", "extract_tables": True},
    ],
    "read_docx": [
        {"file_path": "D:/documents/report.docx"},
        {"file_path": "D:/documents/report.docx", "extract_tables": True},
    ],
    "read_pptx": [
        {"file_path": "D:/documents/presentation.pptx"},
    ],
    "read_xlsx": [
        {"file_path": "D:/data/sales.xlsx", "sheet_name": "Sheet2", "max_rows": 100},
        {"file_path": "D:/data/sales.csv", "encoding": "gbk"},
    ],
    "write_docx": [
        {"file_path": "D:/output/report.docx", "title": "测试报告", "content": "这是测试内容"},
        {"file_path": "D:/output/report_structured.docx", "data": {"title": "结构化报告", "content": [{"type": "h1", "text": "第一章"}, {"type": "paragraph", "text": "正文内容"}, {"type": "table", "rows": [["列1", "列2"], ["a", "b"]]}]}},
    ],
    "write_xlsx": [
        {"file_path": "D:/output/data.xlsx", "data": {"headers": ["姓名", "年龄"], "rows": [["张三", 25], ["李四", 30]]}},
    ],
    "write_pdf": [
        {"file_path": "D:/output/report.pdf", "title": "测试报告", "content": "这是报告内容"},
    ],
    "write_pptx": [
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
    "read_pdf": ReadPdfInput,
    "read_docx": ReadDocxInput,
    "read_pptx": ReadPptxInput,
    "read_xlsx": ReadXlsxInput,
    "write_docx": WriteDocxInput,
    "write_xlsx": WriteXlsxInput,
    "write_pdf": WritePdfInput,
    "write_pptx": WritePptxInput,
    "convert_document": ConvertDocumentInput,
    "analyze_data": AnalyzeDataInput,
    "filter_data": FilterDataInput,
    "generate_chart": GenerateChartInput,
    "query_sql": QuerySqlInput,
    "execute_sql": ExecuteSqlInput,
    "get_db_schema": GetDbSchemaInput,
}

TOOL_IMPLEMENTATIONS = {
    "read_pdf": read_pdf,
    "read_docx": read_docx,
    "read_pptx": read_pptx,
    "read_xlsx": read_xlsx,
    "write_docx": write_docx,
    "write_xlsx": write_xlsx,
    "write_pdf": write_pdf,
    "write_pptx": write_pptx,
    "convert_document": convert_document,
    "analyze_data": analyze_data,
    "filter_data": filter_data,
    "generate_chart": generate_chart,
    "query_sql": query_sql,
    "execute_sql": execute_sql,
    "get_db_schema": get_db_schema,
}


def _register_document_tools():
    """注册文档操作工具(9个DOCUMENT分类) + 数据处理工具(6个DATA分类) — 小沈 2026-06-17"""
    # 文档操作工具 → DOCUMENT分类
    DOCUMENT_TOOLS = [
        "read_pdf", "read_docx", "read_pptx", "read_xlsx",
        "write_docx", "write_xlsx", "write_pdf", "write_pptx",
        "convert_document",
    ]
    # 数据处理工具 → DATA分类
    DATA_TOOLS = [
        "analyze_data", "filter_data", "generate_chart",
        "query_sql", "execute_sql", "get_db_schema",
    ]

    for name, func in TOOL_IMPLEMENTATIONS.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])
        # 根据工具名选择分类
        cat = ToolCategory.DOCUMENT if name in DOCUMENT_TOOLS else ToolCategory.DATA

        tool_registry.register(
            name=name,
            description=desc,
            category=cat,
            implementation=func,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
            needs_confirmation=(name == "execute_sql"),
        )
        logger.debug(
            f"[document_register] 已注册工具: {name}, "
            f"分类: {cat.value}, "
            f"Pydantic模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


__all__ = [
    "_register_document_tools",
    "read_pdf",
    "read_docx",
    "read_pptx",
    "read_xlsx",
    "write_docx",
    "write_xlsx",
    "write_pdf",
    "write_pptx",
    "convert_document",
    "analyze_data",
    "filter_data",
    "generate_chart",
    "query_sql",
    "execute_sql",
    "get_db_schema",
]
