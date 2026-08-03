
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-21 - 小欧 - 入参即信任: top_n/max_rows 加 ge=1,le=1000 校验
# 2026-07-24 - 小欧 - str(conditions)[:200] → FILTER_DATA_OUTPARM_LIMIT_CONDITIONS(魔数→命名常量)
# 2026-07-25 - 小欧 - 删除max_rows: top_n唯一行数控制,_load_data_to_df不再限制读取
# 2026-07-25 - 小欧 - Bug修: head(top_n)截断加 truncated=True/truncated_reason, _load_data_to_df 加 TODO 大文件安全网注释
# 2026-07-25 - 小欧 - em dash替换为ascii连字符- (欧阳建议，消除SyntaxError嫌疑)
# 2026-07-26 - 小欧 - 加nrows=100000硬安全网防OOM+before变量在else分支正确定义(欧阳报告问题2/3修复)
# 2026-07-26 - 小欧 - 删除nrows=100000:OOM让异常自然抛出被except捕获报error给LLM,不加硬限制(老陈方向)
# 2026-07-26 - 小欧 - OOD重构:数据加载_load_data_to_df抽取至data_loader.load_data_to_df公用函数(analyze_data/filter_data共享)
# 2026-07-26 - 小欧 - 迁移: hint_for_data_error导入从tool_constants改为file_path_checker(配合函数迁移)
"""
filter_data  按条件筛选/过滤数据
【2026-06-22 小健】从 dataanalysis_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import time as _time_mod
from typing import Dict, Any, List, Optional

import pandas as pd

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module, _serialize_rows
from app.tools.dataanalysis.data_loader import load_data_to_df, validate_top_n
from app.utils.json_utils import coerce_json
from app.tools.tool_constants import ERR_FILTER_INVALID, FILTER_DATA_OUTPARM_LIMIT_CONDITIONS
from app.tools.validate.file_path_checker import hint_for_data_error


def _build_filter_data_llm_data(exec_code, duration_ms, original_count=0, filtered_count=0, columns=None, detail="", hint="",
                                 path="", data="", conditions=None, select_columns=None, sort_by="", top_n=0):
    """filter_data的llm_data构建函数 - 小健 2026-06-22 - 小欧 2026-07-05 新增user_params - 小欧 2026-07-05 加hint参数 - 小欧 2026-07-06 去掉data/conditions字段，防止大字段返回给LLM - 小欧 2026-07-11 路径参数统一为path"""
    columns = columns or []
    _act_params = {}
    if path:
        _act_params["path"] = path
    if select_columns:
        _act_params["select_columns"] = select_columns
    if sort_by:
        _act_params["sort_by"] = sort_by
    if top_n:
        _act_params["top_n"] = top_n
    _target = path or "数据集"
    if exec_code == "error":
        return {
            "summary": f"筛选数据{_target}，失败: {detail}",
            "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": _act_params},
            "status": {"exec_code": "error", "message": "筛选失败", "code": ERR_FILTER_INVALID, "detail": detail, "hint": hint if hint else "请检查条件和数据"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"筛选数据{_target}，成功: 从{original_count}行筛选出{filtered_count}行",
        "action": {"tool": "filter_data", "tool_zh": "筛选数据", "target": "dataset", "params": _act_params},
        "status": {"exec_code": "success", "message": "筛选成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"original_count": {"value": original_count, "text": f"{original_count}行"}, "filtered_count": {"value": filtered_count, "text": f"{filtered_count}行"}},
    }



def _build_condition_mask(df: "pd.DataFrame", conditions: List[Dict[str, Any]]) -> dict:
    """构建过滤掩码 - 小沈 2026-05-25"""
    operator_map = {"eq": "__eq__", "ne": "__ne__", "gt": "__gt__", "gte": "__ge__", "lt": "__lt__", "lte": "__le__"}
    valid_operators = set(operator_map.keys()) | {"in", "contains", "not_contains"}
    mask = pd.Series([True] * len(df), index=df.index)
    warnings: List[str] = []

    for cond in conditions:
        column = cond.get("column")
        operator = cond.get("operator", "eq")
        value = cond.get("value")

        if not column:
            return {"error_detail": f"条件缺少column字段: {cond}", "params": {"conditions": str(conditions)[:FILTER_DATA_OUTPARM_LIMIT_CONDITIONS]}}
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


def filter_data(path: Optional[str] = None, data: Optional[str] = None,
                conditions: List[Dict[str, Any]] = None,
                select_columns: Optional[List[str]] = None,
                sort_by: Optional[str] = None, top_n: Optional[int] = None) -> Dict[str, Any]:
    """筛选数据 - 小健 2026-06-22 拆分独立文件 - 小健 2026-06-26 删除Union - 小欧 2026-06-27 file_path+data互斥拆分 - 小欧 2026-07-11 路径参数统一为path"""
    # 路径参数统一为path,桥接到内部变量file_path - 小欧 2026-07-11
    file_path = path
    if file_path and data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="path和data参数互斥,只能传入其中一个", hint="path和data只能选其一", path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)
    if not file_path and not data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="path和data参数必须传入其中一个", hint="请提供path或data参数")
        return build_error(data={}, llm_data=llm_data)

    if conditions is not None:
        conditions = coerce_json(conditions)
    else:
        conditions = []

    err_msg = validate_top_n(top_n)
    if err_msg:
        llm_data = _build_filter_data_llm_data("error", 0, detail=err_msg, hint="top_n参数必须设置在1-1000之间", path=file_path, data=data, conditions=conditions)
        return build_error(data={}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail="pandas库未安装", hint="请安装pandas库", path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)

    try:
        if file_path:
            loaded = load_data_to_df(file_path)
        else:
            parsed_data = coerce_json(data)
            if isinstance(parsed_data, list):
                loaded = load_data_to_df(parsed_data)
            else:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_filter_data_llm_data("error", duration_ms, detail="data参数必须是JSON数组格式的字符串", hint="请提供JSON数组格式的数据", data=data)
                return build_error(data={}, llm_data=llm_data)
        if "error_detail" in loaded:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_filter_data_llm_data("error", duration_ms, detail=loaded["error_detail"], hint="请检查数据加载路径", path=file_path, data=data)
            return build_error(data={}, llm_data=llm_data)
        df = loaded["df"]
        original_count = len(df)

        result = _build_condition_mask(df, conditions)
        if "error_detail" in result:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_filter_data_llm_data("error", duration_ms, detail=result["error_detail"], hint="请检查筛选条件", path=file_path, data=data, conditions=conditions)
            return build_error(data={}, llm_data=llm_data)
        filtered_df = df[result["mask"]]
        warnings = result["warnings"]

        if select_columns:
            available_cols = [c for c in select_columns if c in filtered_df.columns]
            if available_cols:
                filtered_df = filtered_df[available_cols]

        if sort_by and sort_by in filtered_df.columns:
            filtered_df = filtered_df.sort_values(by=sort_by, ascending=True)

        if top_n and top_n > 0:
            before = len(filtered_df)
            filtered_df = filtered_df.head(top_n)
            # 工具层截断标记,供观察层区分"数据刚好这么多"vs"被top_n截断" - 小欧 2026-07-25
            tool_truncated = before > top_n
        else:
            before = len(filtered_df)
            tool_truncated = False

        columns = filtered_df.columns.tolist()
        rows = _serialize_rows(filtered_df)
        result_data = {"columns": columns, "rows": rows}
        if tool_truncated:
            result_data["truncated"] = True
            result_data["truncated_reason"] = f"结果{before}行，仅返回前{top_n}行"
        if warnings:
            result_data["warnings"] = warnings

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("success", duration_ms, original_count, len(rows), columns,
                                                   path=file_path, data=data, conditions=conditions, select_columns=select_columns, sort_by=sort_by, top_n=top_n or 0)
        # =============================================================================
        # 数据设计：original_count/filtered_count 从 data 移除，通过 llm_data.metrics 传入 summary
        # summary 示例: "筛选完成: 100行→50行"
        # - 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #5 rows
        # trigger: "rows" in data - rows 是 List[list|dict]
        # handler: _format_rows(data["rows"], data.get("columns"))
        # file:    observation_formatter.py:140-142
        # ------------------------------------------------------------------------------
        return build_success(data=result_data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_filter_data_llm_data("error", duration_ms, detail=str(e), hint=hint_for_data_error(e), path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)


__all__ = ["filter_data"]

