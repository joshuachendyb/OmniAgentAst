# -*- coding: utf-8 -*-
"""
数据分析工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.2节 Tool 77-79 定义

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- read_csv_dataframe: 使用pandas读取CSV文件并返回DataFrame格式数据
- generate_chart: 使用matplotlib生成数据可视化图表
- analyze_data: 对数据集进行统计分析
- read_excel_dataframe: 使用pandas读取Excel文件并返回DataFrame格式数据
- filter_data: 按条件筛选/过滤数据

Author: 小沈 - 2026-05-02
【新增 2026-05-05 小沈】read_excel_dataframe, filter_data
"""

import os
import json
import tempfile
import importlib
from typing import Dict, Any, List, Union
from pathlib import Path
from datetime import datetime


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


def read_csv_dataframe(
    file_path: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    has_header: bool = True,
    max_rows: int = 1000,
    usecols: List[str] = None,
    skip_rows: int = 0
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
            nrows=max_rows,
            usecols=usecols,
            skiprows=skip_rows
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


def generate_chart(
    data: Dict[str, Any],
    chart_type: str = "bar",
    title: str = None,
    x_label: str = None,
    y_label: str = None,
    output_path: str = None,
    figure_size: tuple = None,
    rotation: int = 0,
    color: str = None
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

        fig, ax = plt.subplots(figsize=figure_size if figure_size else (10, 6))

        chart_type_lower = chart_type.lower() if chart_type else "bar"

        # 处理颜色
        if color:
            if chart_type_lower == "bar":
                ax.bar(labels, values, color=color)
            elif chart_type_lower == "line":
                ax.plot(labels, values, marker="o", color=color)
            elif chart_type_lower == "pie":
                ax.pie(values, labels=labels, autopct="%1.1f%%", colors=[color]*len(values))
            elif chart_type_lower == "scatter":
                ax.scatter(labels, values, c=color)
            else:
                ax.bar(labels, values, color=color)
        else:
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

        # 设置标签旋转
        if rotation and chart_type_lower != "pie":
            plt.xticks(rotation=rotation)

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


def analyze_data(
    data: Union[str, List[Dict[str, Any]]],
    operations: List[str] = None,
    group_by: str = None,
    sort_by: str = None,
    sort_ascending: bool = True,
    top_n: int = None
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

        # 排序处理
        if sort_by and sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=sort_ascending)

        # 取前N条
        if top_n and top_n > 0:
            df = df.head(top_n)
            result["limited"] = True
            result["top_n"] = top_n

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


def _check_openpyxl() -> bool:
    """检查openpyxl是否可用 - 小沈 2026-05-05"""
    try:
        importlib.import_module("openpyxl")
        return True
    except ImportError:
        return False


def read_excel_dataframe(
    file_path: str,
    sheet_name: str = None,
    max_rows: int = 1000,
    usecols: List[str] = None,
    skip_rows: int = 0
) -> Dict[str, Any]:
    """使用pandas读取Excel文件返回DataFrame格式数据 - 小沈 2026-05-05"""
    if not _check_pandas():
        return {
            "code": "ERR_NO_PANDAS",
            "data": None,
            "message": "pandas库未安装，请先执行: pip install pandas openpyxl"
        }

    if not _check_openpyxl():
        return {
            "code": "ERR_NO_OPENPYXL",
            "data": None,
            "message": "openpyxl库未安装，请先执行: pip install openpyxl"
        }

    try:
        import pandas as pd

        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_EXCEL_DATAFRAME",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }

        df = pd.read_excel(
            path,
            sheet_name=sheet_name,
            nrows=max_rows,
            usecols=usecols,
            skiprows=skip_rows,
            engine="openpyxl"
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
                "sheet_name": sheet_name or "default",
            },
            "message": f"成功读取Excel文件: {file_path}，共 {len(serialized_rows)} 行数据"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_EXCEL_DATAFRAME",
            "data": None,
            "message": f"读取Excel文件失败: {str(e)}"
        }


def filter_data(
    data: Union[str, List[Dict[str, Any]]],
    conditions: List[Dict[str, Any]],
    select_columns: List[str] = None,
    sort_by: str = None,
    sort_ascending: bool = True,
    top_n: int = None
) -> Dict[str, Any]:
    """按条件筛选/过滤数据 - 小沈 2026-05-05"""
    if not _check_pandas():
        return {
            "code": "ERR_NO_PANDAS",
            "data": None,
            "message": "pandas库未安装，请先执行: pip install pandas"
        }

    try:
        import pandas as pd

        if isinstance(data, str):
            path = Path(data)
            if not path.exists():
                return {
                    "code": "ERR_FILTER_DATA",
                    "data": None,
                    "message": f"文件不存在: {data}"
                }
            if data.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(data, engine="openpyxl" if data.endswith('.xlsx') else None)
            else:
                df = pd.read_csv(data)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            return {
                "code": "ERR_FILTER_DATA",
                "data": None,
                "message": "data参数必须是文件路径或数据数组"
            }

        original_count = len(df)

        operator_map = {
            "eq": "__eq__",
            "ne": "__ne__",
            "gt": "__gt__",
            "gte": "__ge__",
            "lt": "__lt__",
            "lte": "__le__",
        }

        mask = pd.Series([True] * len(df), index=df.index)

        for cond in conditions:
            column = cond.get("column")
            operator = cond.get("operator", "eq")
            value = cond.get("value")

            if column not in df.columns:
                continue

            if operator in operator_map:
                try:
                    col_values = df[column].astype(float)
                    value = float(value)
                    cond_mask = getattr(col_values, operator_map[operator])(value)
                except (ValueError, TypeError):
                    cond_mask = getattr(df[column], operator_map[operator])(value)
            elif operator == "in":
                cond_mask = df[column].isin(value if isinstance(value, list) else [value])
            elif operator == "contains":
                cond_mask = df[column].astype(str).str.contains(str(value), na=False)
            elif operator == "not_contains":
                cond_mask = ~df[column].astype(str).str.contains(str(value), na=False)
            else:
                continue

            mask = mask & cond_mask

        filtered_df = df[mask]

        if select_columns:
            available_cols = [c for c in select_columns if c in filtered_df.columns]
            if available_cols:
                filtered_df = filtered_df[available_cols]

        if sort_by and sort_by in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=sort_ascending)

        if top_n and top_n > 0:
            filtered_df = filtered_df.head(top_n)

        columns = filtered_df.columns.tolist()
        rows = filtered_df.values.tolist()
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
                "original_count": original_count,
                "filtered_count": len(serialized_rows),
                "filter_ratio": f"{len(serialized_rows)}/{original_count}",
            },
            "message": f"筛选完成: {original_count}行 → {len(serialized_rows)}行 (条件: {len(conditions)}个)"
        }
    except Exception as e:
        return {
            "code": "ERR_FILTER_DATA",
            "data": None,
            "message": f"数据筛选失败: {str(e)}"
        }
