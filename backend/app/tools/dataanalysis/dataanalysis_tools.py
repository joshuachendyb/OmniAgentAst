# -*- coding: utf-8 -*-
"""
数据分析工具函数模块
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。后续审查关注功能逻辑本身的代码10大规范遵守和最优美简洁性，禁止以"文件过大"作为问题提出。

【创建时间】2026-05-02 小沈
【设计依据】按文档第8.2节 Tool 77-79 定义

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件:
1. *_tools.py: 函数实现(必须有详细注释)
2. *_schema.py: Pydantic 模型(输入参数定义)
3. *_register.py: 显式注册(description + examples + input_model)

包含:
- generate_chart: 使用matplotlib生成数据可视化图表
- analyze_data: 对数据集进行统计分析
- filter_data: 按条件筛选/过滤数据

Author: 小沈 - 2026-05-02
【2026-05-18 小沈】删除read_csv_dataframe/read_excel_dataframe,逻辑已迁入document_tools.py
"""

import os
import json
import tempfile
import time as _time_mod
import pandas as pd
from typing import Dict, Any, List, Union, Optional, Literal, Tuple
from pathlib import Path
from app.utils.time_utils import timestamp_for_filename
from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.tools.toolhelper.common_helper import _check_module
from app.tools.toolhelper.data_helper import _serialize_rows
from app.utils.logger import setup_logger
from app.utils.json_utils import coerce_json
from app.constants import (
    ERR_DOC_ANALYZE_DATA,
    ERR_DOC_CHART_GENERATE,
    ERR_DOC_NO_OPENPYXL,
    ERR_FILTER_INVALID,
    ERR_NO_MATPLOTLIB,
    ERR_NO_PANDAS,
)




logger = setup_logger(__name__)


