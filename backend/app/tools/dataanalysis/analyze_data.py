# -*- coding: utf-8 -*-
"""
analyze_data — 对数据集进行统计分析
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
from app.tools.tool_fc_helper import _check_module
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.json_utils import coerce_json
from app.tools.tool_constants import ERR_DOC_ANALYZE_DATA


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


def _build_analyze_data_llm_data(exec_code, duration_ms, row_count=0, numeric_col_count=0, columns=None, detail="", hint="",
                                  file_path="", data="", operations=None, group_by="", sort_by="", top_n=0, max_rows=0):
    """analyze_data的llm_data构建函数 — 小健 2026-06-22 — 小欧 2026-07-05 新增user_params — 小欧 2026-07-05 加hint参数 — 小欧 2026-07-06 去掉data字段，防止大字段返回给LLM"""
    columns = columns or []
    _act_params = {}
    if file_path:
        _act_params["file_path"] = file_path
    if operations:
        _act_params["operations"] = operations
    if group_by:
        _act_params["group_by"] = group_by
    if sort_by:
        _act_params["sort_by"] = sort_by
    if top_n:
        _act_params["top_n"] = top_n
    if max_rows:
        _act_params["max_rows"] = max_rows
    _target = file_path or "数据集"
    if exec_code == "error":
        return {
            "summary": f"分析数据{_target}，失败: {detail}",
            "action": {"tool": "analyze_data", "tool_zh": "分析数据", "target": "dataset", "params": _act_params},
            "status": {"exec_code": "error", "message": "分析失败", "code": ERR_DOC_ANALYZE_DATA, "detail": detail, "hint": hint if hint else "请检查数据格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"分析数据{_target}，成功: {row_count}行, {numeric_col_count}个数值列",
        "action": {"tool": "analyze_data", "tool_zh": "分析数据", "target": "dataset", "params": _act_params},
        "status": {"exec_code": "success", "message": "分析成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"row_count": {"value": row_count, "text": f"{row_count}行"}, "numeric_cols": {"value": numeric_col_count, "text": f"{numeric_col_count}列"}},
    }


def analyze_data(file_path: Optional[str] = None, data: Optional[str] = None,
                 operations: Optional[List[str]] = None,
                 group_by: Optional[str] = None, sort_by: Optional[str] = None,
                 top_n: Optional[int] = None, max_rows: Optional[int] = None) -> Dict[str, Any]:
    """对数据集进行统计分析 — 小健 2026-06-22 拆分独立文件 — 小健 2026-06-26 删除Union — 小欧 2026-06-27 file_path+data互斥拆分"""
    if file_path and data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="file_path和data参数互斥,只能传入其中一个", hint="file_path和data只能选其一", file_path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)
    if not file_path and not data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="file_path和data参数必须传入其中一个", hint="请提供file_path或data参数")
        return build_error(data={}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="pandas库未安装", hint="请安装pandas库", file_path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)

    try:
        all_ops = ["mean", "sum", "count", "min", "max", "std"]
        if operations is None:
            operations = all_ops

        if file_path:
            # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
            # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
            is_valid, err, _ = validate_path(OpCategory.READ_FILE, file_path)
            if not is_valid:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_analyze_data_llm_data("error", duration_ms, detail=err, hint="请检查文件路径", file_path=file_path)
                return build_error(data={}, llm_data=llm_data)
            path = Path(file_path)
            read_kwargs = {}
            if max_rows is not None:
                read_kwargs["nrows"] = max_rows
            if file_path.endswith('.xlsx'):
                if not _check_module("openpyxl"):
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="openpyxl库未安装", hint="请安装openpyxl库", file_path=file_path)
                    return build_error(data={}, llm_data=llm_data)
                df = pd.read_excel(file_path, engine="openpyxl", **({k: v for k, v in read_kwargs.items() if k == 'nrows'}))
            else:
                df = pd.read_csv(file_path, **read_kwargs)
        else:
            parsed_data = coerce_json(data)
            if isinstance(parsed_data, list):
                df = pd.DataFrame(parsed_data)
            else:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="data参数必须是JSON数组格式的字符串", hint="请提供JSON数组格式的数据", data=data)
                return build_error(data={}, llm_data=llm_data)

        total_count = len(df)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_analyze_data_llm_data("success", duration_ms, total_count, 0, df.columns.tolist(),
                                                      file_path=file_path, data=data, operations=operations, group_by=group_by, sort_by=sort_by, top_n=top_n or 0, max_rows=max_rows or 0)
            # ---- observation_formatter route -------------------------------------------
            # branch: #20 analyze_data(transposed) — 无数值列场景
            # trigger: "statistics" in data — statistics 为 {} 空 dict
            # handler: _format_analyze_data(data) — 首行 列名 | 总数 转置表
            # file:    observation_formatter.py:201-202
            # ------------------------------------------------------------------------------
            # =============================================================================
            # 数据设计：row_count 从 data 移除，通过 llm_data.metrics 传入 summary
            # summary 示例: "分析完成: X行, Y个数值列"
            # — 小欧 2026-07-06 18:46:13
            # =============================================================================
            return build_success(data={"columns": df.columns.tolist(), "statistics": {}}, llm_data=llm_data)

        result = {"columns": numeric_cols, "row_count": total_count}
        if sort_by and sort_by in df.columns:
            df = df.sort_values(by=sort_by, ascending=True)
        if top_n and top_n > 0:
            df = df.head(top_n)

        result.update(_compute_stats(df, numeric_cols, operations, all_ops, group_by=group_by))

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("success", duration_ms, len(df), len(numeric_cols), df.columns.tolist(),
                                                  file_path=file_path, data=data, operations=operations, group_by=group_by, sort_by=sort_by, top_n=top_n or 0, max_rows=max_rows or 0)
        # ---- observation_formatter route -------------------------------------------
        # branch: #20 analyze_data(transposed) — 有数值列场景
        # trigger: "statistics" in data or "grouped_statistics" in data
        # handler: _format_analyze_data(data) — 每列名 均值/求和/计数 转置表
        # file:    observation_formatter.py:201-202
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail=str(e), hint="分析异常，请检查数据", file_path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)


__all__ = ["analyze_data"]