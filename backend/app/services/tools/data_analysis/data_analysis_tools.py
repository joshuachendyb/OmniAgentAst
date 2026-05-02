# -*- coding: utf-8 -*-
"""
数据分析工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.2节 Tool 77-79 定义

包含：
- read_csv_dataframe: 使用pandas读取CSV文件并返回DataFrame格式数据
- generate_chart: 使用matplotlib生成数据可视化图表
- analyze_data: 对数据集进行统计分析

Author: 小沈 - 2026-05-02
"""

import os
import json
import tempfile
import importlib
from typing import Dict, Any, List, Union
from pathlib import Path
from datetime import datetime

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.data_analysis.data_analysis_schema import (
    ReadCsvDataframeInput,
    GenerateChartInput,
    AnalyzeDataInput,
)


def _check_pandas() -> bool:
    """检查pandas是否可用 - 小沈 2026-05-02"""
    try:
        importlib.import_module("pandas")
        return True
    except ImportError:
        return False


def _check_matplotlib() -> bool:
    """检查matplotlib是否可用 - 小沈 2026-05-02"""
    try:
        importlib.import_module("matplotlib")
        return True
    except ImportError:
        return False


@register_tool(
    name="read_csv_dataframe",
    description="""使用 pandas 读取 CSV 文件并进行数据分析，返回 DataFrame 格式支持后续统计分析。

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
    category=ToolCategory.DATA_ANALYSIS,
    input_model=ReadCsvDataframeInput,
    examples=[
        {"file_path": "D:/data/users.csv"},
        {"file_path": "D:/data/users.csv", "encoding": "gbk", "delimiter": ";"},
    ]
)
def read_csv_dataframe(
    file_path: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    has_header: bool = True,
    max_rows: int = 1000
) -> Dict[str, Any]:
    """使用pandas读取CSV文件返回DataFrame格式数据 - 小沈 2026-05-02"""
    if not _check_pandas():
        return {
            "code": "ERR_NO_PANDAS",
            "data": None,
            "message": "pandas库未安装，请先执行: pip install pandas"
        }

    try:
        import pandas as pd

        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_CSV_DATAFRAME",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }

        header = 0 if has_header else None
        df = pd.read_csv(
            path,
            encoding=encoding,
            delimiter=delimiter,
            header=header,
            nrows=max_rows
        )

        columns = df.columns.tolist()
        rows = df.values.tolist()
        dtypes = {col: str(dtype) for col, dtype in df.dtypes.items()}

        serialized_rows = []
        for row in rows:
            serialized_row = []
            for val in row:
                if pd.isna(val):
                    serialized_row.append(None)
                elif hasattr(val, 'item'):
                    serialized_row.append(val.item())
                else:
                    serialized_row.append(val)
            serialized_rows.append(serialized_row)

        return {
            "code": "SUCCESS",
            "data": {
                "columns": columns,
                "rows": serialized_rows,
                "row_count": len(serialized_rows),
                "dtypes": dtypes,
            },
            "message": f"成功读取CSV文件: {file_path}，共 {len(serialized_rows)} 行数据"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_CSV_DATAFRAME",
            "data": None,
            "message": f"读取CSV文件失败: {str(e)}"
        }


@register_tool(
    name="generate_chart",
    description="""使用 matplotlib 生成数据可视化图表。

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
    category=ToolCategory.DATA_ANALYSIS,
    input_model=GenerateChartInput,
    examples=[
        {"data": {"labels": ["A", "B"], "values": [10, 20]}, "chart_type": "bar", "title": "销售统计"},
        {"data": {"labels": ["1月", "2月"], "values": [100, 200]}, "chart_type": "line", "output_path": "D:/output/chart.png"},
    ]
)
def generate_chart(
    data: Dict[str, Any],
    chart_type: str = "bar",
    title: str = None,
    x_label: str = None,
    y_label: str = None,
    output_path: str = None
) -> Dict[str, Any]:
    """使用matplotlib生成数据可视化图表 - 小沈 2026-05-02"""
    if not _check_matplotlib():
        return {
            "code": "ERR_NO_MATPLOTLIB",
            "data": None,
            "message": "matplotlib库未安装，请先执行: pip install matplotlib"
        }

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = data.get("labels", [])
        values = data.get("values", [])

        if not labels or not values:
            return {
                "code": "ERR_GENERATE_CHART",
                "data": None,
                "message": "数据格式错误，需要包含 labels 和 values 字段"
            }

        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"chart_{timestamp}.png")

        fig, ax = plt.subplots(figsize=(10, 6))

        chart_type_lower = chart_type.lower() if chart_type else "bar"

        if chart_type_lower == "bar":
            ax.bar(labels, values)
        elif chart_type_lower == "line":
            ax.plot(labels, values, marker="o")
        elif chart_type_lower == "pie":
            ax.pie(values, labels=labels, autopct="%1.1f%%")
        elif chart_type_lower == "scatter":
            ax.scatter(labels, values)
        else:
            ax.bar(labels, values)

        if title:
            ax.set_title(title)
        if x_label and chart_type_lower != "pie":
            ax.set_xlabel(x_label)
        if y_label and chart_type_lower != "pie":
            ax.set_ylabel(y_label)

        plt.tight_layout()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        return {
            "code": "SUCCESS",
            "data": output_path,
            "message": f"成功生成{chart_type_lower}图表: {output_path}"
        }
    except Exception as e:
        return {
            "code": "ERR_GENERATE_CHART",
            "data": None,
            "message": f"生成图表失败: {str(e)}"
        }


