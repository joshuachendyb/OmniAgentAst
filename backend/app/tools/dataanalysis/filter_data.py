# -*- coding: utf-8 -*-
"""
filter_data — 按条件筛选/过滤数据
【2026-06-22 小健】从 dataanalysis_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import time as _time_mod
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import pandas as pd

from app.tools.tool_response import build_success, build_error
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.tools.tool_fc_helper import _check_module, _serialize_rows
from app.utils.json_utils import coerce_json
from app.tools.tool_constants import ERR_FILTER_INVALID


def _build_filter_data_llm_data(exec_code, duration_ms, original_count=0, filtered_count=0, columns=None, detail="", hint="",
                                 file_path="", data="", conditions=None, select_columns=None, sort_by="", top_n=0, max_rows=0):
    """filter_data的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增user_params — 小欧 2026-07-05 加hint参数 — 小欧 2026-07-06 去掉data/conditions字段，防止大字段返回给LLM"""
    columns = columns or []
    _act_params = {}
    if file_path:
        _act_params["file_path"] = file_path
    if select_columns:
        _act_params["select_columns"] = select_columns
    if sort_by:
        _act_params["sort_by"] = sort_by
    if top_n:
        _act_params["top_n"] = top_n
    if max_rows:
        _act_params["max_rows"] = max_rows
    if exec_code == "error":
        return {
            "summary": f"数据筛选失败: {detail}",
            "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": _act_params},
            "status": {"exec_code": "error", "message": "筛选失败", "code": ERR_FILTER_INVALID, "detail": detail, "hint": hint if hint else "请检查条件和数据"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"筛选完成: {original_count}行→{filtered_count}行",
        "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": _act_params},
        "status": {"exec_code": "success", "message": "筛选成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"original_count": {"value": original_count, "text": f"{original_count}行"}, "filtered_count": {"value": filtered_count, "text": f"{filtered_count}行"}},
    }


def _load_data_to_df(data: Union[str, List[Dict[str, Any]]], max_rows: Optional[int] = None) -> dict:
    """加载数据为 DataFrame — 小健 2026-06-22 拆分独立文件 — 小欧 2026-06-24 修复list分支max_rows无效"""
    if isinstance(data, str):
        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.READ_FILE, data)
        if not is_valid:
            return {"error_detail": err, "params": {"file_path": data}}
        path = Path(data)
        if data.endswith('.xlsx'):
            if not _check_module("openpyxl"):
                return {"error_detail": "openpyxl库未安装", "params": {"library": "openpyxl"}}
            return {"df": pd.read_excel(data, engine="openpyxl", nrows=max_rows)}
        return {"df": pd.read_csv(data, nrows=max_rows)}
    if isinstance(data, list):
        if max_rows is not None and len(data) > max_rows:
            data = data[:max_rows]
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


def filter_data(file_path: Optional[str] = None, data: Optional[str] = None,
                conditions: List[Dict[str, Any]] = None,
                select_columns: Optional[List[str]] = None, max_rows: Optional[int] = None,
                sort_by: Optional[str] = None, top_n: Optional[int] = None) -> Dict[str, Any]:
    """筛选数据 — 小健 2026-06-22 拆分独立文件 — 小健 2026-06-26 删除Union — 小欧 2026-06-27 file_path+data互斥拆分"""
    if file_path and data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="file_path和data参数互斥,只能传入其中一个", hint="file_path和data只能选其一", file_path=file_path, data=data)
        return build_error(data={"error_detail": "file_path和data参数互斥,只能传入其中一个", "params": {"file_path": file_path, "data": data}}, llm_data=llm_data)
    if not file_path and not data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="file_path和data参数必须传入其中一个", hint="请提供file_path或data参数")
        return build_error(data={"error_detail": "file_path和data参数必须传入其中一个"}, llm_data=llm_data)

    if conditions is not None:
        conditions = coerce_json(conditions)
    else:
        conditions = []
    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="pandas库未安装", hint="请安装pandas库", file_path=file_path, data=data)
        return build_error(data={"error_detail": "pandas库未安装", "params": {"library": "pandas"}}, llm_data=llm_data)

    try:
        if file_path:
            loaded = _load_data_to_df(file_path, max_rows)
        else:
            parsed_data = coerce_json(data)
            if isinstance(parsed_data, list):
                loaded = _load_data_to_df(parsed_data, max_rows)
            else:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_filter_data_llm_data("error", duration_ms, detail="data参数必须是JSON数组字符串", hint="请提供JSON数组格式的数据", data=data)
                return build_error(data={"error_detail": "data参数必须是JSON数组字符串", "params": {"data_type": type(parsed_data).__name__}}, llm_data=llm_data)
        if "error_detail" in loaded:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_filter_data_llm_data("error", duration_ms, detail=loaded["error_detail"], hint="请检查数据加载路径", file_path=file_path, data=data)
            return build_error(data=loaded, llm_data=llm_data)
        df = loaded["df"]
        original_count = len(df)

        result = _build_condition_mask(df, conditions)
        if "error_detail" in result:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_filter_data_llm_data("error", duration_ms, detail=result["error_detail"], hint="请检查筛选条件", file_path=file_path, data=data, conditions=conditions)
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
            "row_count": len(rows),
            "filter_ratio": f"{len(rows)}/{original_count}",
        }
        if warnings:
            result_data["warnings"] = warnings

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("success", duration_ms, original_count, len(rows), columns,
                                                  file_path=file_path, data=data, conditions=conditions, select_columns=select_columns, sort_by=sort_by, top_n=top_n or 0, max_rows=max_rows or 0)
        # =============================================================================
        # 数据设计：original_count/filtered_count 从 data 移除，通过 llm_data.metrics 传入 summary
        # summary 示例: "筛选完成: 100行→50行"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #5 rows
        # trigger: "rows" in data — rows 是 List[list|dict]
        # handler: _format_rows(data["rows"], data.get("columns"))
        # file:    observation_formatter.py:140-142
        # ------------------------------------------------------------------------------
        return build_success(data=result_data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail=str(e), hint="筛选异常，请检查数据", file_path=file_path, data=data)
        return build_error(data={"error_detail": str(e), "params": {"data": str(data)[:200]}}, llm_data=llm_data)


__all__ = ["filter_data"]