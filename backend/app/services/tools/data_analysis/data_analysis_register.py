# -*- coding: utf-8 -*-
"""
Data Analysis Register - 数据分析工具注册点

【架构规范】2026-05-02 小沈
- 使用 tool_registry.register() 显式注册所有数据分析工具
- 工具函数从 data_analysis_tools.py 导入

【工具列表】（共5个）
1. read_csv_dataframe - 使用pandas读取CSV文件并返回DataFrame格式数据
2. generate_chart - 使用matplotlib生成数据可视化图表
3. analyze_data - 对数据集进行统计分析
4. read_excel_dataframe - 使用pandas读取Excel文件并返回DataFrame格式数据
5. filter_data - 按条件筛选/过滤数据

【注册说明】
- 使用 registry.py 的 tool_registry 统一注册
- 导入 data_analysis_register 时自动触发注册

创建时间: 2026-05-02
更新时间: 2026-05-02
"""

# ============================================================
# 数据分析工具注册 - 使用 Pydantic 模型（按文档设计）
# ============================================================
import logging
from app.services.tools.registry import tool_registry, ToolCategory
from app.utils.logger import logger

from app.services.tools.data_analysis.data_analysis_schema import (
    ReadCsvDataframeInput,
    GenerateChartInput,
    AnalyzeDataInput,
    ReadExcelDataframeInput,
    FilterDataInput,
)

from app.services.tools.data_analysis.data_analysis_tools import (
    read_csv_dataframe,
    generate_chart,
    analyze_data,
    read_excel_dataframe,
    filter_data,
)


DESCRIPTIONS = {
    "read_csv_dataframe": """使用 pandas 读取 CSV 文件并进行数据分析，返回 DataFrame 格式支持后续统计分析。

使用场景：
- 当用户需要读取 CSV 文件并进行数据分析时使用
- 当用户想要对表格数据进行统计、筛选、排序时使用
- 当用户需要进行数据清洗和预处理时使用

参数说明：
- file_path：CSV 文件路径（字符串）。必填参数。如 D:/data/users.csv
- encoding：文件编码（可选）。Agent根据文件来源自动判断，中文文件→gbk/GB2312，英文→utf-8，支持utf-8-sig（带BOM）。默认 utf-8
- delimiter：分隔符（可选）。Agent根据文件内容自动检测，CSV→逗号，TSV→制表符，中文CSV常用分号。默认 ,
- has_header：是否有表头（可选）。Agent分析第一行是否为表头，自动判断。默认 True
- max_rows：最大读取行数（可选）。Agent根据文件大小自动调整，大文件→500，小文件→2000。默认 1000
- usecols：选择列（可选）。指定要读取的列名列表，如 ["name", "age", "score"]
- skip_rows：跳过行数（可选）。跳过文件开头的N行。默认 0

【重要】需要安装 pandas 库（pip install pandas）

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_CSV_DATAFRAME/ERR_NO_PANDAS）
- data: 包含columns、rows、row_count、dtypes的字典
- message: 操作结果消息""",

    "generate_chart": """使用 matplotlib 生成数据可视化图表。

使用场景：
- 当用户需要将数据可视化展示时使用
- 当用户想要生成柱状图、折线图、饼图等图表时使用
- 当用户需要生成报告中的图表时使用

参数说明：
- data：图表数据（JSON 格式，必填）。如 {"labels": ["A", "B"], "values": [10, 20]}
- chart_type：图表类型（可选）。Agent根据数据特征自动判断，趋势数据→line，比例数据→pie，可选 bar/line/pie/scatter。默认 bar
- title：图表标题（可选）。Agent根据数据内容生成描述性标题
- x_label：X轴标签（可选）。Agent从数据列名推断
- y_label：Y轴标签（可选）。Agent从数据列名推断
- output_path：输出图片路径（可选）。Agent根据上下文自动生成，含时间戳
- figure_size：图表尺寸（可选）。如 (10, 6)，默认 (10, 6)
- rotation：X轴标签旋转角度（可选）。如 45，设置标签旋转避免重叠。默认 0
- color：图表颜色（可选）。如 #FF5733 或 blue

【重要】需要安装 matplotlib 库（pip install matplotlib）

返回数据说明：
- code: 状态码（SUCCESS/ERR_GENERATE_CHART/ERR_NO_MATPLOTLIB）
- data: 输出图片路径
- message: 操作结果消息""",

    "analyze_data": """对数据集进行统计分析，返回描述性统计信息。

使用场景：
- 当用户需要对数据进行统计分析时使用
- 当用户想要获取数据的均值、总和、最大值、最小值等统计信息时使用
- 当用户需要进行数据分组分析时使用

参数说明：
- data：要分析的数据（必填）。可以是数组（如 [{"name": "A", "value": 10}]）或 CSV 文件路径（如 "D:/data/users.csv"）
- operations：分析操作（可选）。Agent根据query语义推断所需操作，默认执行全部（mean/sum/count/min/max/std）
- group_by：分组字段（可选）。Agent根据query推断分组字段
- sort_by：排序字段（可选）。按指定列排序
- sort_ascending：升序/降序（可选）。默认 True 升序
- top_n：返回前N条（可选）。如 top_n=10 返回前10条

【重要】需要安装 pandas 库

返回数据说明：
- code: 状态码（SUCCESS/ERR_ANALYZE_DATA/ERR_NO_PANDAS）
- data: 统计分析结果（包含row_count、columns、statistics/grouped_statistics等）
- message: 操作结果消息""",

    "read_excel_dataframe": """使用 pandas 读取 Excel 文件并进行数据分析，返回 DataFrame 格式支持后续统计分析。

使用场景：
- 当用户需要读取 Excel 文件并进行数据分析时使用
- 当用户说"帮我分析这个Excel"时使用
- 当用户想要对Excel表格数据进行统计、筛选时使用

参数说明：
- file_path：Excel 文件路径（必填）。如 D:/data/sales.xlsx
- sheet_name：工作表名称（可选）。默认第一个工作表
- max_rows：最大读取行数（可选）。默认 1000
- usecols：选择列（可选）。如 ["name", "age", "score"]
- skip_rows：跳过行数（可选）。默认 0

【重要】需要安装 pandas + openpyxl 库

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_EXCEL_DATAFRAME/ERR_NO_PANDAS/ERR_NO_OPENPYXL）
- data: 包含columns、rows、row_count、dtypes的字典
- message: 操作结果消息""",

    "filter_data": """按条件筛选/过滤数据，支持多条件组合。

使用场景：
- 当用户说"筛选年龄大于30的记录"时使用
- 当用户说"找出销售额前10的产品"时使用
- 当用户说"只看北京的数据"时使用
- 当用户需要按条件过滤数据时使用

参数说明：
- data：要筛选的数据（必填）。可以是数组或CSV/Excel文件路径
- conditions：筛选条件列表（必填）。每个条件: {"column": "列名", "operator": "操作符", "value": 值}
  - 操作符: eq(等于), ne(不等于), gt(大于), gte(大于等于), lt(小于), lte(小于等于), in(在列表中), contains(包含文本), not_contains(不包含文本)
- select_columns：选择返回的列（可选）。如 ["name", "age"]
- sort_by：排序字段（可选）
- sort_ascending：升序/降序（可选）。默认True升序
- top_n：返回前N条（可选）

返回数据说明：
- code: 状态码（SUCCESS/ERR_FILTER_DATA）
- data: 包含columns、rows、row_count、original_count、filtered_count
- message: 操作结果消息""",
}


