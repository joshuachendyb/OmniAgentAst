# -*- coding: utf-8 -*-
"""
analyze_data — 对数据集进行统计分析
【2026-06-22 小健】从 dataanalysis_tools.py 拆分为独立文件
"""

import time as _time_mod
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import pandas as pd

from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.utils.json_utils import coerce_json
from app.constants import ERR_DOC_ANALYZE_DATA


def _convert_pd_value(val: Any) -> Any:
    """统一 pandas 值转换为 Python 原生类型 — 小沈 2026-05-25"""
    if isinstance(val, pd.Series):
        return {k: _convert_pd_value(v) for k, v in val.items()}
    if pd.isna(val):
        return None
    if hasattr(val, 'item'):
        return val.item()
    return val


def _compute_stats(df: "pd.DataFrame", numeric_cols: List[str], operations: List[str],
                   all_ops: List[str], *, group_by: Optional[str] = None) -> Dict[str, Any]:
    """统一分组/非分组统计计算 — 小沈 2026-05-25"""
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


def _build_analyze_data_llm_data(exec_code, duration_ms, row_count=0, numeric_col_count=0, columns=None, detail=""):
    """analyze_data的llm_data构建函数 — 小健 2026-06-22"""
    columns = columns or []
    if exec_code == "error":
        return {
            "summary": f"数据分析失败: {detail}",
            "action": {"tool": "analyze_data", "tool_zh": "分析数据", "target": "dataset", "params": {}},
            "status": {"exec_code": "error", "message": "分析失败", "code": ERR_DOC_ANALYZE_DATA, "detail": detail, "hint": "请检查数据格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"分析完成: {row_count}行, {numeric_col_count}个数值列",
        "action": {"tool": "analyze_data", "tool_zh": "分析数据", "target": "dataset", "params": {}},
        "status": {"exec_code": "success", "message": "分析成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"row_count": {"value": row_count, "text": f"{row_count}行"}, "numeric_cols": {"value": numeric_col_count, "text": f"{numeric_col_count}列"}},
    }


def analyze_data(data: Union[str, List[Dict[str, Any]]], operations: Optional[List[str]] = None,
                 group_by: Optional[str] = None, sort_by: Optional[str] = None,
                 top_n: Optional[int] = None, max_rows: Optional[int] = None) -> Dict[str, Any]:
    """对数据集进行统计分析 — 小健 2026-06-22 拆分独立文件"""
    data = coerce_json(data)
    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="pandas库未安装")
        return build_error(data={"error_detail": "pandas库未安装"}, llm_data=llm_data)

    try:
        all_ops = ["mean", "sum", "count", "min", "max", "std"]
        if operations is None:
            operations = all_ops

        if isinstance(data, str):
            path = Path(data)
            if not path.exists():
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_analyze_data_llm_data("error", duration_ms, detail=f"文件不存在: {data}")
                return build_error(data={"error_detail": f"文件不存在: {data}"}, llm_data=llm_data)
            read_kwargs = {}
            if max_rows is not None:
                read_kwargs["nrows"] = max_rows
            if data.endswith('.xlsx') or data.endswith('.xls'):
                if not _check_module("openpyxl"):
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="openpyxl库未安装")
                    return build_error(data={"error_detail": "openpyxl库未安装"}, llm_data=llm_data)
                df = pd.read_excel(data, engine="openpyxl", **({k: v for k, v in read_kwargs.items() if k == 'nrows'}))
            else:
                df = pd.read_csv(data, **read_kwargs)
        elif isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="data参数必须是文件路径或数据数组")
            return build_error(data={"error_detail": "data参数必须是文件路径或数据数组"}, llm_data=llm_data)

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
        return build_error(data={"error_detail": str(e)}, llm_data=llm_data)


__all__ = ["analyze_data"]