def _build_generate_chart_llm_data(exec_code, duration_ms, chart_type="", output_path="", detail=""):
    """generate_chart的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        return {
            "summary": f"生成图表失败: {detail}",
            "action": {"tool": "generate_chart", "tool_zh": "生成图表", "target": chart_type, "params": {"chart_type": chart_type}},
            "status": {"exec_code": "error", "message": "生成图表失败", "code": ERR_DOC_CHART_GENERATE, "detail": detail, "hint": "请检查数据和参数"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"成功生成{chart_type}图表: {output_path}",
        "action": {"tool": "generate_chart", "tool_zh": "生成图表", "target": chart_type, "params": {"chart_type": chart_type}},
        "status": {"exec_code": "success", "message": "图表生成成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


def _build_analyze_data_llm_data(exec_code, duration_ms, row_count=0, numeric_col_count=0, columns=None, detail=""):
    """analyze_data的llm_data构建函数 — 小健 2026-06-21"""
    columns = columns or []
    if exec_code == "error":
        return {
            "summary": f"数据分析失败: {detail}",
            "action": {"tool": "analyze_data", "tool_zh": "分析数据", "target": "dataset", "params": {}},
            "status": {"exec_code": "error", "message": "分析失败", "code": ERR_DOC_ANALYZE_DATA, "detail": detail, "hint": "请检查数据格式"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"分析完成: {row_count}行, {numeric_col_count}个数值列",
        "action": {"tool": "analyze_data", "tool_zh": "分析数据", "target": "dataset", "params": {}},
        "status": {"exec_code": "success", "message": "分析成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"row_count": {"value": row_count, "text": f"{row_count}行"}, "numeric_cols": {"value": numeric_col_count, "text": f"{numeric_col_count}列"}},
    }


def _build_filter_data_llm_data(exec_code, duration_ms, original_count=0, filtered_count=0, columns=None, detail=""):
    """filter_data的llm_data构建函数 — 小健 2026-06-21"""
    columns = columns or []
    if exec_code == "error":
        return {
            "summary": f"数据筛选失败: {detail}",
            "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": {}},
            "status": {"exec_code": "error", "message": "筛选失败", "code": ERR_FILTER_INVALID, "detail": detail, "hint": "请检查条件和数据"},
            "duration_ms": duration_ms, "metrics": {},
        }
    return {
        "summary": f"筛选完成: {original_count}行→{filtered_count}行",
        "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": {}},
        "status": {"exec_code": "success", "message": "筛选成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"original_count": {"value": original_count, "text": f"{original_count}行"}, "filtered_count": {"value": filtered_count, "text": f"{filtered_count}行"}},
    }


def generate_chart(
    data: Union[str, Dict[str, Any]],
    chart_type: Literal["bar", "line", "pie", "scatter"] = "bar",
    title: Optional[str] = None,
    x_label: Optional[str] = None,
    y_label: Optional[str] = None,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """使用matplotlib生成数据可视化图表 - 小沈 2026-05-02, 修正 2026-05-05
    【2026-06-18 小健】修改output_path逻辑：文件路径→原文件目录，字典→必须指定output_path
    【2026-06-20 小健】Schema删x_label/y_label，函数签名保留内部默认值; 加coerce_json防御
    【2026-06-21 小健】builder改造，新3字段result
    """
    data = coerce_json(data)
    t0 = _time_mod.perf_counter()
    if not _check_module("matplotlib"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="matplotlib库未安装")
        return build_error(data={"error": "matplotlib库未安装,请先执行: pip install matplotlib"}, llm_data=llm_data)

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        source_file_dir = None
        chart_data = None
        
        if isinstance(data, str):
            path = Path(data)
            if not path.exists():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=f"文件不存在: {data}")
                return build_error(data={"file_path": data}, llm_data=llm_data)
            source_file_dir = str(path.parent)
            
            if data.endswith('.xlsx') or data.endswith('.xls'):
                df = pd.read_excel(data, engine="openpyxl")
            else:
                df = pd.read_csv(data)
            
            if len(df.columns) < 2:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="数据至少需要2列(标签列+数值列)")
                return build_error(data={"error": "数据至少需要2列"}, llm_data=llm_data)
            
            labels = df.iloc[:, 0].tolist()
            values = df.iloc[:, 1].tolist()
            chart_data = {"labels": labels, "values": values}
        elif isinstance(data, dict):
            chart_data = data
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="data参数必须是文件路径(str)或图表数据(dict)")
            return build_error(data={"error": "data参数必须是文件路径或图表数据"}, llm_data=llm_data)

        from app.tools.document.document_tools import _validate_chart_data
        validation = _validate_chart_data(chart_data)
        if validation["code"] != "SUCCESS" or not validation["data"].get("valid", False):
            return validation

        labels = chart_data.get("labels", [])
        values = chart_data.get("values", [])

        if not labels or not values:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="数据格式错误,需要包含labels和values字段")
            return build_error(data={"error": "数据格式错误"}, llm_data=llm_data)

        if output_path is None:
            timestamp = timestamp_for_filename()
            if source_file_dir:
                output_path = os.path.join(source_file_dir, f"chart_{timestamp}.png")
            else:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail="data为字典时必须指定output_path参数")
                return build_error(data={"error": "data为字典时必须指定output_path"}, llm_data=llm_data)

        fig, ax = plt.subplots(figsize=(10, 6))

        chart_type_lower = chart_type

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

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("success", duration_ms, chart_type_lower, output_path)
        return build_success(data={"output_path": output_path, "chart_type": chart_type_lower}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_generate_chart_llm_data("error", duration_ms, chart_type, detail=str(e))
        return build_error(data={"error": str(e)}, llm_data=llm_data)


def _convert_pd_value(val: Any) -> Any:
    """统一 pandas 值转换为 Python 原生类型。

    小沈 2026-05-25 重构拆分
    消除 P1a-P1c NA转换4处重复(原L209-214, 225-230, 208-212, 224-228)

    pd.Series → {k: _convert_pd_value(v) for k, v in val.items()}
    pd.NA/pd.NaT → None
    有 .item() 的 numpy 类型 → val.item()
    其他 → val
    """
    if isinstance(val, pd.Series):
        return {k: _convert_pd_value(v) for k, v in val.items()}
    if pd.isna(val):
        return None
    if hasattr(val, 'item'):
        return val.item()
    return val


def _compute_stats(
    df: "pd.DataFrame",
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
    【2026-06-20 小健】Schema删operations/max_rows，函数签名保留内部默认值; 加coerce_json防御
    【2026-06-21 小健】builder改造，新3字段result
    """
    data = coerce_json(data)
    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="pandas库未安装")
        return build_error(data={"error": "pandas库未安装,请先执行: pip install pandas"}, llm_data=llm_data)

    try:
        all_ops = ["mean", "sum", "count", "min", "max", "std"]
        if operations is None:
            operations = all_ops

        if isinstance(data, str):
            path = Path(data)
            if not path.exists():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_analyze_data_llm_data("error", duration_ms, detail=f"文件不存在: {data}")
                return build_error(data={"file_path": data}, llm_data=llm_data)
            read_kwargs = {}
            if max_rows is not None:
                read_kwargs["nrows"] = max_rows
            if data.endswith('.xlsx') or data.endswith('.xls'):
                if not _check_module("openpyxl"):
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="openpyxl库未安装")
                    return build_error(data={"error": "openpyxl库未安装"}, llm_data=llm_data)
                df = pd.read_excel(data, engine="openpyxl", **({k: v for k, v in read_kwargs.items() if k == 'nrows'}))
            else:
                df = pd.read_csv(data, **read_kwargs)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="data参数必须是CSV文件路径或数据数组")
            return build_error(data={"error": "data参数必须是文件路径或数据数组"}, llm_data=llm_data)

        total_count = len(df)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_analyze_data_llm_data("success", duration_ms, total_count, 0, df.columns.tolist())
            return build_success(data={"row_count": total_count, "columns": df.columns.tolist(), "statistics": {}}, llm_data=llm_data)

        result = {"total_count": total_count, "columns": df.columns.tolist()}

        if sort_by and sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=True)

        if top_n and top_n > 0:
            df = df.head(top_n)
            result["top_n"] = top_n

        result["row_count"] = len(df)
        result.update(_compute_stats(df, numeric_cols, operations, all_ops, group_by=group_by))

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("success", duration_ms, len(df), len(numeric_cols), df.columns.tolist())
        return build_success(data=truncate_data_for_frontend(result), llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail=str(e))
        return build_error(data={"error": str(e)}, llm_data=llm_data)