EXAMPLES = {
    "read_csv_dataframe": [
        {"file_path": "D:/data/users.csv"},
        {"file_path": "D:/data/users.csv", "encoding": "gbk", "delimiter": ";"},
    ],
    "generate_chart": [
        {"data": {"labels": ["A", "B"], "values": [10, 20]}, "chart_type": "bar", "title": "销售统计"},
        {"data": {"labels": ["1月", "2月"], "values": [100, 200]}, "chart_type": "line", "output_path": "D:/output/chart.png"},
    ],
    "analyze_data": [
        {"data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}]},
        {"data": "D:/data/users.csv", "operations": ["mean", "max"]},
    ],
    "read_excel_dataframe": [
        {"file_path": "D:/data/sales.xlsx"},
        {"file_path": "D:/data/sales.xlsx", "sheet_name": "Sheet2", "max_rows": 500},
    ],
    "filter_data": [
        {"data": [{"name": "A", "age": 25}, {"name": "B", "age": 35}], "conditions": [{"column": "age", "operator": "gt", "value": 30}]},
        {"data": "D:/data/users.csv", "conditions": [{"column": "city", "operator": "eq", "value": "北京"}], "sort_by": "age", "top_n": 10},
    ],
}


TOOL_INPUT_MODELS = {
    "read_csv_dataframe": ReadCsvDataframeInput,
    "generate_chart": GenerateChartInput,
    "analyze_data": AnalyzeDataInput,
    "read_excel_dataframe": ReadExcelDataframeInput,
    "filter_data": FilterDataInput,
}


def _register_data_analysis_tools():
    """
    【2026-05-02 小沈】显式注册所有数据分析工具
    使用 Pydantic 模型自动生成 OpenAI Schema
    """
    tool_methods = {
        "read_csv_dataframe": read_csv_dataframe,
        "generate_chart": generate_chart,
        "analyze_data": analyze_data,
        "read_excel_dataframe": read_excel_dataframe,
        "filter_data": filter_data,
    }

    for name, func in tool_methods.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DATA_ANALYSIS,
            implementation=func,
            version="1.0.0",
            input_model=input_model,
            examples=examples
        )
        logger.info(f"[data_analysis_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__ if input_model else 'None'}, examples: {len(examples)}个")


# 触发注册
_register_data_analysis_tools()


__all__ = [
    "read_csv_dataframe",
    "generate_chart",
    "analyze_data",
    "read_excel_dataframe",
    "filter_data",
]
