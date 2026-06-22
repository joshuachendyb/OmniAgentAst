# -*- coding: utf-8 -*-
"""
filter_data — 按条件筛选/过滤数据
【2026-06-22 小健】从 dataanalysis_tools.py 拆分为独立文件
"""
# 【铁规】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。

import time as _time_mod
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import pandas as pd

from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module, _serialize_rows
from app.utils.json_utils import coerce_json
from app.constants import ERR_FILTER_INVALID


def _build_filter_data_llm_data(exec_code, duration_ms, original_count=0, filtered_count=0, columns=None, detail=""):
    """filter_data的llm_data构建函数 — 小健 2026-06-22"""
    columns = columns or []
    if exec_code == "error":
        return {
            "summary": f"数据筛选失败: {detail}",
            "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": {}},
            "status": {"exec_code": "error", "message": "筛选失败", "code": ERR_FILTER_INVALID, "detail": detail, "hint": "请检查条件和数据"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"筛选完成: {original_count}行→{filtered_count}行",
        "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": {}},
        "status": {"exec_code": "success", "message": "筛选成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"original_count": {"value": original_count, "text": f"{original_count}行"}, "filtered_count": {"value": filtered_count, "text": f"{filtered_count}行"}},
    }


def _load_data_to_df(data: Union[str, List[Dict[str, Any]]], max_rows: Optional[int] = None) -> dict:
    """加载数据为 DataFrame — 小健 2026-06-22 拆分独立文件"""
    if isinstance(data, str):
        path = Path(data)
        if not path.exists():
            return {"error_detail": f"文件不存在: {data}", "params": {"file_path": data}}
        if data.endswith('.xlsx'):
            if not _check_module("openpyxl"):
                return {"error_detail": "openpyxl库未安装", "params": {"library": "openpyxl"}}
            return {"df": pd.read_excel(data, engine="openpyxl", nrows=max_rows)}
        return {"df": pd.read_csv(data, nrows=max_rows)}
    if isinstance(data, list):
        return {"df": pd.DataFrame(data)}
    return {"error_detail": "data参数必须是文件路径或数据数组", "params": {"data_type": type(data).__name__}}


def _build_condition_mask(df: "pd.DataFrame", conditions: List[Dict[str, Any]]) -> dict:
    """构建过滤掩码 — 小沈 2026-05-25"""
    operator_map = {"eq": "__eq__", "ne": "__ne__", "gt": "__gt__", "gte": "__ge__", "lt": "__lt__", "lte": "__le__"}
    valid_operators = set(operator_map.keys()) | {"in", "contains", "not_contains"}
    mask = pd.Series([True] * len(df), index=df.index)
    warnings: List[str] = []

    for cond in conditions:
        column = cond.get("column")
        operator = cond.get("operator", "eq")
        value = cond.get("value")

        if not column:
            return {"error_detail": f"条件缺少column字段: {cond}", "params": {"conditions": str(conditions)[:200]}}
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


def filter_data(data: Union[str, List[Dict[str, Any]]], conditions: List[Dict[str, Any]],
                select_columns: Optional[List[str]] = None, max_rows: Optional[int] = None,
                sort_by: Optional[str] = None, top_n: Optional[int] = None) -> Dict[str, Any]:
    """筛选数据 — 小健 2026-06-22 拆分独立文件"""
    data = coerce_json(data)
    conditions = coerce_json(conditions)
    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="pandas库未安装")
        return build_error(data={"error_detail": "pandas库未安装", "params": {"library": "pandas"}}, llm_data=llm_data)

    try:
        loaded = _load_data_to_df(data, max_rows)
        if "error_detail" in loaded:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_filter_data_llm_data("error", duration_ms, detail=loaded["error_detail"])
            return build_error(data=loaded, llm_data=llm_data)
        df = loaded["df"]
        original_count = len(df)

        result = _build_condition_mask(df, conditions)
        if "error_detail" in result:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_filter_data_llm_data("error", duration_ms, detail=result["error_detail"])
            return build_error(data=result, llm_data=llm_data)
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
        return build_error(data={"error_detail": str(e), "params": {"data": str(data)[:200]}}, llm_data=llm_data)


__all__ = ["filter_data"]