def _load_data_to_df(data: Union[str, List[Dict[str, Any]]],
                      max_rows: Optional[int] = None) -> dict:
    """加载数据为 DataFrame,返回 {"df": DataFrame} 或 {"error": dict}。
    【2026-06-21 小健】builder改造，新3字段result
    """
    if isinstance(data, str):
        path = Path(data)
        if not path.exists():
            llm_data = _build_filter_data_llm_data("error", 0, detail=f"文件不存在: {data}")
            return {"error": build_error(data={"file_path": data}, llm_data=llm_data)}
        if data.endswith('.xlsx'):
            if not _check_module("openpyxl"):
                llm_data = _build_filter_data_llm_data("error", 0, detail="openpyxl库未安装")
                return {"error": build_error(data={"error": "openpyxl库未安装"}, llm_data=llm_data)}
            return {"df": pd.read_excel(data, engine="openpyxl", nrows=max_rows)}
        return {"df": pd.read_csv(data, nrows=max_rows)}
    if isinstance(data, list):
        return {"df": pd.DataFrame(data)}
    llm_data = _build_filter_data_llm_data("error", 0, detail="data参数必须是文件路径或数据数组")
    return {"error": build_error(data={"error": "data参数必须是文件路径或数据数组"}, llm_data=llm_data)}


def _build_condition_mask(df: "pd.DataFrame", conditions: List[Dict[str, Any]]) -> dict:
    """构建过滤掩码,返回 {"mask": pd.Series, "warnings": List[str]}。"""
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
            llm_data = _build_filter_data_llm_data("error", 0, detail=f"条件缺少column字段: {cond}")
            return {"error": build_error(data={"condition": cond}, llm_data=llm_data)}
        if column not in df.columns:
            warnings.append(f"列'{column}'不存在,已跳过")
            continue
        if operator not in valid_operators:
            warnings.append(f"操作符'{operator}'不支持,已跳过")
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
    """筛选数据 — 小沈 2026-05-25 重构
    【2026-06-20 小健】Schema删max_rows，函数签名保留内部默认值; 加coerce_json防御
    【2026-06-21 小健】builder改造，新3字段result
    """
    data = coerce_json(data)
    conditions = coerce_json(conditions)
    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="pandas库未安装")
        return build_error(data={"error": "pandas库未安装,请先执行: pip install pandas"}, llm_data=llm_data)

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

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("success", duration_ms, original_count, len(rows), columns)
        return build_success(data=truncate_data_for_frontend(result_data), llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail=str(e))
        return build_error(data={"error": str(e)}, llm_data=llm_data)

