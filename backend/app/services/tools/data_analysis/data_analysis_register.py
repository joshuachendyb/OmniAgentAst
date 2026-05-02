# -*- coding: utf-8 -*-
"""
Data Analysis Register - 数据分析工具注册点

【架构规范】2026-05-02 小沈
- 使用 tool_registry.register() 显式注册所有数据分析工具
- 工具函数从 data_analysis_tools.py 导入

【工具列表】（共3个）
1. read_csv_dataframe - 使用pandas读取CSV文件并返回DataFrame格式数据
2. generate_chart - 使用matplotlib生成数据可视化图表
3. analyze_data - 对数据集进行统计分析

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
)

from app.services.tools.data_analysis.data_analysis_tools import (
    read_csv_dataframe,
    generate_chart,
    analyze_data,
)


DESCRIPTIONS = {
    "read_csv_dataframe": """使用 pandas 读取 CSV 文件并进行数据分析，返回 DataFrame 格式支持后续统计分析。

使用场景：
- 当用户需要读取 CSV 文件并进行数据分析时使用
- 当用户想要对表格数据进行统计、筛选、排序时使用
- 当用户需要进行数据清洗和预处理时使用

参数说明：
- file_path：CSV 文件路径
- encoding：文件编码，默认 utf-8
- delimiter：分隔符，默认 ,
- has_header：是否有表头，默认 true
- max_rows：最大读取行数，默认 1000

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
- data：图表数据（JSON 格式）
- chart_type：图表类型（可选），可填 bar/line/pie/scatter
- title：图表标题
- x_label：X轴标签
- y_label：Y轴标签
- output_path：输出图片路径（可选）

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
- data：要分析的数据（数组或 CSV 文件路径）
- operations：分析操作，可选 mean/sum/count/min/max/std（默认全部）
- group_by：分组字段

【重要】需要安装 pandas 库

返回数据说明：
- code: 状态码（SUCCESS/ERR_ANALYZE_DATA/ERR_NO_PANDAS）
- data: 统计分析结果
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
}


TOOL_INPUT_MODELS = {
    "read_csv_dataframe": ReadCsvDataframeInput,
    "generate_chart": GenerateChartInput,
    "analyze_data": AnalyzeDataInput,
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
]
