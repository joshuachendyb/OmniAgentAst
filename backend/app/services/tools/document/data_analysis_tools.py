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
- generate_chart: 使用matplotlib生成数据可视化图表
- analyze_data: 对数据集进行统计分析
- filter_data: 按条件筛选/过滤数据

Author: 小沈 - 2026-05-02
【2026-05-18 小沈】删除read_csv_dataframe/read_excel_dataframe，逻辑已迁入document_tools.py
"""

import os
import json
import tempfile
from typing import Dict, Any, List, Union, Optional, Literal, Tuple
from pathlib import Path
import pandas as pd
from app.utils.time_utils import timestamp_for_filename
from app.utils.tool_result_formatter import build_next_actions, truncate_data_for_frontend, make_json_safe
from app.services.tools._response import build_success, build_error
from app.services.tools.toolhelper.common_helper import _check_module
from app.services.tools.toolhelper.data_helper import _serialize_rows
from app.utils.logger import setup_logger




logger = setup_logger(__name__)


def generate_chart(
    data: Dict[str, Any],
    chart_type: Literal["bar", "line", "pie", "scatter"] = "bar",
    title: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """使用matplotlib生成数据可视化图表 - 小沈 2026-05-02, 修正 2026-05-05"""
    from app.services.tools.document.document_tools import _validate_chart_data
    validation = _validate_chart_data(data)
    if validation["code"] != "SUCCESS" or not validation["data"].get("valid", False):
        return validation

    if not _check_module("matplotlib"):
        return build_error(ERR_NO_MATPLOTLIB, "matplotlib库未安装，请先执行: pip install matplotlib",
            next_actions=build_next_actions([
                ("tool_search", "搜索其他可视化方式", "matplotlib不可用时"),
            ]))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        labels = data.get("labels", [])
        values = data.get("values", [])

        if not labels or not values:
            return build_error(ERR_DOC_CHART_GENERATE, "数据格式错误，需要包含 labels 和 values 字段",
                next_actions=build_next_actions([
                    ("tool_help", "查看generate_chart参数", "确认数据格式时", {"tool_name": "generate_chart"}),
                    ("analyze_data", "先分析数据", "确认可用字段时"),
                ]))

        if output_path is None:
            timestamp = timestamp_for_filename()
            temp_dir = tempfile.gettempdir()
            output_path = os.path.join(temp_dir, f"chart_{timestamp}.png")

        fig, ax = plt.subplots(figsize=(10, 6))

        chart_type_lower = chart_type  # 小健 2026-05-19: Schema Literal已保证非空小写

        try:
            if chart_type_lower == "pie":
                ax.pie(values, labels=labels, autopct="%1.1f%%")
            elif chart_type_lower == "bar":
                ax.bar(labels, values)
            elif chart_type_lower == "line":
                ax.plot(labels, values, marker="o")
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
        finally:
            plt.close(fig)

        result = build_success(
            output_path,
            f"成功生成{chart_type_lower}图表: {output_path}",
            next_actions=build_next_actions([])
        )
        return result
    except Exception as e:
        return build_error(ERR_DOC_CHART_GENERATE, f"生成图表失败: {str(e)}",
            next_actions=build_next_actions([
                ("tool_help", "查看generate_chart用法", "检查参数时", {"tool_name": "generate_chart"}),
                ("filter_data", "尝试筛选数据后重试", "数据量过大时"),
            ]))


def _convert_pd_value(val: Any) -> Any:
    """统一 pandas 值转换为 Python 原生类型。

    小沈 2026-05-25 重构拆分
    消除 P1a-P1c NA转换4处重复（原L209-214, 225-230, 208-212, 224-228）

    pd.Series → {k: _convert_pd_value(v) for k, v in val.items()}
    pd.NA/pd.NaT → None
    有 .item() 的 numpy 类型 → val.item()
    其他 → val
    """
    import pandas as pd
    if isinstance(val, pd.Series):
        return {k: _convert_pd_value(v) for k, v in val.items()}
    if pd.isna(val):
        return None
    if hasattr(val, 'item'):
        return val.item()
    return val


def _compute_stats(
    df: pd.DataFrame,
    numeric_cols: List[str],
    operations: List[str],
    all_ops: List[str],
    *,
    group_by: Optional[str] = None,
) -> Dict[str, Any]:
    """统一分组/非分组统计计算。

    小沈 2026-05-25 重构拆分
    消除 G1a(分组, 原L198-217)和 G1b(非分组, 原L219-233)两套完全重复的循环。
    内部调用 _convert_pd_value 统一 NA 转换。
    """
    import pandas as pd
    if group_by and group_by in df.columns:
        grouped = df.groupby(group_by)[numeric_cols]
        result = {}
        for name, group_df in grouped:
            group_key = str(name)
            result[group_key] = {}
            for op in operations:
                if op not in all_ops:
                    continue
                try:
                    val = getattr(group_df, op)()
                    result[group_key][op] = _convert_pd_value(val)
                except Exception:
                    result[group_key][op] = None
        return {"grouped_statistics": result}

    statistics = {}
    for op in operations:
        if op not in all_ops:
            continue
        try:
            val = getattr(df[numeric_cols], op)()
            statistics[op] = _convert_pd_value(val)
        except Exception:
            statistics[op] = None
    return {"statistics": statistics}


def analyze_data(
    data: Union[str, List[Dict[str, Any]]],
    operations: Optional[List[str]] = None,
    group_by: Optional[str] = None,
    sort_by: Optional[str] = None,
    top_n: Optional[int] = None,
    max_rows: Optional[int] = None,
) -> Dict[str, Any]:
    """对数据集进行统计分析 - 小沈 2026-05-02, 修正 2026-05-05
    【新增参数】encoding: 文件编码(默认utf-8); max_rows: 最大读取行数(默认None=全部)
    """
    if not _check_module("pandas"):
        return build_error(ERR_NO_PANDAS, "pandas库未安装，请先执行: pip install pandas",
            next_actions=build_next_actions([
                ("tool_search", "搜索替代工具", "pandas不可用时"),
            ]))

    try:
        import pandas as pd

        all_ops = ["mean", "sum", "count", "min", "max", "std"]
        if operations is None:
            operations = all_ops

        if isinstance(data, str):
            path = Path(data)
            if not path.exists():
                return build_error(ERR_DOC_ANALYZE_DATA, f"文件不存在: {data}",
                    next_actions=build_next_actions([
                        ("search_files", "搜索文件", "确认文件路径时", {"pattern": Path(data).name}),
                        ("list_directory", "查看目录", "确认目录内容时", {"dir_path": str(Path(data).parent)}),
                    ]))
            read_kwargs = {}
            if max_rows is not None:
                read_kwargs["nrows"] = max_rows
            # 小健 2026-05-19: 识别xlsx后缀
            if data.endswith('.xlsx') or data.endswith('.xls'):
                if not _check_module("openpyxl"):
                    return build_error(ERR_DOC_NO_OPENPYXL, "openpyxl库未安装，请先执行: pip install openpyxl",
                        next_actions=build_next_actions([
                            ("read_document", "尝试其他方式读取", "openpyxl不可用时", {"file_path": data}),
                        ]))
                df = pd.read_excel(data, engine="openpyxl", **({k: v for k, v in read_kwargs.items() if k == 'nrows'}))
            else:
                df = pd.read_csv(data, **read_kwargs)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            return build_error(ERR_DOC_ANALYZE_DATA, "data参数必须是CSV文件路径或数据数组",
                next_actions=build_next_actions([
                    ("tool_help", "查看analyze_data参数", "确认数据格式时", {"tool_name": "analyze_data"}),
                ]))

        total_count = len(df)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            return build_success(
                {"row_count": total_count, "columns": df.columns.tolist(), "statistics": {}},
                "数据中无数值列，无法进行统计计算",
                next_actions=build_next_actions([
                    ("filter_data", "筛选数据", "需要按条件过滤时"),
                    ("generate_chart", "生成图表", "需要可视化时"),
                ])
            )

        result = {"total_count": total_count, "columns": df.columns.tolist()}

        if sort_by and sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=True)

        if top_n and top_n > 0:
            df = df.head(top_n)
            result["top_n"] = top_n

        result["row_count"] = len(df)
        result.update(_compute_stats(df, numeric_cols, operations, all_ops, group_by=group_by))

        return build_success(
            truncate_data_for_frontend(result),
            f"成功分析数据，共 {len(df)} 行，{len(numeric_cols)} 个数值列",
            llm_data={
                "总行数": len(df), "数值列数": len(numeric_cols),
                "列": list(result.get("columns", {}).keys())[:20] if isinstance(result.get("columns"), dict) else [],
                "统计摘要": make_json_safe(result.get("statistics", {}), max_str_len=200)
            },
            next_actions=build_next_actions([
                ("filter_data", "筛选数据", "需要按条件过滤时"),
                ("generate_chart", "生成图表", "需要可视化时"),
            ])
        )
    except Exception as e:
        return build_error(ERR_DOC_ANALYZE_DATA, f"数据分析失败: {str(e)}",
            next_actions=build_next_actions([
                ("tool_help", "查看analyze_data用法", "检查参数时", {"tool_name": "analyze_data"}),
                ("filter_data", "先筛选数据", "数据量过大需要分批处理时"),
            ]))


def _load_data_to_df(data: Union[str, List[Dict[str, Any]]],
                      max_rows: Optional[int] = None) -> dict:
    """加载数据为 DataFrame，返回 {"df": DataFrame} 或 {"error": dict}。"""
    if isinstance(data, str):
        path = Path(data)
        if not path.exists():
            return {"error": build_error(ERR_FILTER_INVALID, f"文件不存在: {data}",
                next_actions=build_next_actions([
                    ("search_files", "搜索文件", "确认文件路径时", {"pattern": path.name})]))}
        if data.endswith('.xlsx'):
            if not _check_module("openpyxl"):
                return {"error": build_error(ERR_DOC_NO_OPENPYXL,
                    "openpyxl库未安装，请先执行: pip install openpyxl",
                    next_actions=build_next_actions([
                        ("read_document", "尝试其他方式读取", "openpyxl不可用时", {"file_path": data})]))}
            return {"df": pd.read_excel(data, engine="openpyxl", nrows=max_rows)}
        return {"df": pd.read_csv(data, nrows=max_rows)}
    if isinstance(data, list):
        return {"df": pd.DataFrame(data)}
    return {"error": build_error(ERR_FILTER_INVALID, "data参数必须是文件路径或数据数组",
        next_actions=build_next_actions([
            ("tool_help", "查看filter_data参数", "确认数据格式时", {"tool_name": "filter_data"})]))}


def _build_condition_mask(df: pd.DataFrame, conditions: List[Dict[str, Any]]) -> dict:
    """构建过滤掩码，返回 {"mask": pd.Series, "warnings": List[str]}。"""
    operator_map = {
        "eq": "__eq__", "ne": "__ne__", "gt": "__gt__",
        "gte": "__ge__", "lt": "__lt__", "lte": "__le__",
    }
    valid_operators = set(operator_map.keys()) | {"in", "contains", "not_contains"}
    mask = pd.Series([True] * len(df), index=df.index)
    warnings: List[str] = []

    for cond in conditions:
        column = cond.get("column")
        operator = cond.get("operator", "eq")
        value = cond.get("value")

        if not column:
            return {"error": build_error(ERR_FILTER_INVALID,
                f"条件缺少column字段: {cond}",
                next_actions=build_next_actions([
                    ("tool_help", "查看filter_data参数", "确认条件格式时", {"tool_name": "filter_data"}),
                    ("analyze_data", "先分析数据", "了解可用字段时")]))}
        if column not in df.columns:
            warnings.append(f"列'{column}'不存在，已跳过")
            continue
        if operator not in valid_operators:
            warnings.append(f"操作符'{operator}'不支持，已跳过")
            continue

        if operator in operator_map:
            try:
                cond_mask = getattr(df[column].astype(float), operator_map[operator])(float(value))
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

    return {"mask": mask, "warnings": warnings}


def filter_data(
    data: Union[str, List[Dict[str, Any]]],
    conditions: List[Dict[str, Any]],
    select_columns: Optional[List[str]] = None,
    max_rows: Optional[int] = None,
    sort_by: Optional[str] = None,
    top_n: Optional[int] = None,
) -> Dict[str, Any]:
    import pandas as pd

    if not _check_module("pandas"):
        return build_error(ERR_NO_PANDAS, "pandas库未安装，请先执行: pip install pandas",
            next_actions=build_next_actions([("tool_search", "搜索替代工具", "pandas不可用时")]))

    try:
        loaded = _load_data_to_df(data, max_rows)
        if "error" in loaded:
            return loaded["error"]
        df = loaded["df"]
        original_count = len(df)

        result = _build_condition_mask(df, conditions)
        if "error" in result:
            return result["error"]
        filtered_df = df[result["mask"]]
        warnings = result["warnings"]

        if select_columns:
            available_cols = [c for c in select_columns if c in filtered_df.columns]
            if available_cols:
                filtered_df = filtered_df[available_cols]

        if sort_by and sort_by in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=True)

        if top_n and top_n > 0:
            filtered_df = filtered_df.head(top_n)

        columns = filtered_df.columns.tolist()
        rows = _serialize_rows(filtered_df)
        result_data = {
            "columns": columns, "rows": rows,
            "row_count": len(rows), "original_count": original_count,
            "filtered_count": len(rows),
            "filter_ratio": f"{len(rows)}/{original_count}",
        }
        if warnings:
            result_data["warnings"] = warnings

        message = f"筛选完成: {original_count}行 → {len(rows)}行 (条件: {len(conditions)}个)"
        if warnings:
            message += f" | 警告: {'; '.join(warnings)}"

        return build_success(truncate_data_for_frontend(result_data), message,
            llm_data={
                "筛选前": result_data["original_count"],
                "筛选后": result_data["filtered_count"],
                "列": result_data["columns"][:20],
                "行预览": make_json_safe(result_data["rows"][:5], max_str_len=150),
            },
            next_actions=build_next_actions([
                ("analyze_data", "统计分析", "需要对筛选结果统计时"),
                ("generate_chart", "生成图表", "需要可视化时")]),
        )
    except Exception as e:
        return build_error(ERR_FILTER_INVALID, f"数据筛选失败: {str(e)}",
            next_actions=build_next_actions([
                ("tool_help", "查看filter_data用法", "检查参数时", {"tool_name": "filter_data"}),
                ("analyze_data", "先分析数据概览", "确认数据内容时")]))
from app.constants import (
    ERR_DOC_ANALYZE_DATA,
    ERR_DOC_CHART_GENERATE,
    ERR_DOC_NO_OPENPYXL,
    ERR_FILTER_INVALID,
    ERR_NO_MATPLOTLIB,
    ERR_NO_PANDAS,
)