@register_tool(
    name="analyze_data",
    description="""对数据集进行统计分析，返回描述性统计信息。

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
    category=ToolCategory.DATA_ANALYSIS,
    input_model=AnalyzeDataInput,
    examples=[
        {"data": [{"name": "A", "value": 10}, {"name": "B", "value": 20}]},
        {"data": "D:/data/users.csv", "operations": ["mean", "max"]},
    ]
)
def analyze_data(
    data: Union[str, List[Dict[str, Any]]],
    operations: List[str] = None,
    group_by: str = None
) -> Dict[str, Any]:
    """对数据集进行统计分析 - 小沈 2026-05-02"""
    if not _check_pandas():
        return {
            "code": "ERR_NO_PANDAS",
            "data": None,
            "message": "pandas库未安装，请先执行: pip install pandas"
        }

    try:
        import pandas as pd

        all_ops = ["mean", "sum", "count", "min", "max", "std"]
        if operations is None:
            operations = all_ops

        if isinstance(data, str):
            path = Path(data)
            if not path.exists():
                return {
                    "code": "ERR_ANALYZE_DATA",
                    "data": None,
                    "message": f"文件不存在: {data}"
                }
            df = pd.read_csv(data)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            return {
                "code": "ERR_ANALYZE_DATA",
                "data": None,
                "message": "data参数必须是CSV文件路径或数据数组"
            }

        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            return {
                "code": "SUCCESS",
                "data": {"row_count": len(df), "columns": df.columns.tolist(), "statistics": {}},
                "message": "数据中无数值列，无法进行统计计算"
            }

        result = {"row_count": len(df), "columns": df.columns.tolist()}

        if group_by and group_by in df.columns:
            grouped = df.groupby(group_by)[numeric_cols]
            stats_by_group = {}
            for name, group_df in grouped:
                group_key = str(name)
                stats_by_group[group_key] = {}
                for op in operations:
                    if op in all_ops:
                        try:
                            val = getattr(group_df, op)()
                            if isinstance(val, pd.Series):
                                stats_by_group[group_key][op] = {
                                    k: (None if pd.isna(v) else v.item() if hasattr(v, 'item') else v)
                                    for k, v in val.items()
                                }
                            else:
                                stats_by_group[group_key][op] = None if pd.isna(val) else (val.item() if hasattr(val, 'item') else val)
                        except Exception:
                            stats_by_group[group_key][op] = None
            result["grouped_statistics"] = stats_by_group
        else:
            statistics = {}
            for op in operations:
                if op in all_ops:
                    try:
                        val = getattr(df[numeric_cols], op)()
                        if isinstance(val, pd.Series):
                            statistics[op] = {
                                k: (None if pd.isna(v) else v.item() if hasattr(v, 'item') else v)
                                for k, v in val.items()
                            }
                        else:
                            statistics[op] = None if pd.isna(val) else (val.item() if hasattr(val, 'item') else val)
                    except Exception:
                        statistics[op] = None
            result["statistics"] = statistics

        return {
            "code": "SUCCESS",
            "data": result,
            "message": f"成功分析数据，共 {len(df)} 行，{len(numeric_cols)} 个数值列"
        }
    except Exception as e:
        return {
            "code": "ERR_ANALYZE_DATA",
            "data": None,
            "message": f"数据分析失败: {str(e)}"
        }
