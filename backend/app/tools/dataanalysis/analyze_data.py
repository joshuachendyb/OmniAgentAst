# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-21 - 小欧 - 入参即信任: top_n/max_rows 加 ge=1,le=1000 校验
# 2026-07-25 - 小欧 - 删除max_rows: top_n唯一行数控制,统计在head之前计算,读全部数据
# 2026-07-25 - 小欧 - Bug修: llm_data.row_count 统一为 total_count(全量行数,非head后), L142 加 TODO 大文件安全网注释
# 2026-07-25 - 小欧 - em dash替换为ascii连字符- (欧阳建议，消除SyntaxError嫌疑)
# 2026-07-26 - 小欧 - 加nrows=100000硬安全网防OOM(欧阳报告问题2修复)
# 2026-07-26 - 小欧 - 删除nrows=100000:OOM让异常自然抛出被except捕获报error给LLM,不加硬限制(老陈方向)
# 2026-07-26 - 小欧 - OOD重构:数据加载/convert_pd_value抽取至data_loader公用函数(analyze_data/filter_data共享),内联数据加载改用load_data_to_df
# 2026-07-26 - 小欧 - 迁移: hint_for_data_error导入从tool_constants改为file_path_checker(配合函数迁移)
# 2026-07-31 - 小欧 - Bug⑫修复: group_by/sort_by列不存在时抛明确错误(原静默退回非分组统计/静默跳过排序, 误导LLM) | py_compile ✓
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
"""
analyze_data  对数据集进行统计分析
【2026-06-22 小健】从 dataanalysis_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import time as _time_mod
from typing import Dict, Any, List, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.utils.json_utils import coerce_json
from app.tools.tool_constants import ERR_DOC_ANALYZE_DATA
from app.tools.toolhelper.error_hints import hint_for_data_error
from app.tools.dataanalysis.data_loader import load_data_to_df, convert_pd_value, validate_top_n



def _compute_stats(df: "pd.DataFrame", numeric_cols: List[str], operations: List[str],
                   all_ops: List[str], *, group_by: Optional[str] = None) -> Dict[str, Any]:
    """统一分组/非分组统计计算 - 小沈 2026-05-25
       2026-07-31 小欧: Bug⑫修复 — group_by列不存在时抛ValueError, 不再静默退回非分组统计
    """
    if group_by:
        if group_by not in df.columns:
            raise ValueError(f"group_by列不存在: {group_by}")
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
                    result[group_key][op] = convert_pd_value(val)
                except Exception:
                    result[group_key][op] = None
        return {"grouped_statistics": result}

    statistics = {}
    for op in operations:
        if op not in all_ops:
            continue
        try:
            val = getattr(df[numeric_cols], op)()
            statistics[op] = convert_pd_value(val)
        except Exception:
            statistics[op] = None
    return {"statistics": statistics}


def _build_analyze_data_llm_data(exec_code, duration_ms, row_count=0, numeric_col_count=0, columns=None, detail="", hint="",
                                  path="", data="", operations=None, group_by="", sort_by="", top_n=0):
    """analyze_data的llm_data构建函数 - 小健 2026-06-22 - 小欧 2026-07-05 新增user_params - 小欧 2026-07-05 加hint参数 - 小欧 2026-07-06 去掉data字段，防止大字段返回给LLM - 小欧 2026-07-11 路径参数统一为path"""
    columns = columns or []
    _act_params = {}
    if path:
        _act_params["path"] = path
    if operations:
        _act_params["operations"] = operations
    if group_by:
        _act_params["group_by"] = group_by
    if sort_by:
        _act_params["sort_by"] = sort_by
    if top_n:
        _act_params["top_n"] = top_n
    _target = path or "数据集"
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


def analyze_data(path: Optional[str] = None, data: Optional[str] = None,
                 operations: Optional[List[str]] = None,
                 group_by: Optional[str] = None, sort_by: Optional[str] = None,
                 top_n: Optional[int] = None) -> Dict[str, Any]:
    """对数据集进行统计分析 - 小健 2026-06-22 拆分独立文件 - 小健 2026-06-26 删除Union - 小欧 2026-06-27 file_path+data互斥拆分 - 小欧 2026-07-11 路径参数统一为path"""
    # 路径参数统一为path,桥接到内部变量file_path - 小欧 2026-07-11
    file_path = path
    if file_path and data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="path和data参数互斥,只能传入其中一个", hint="path和data只能选其一", path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)
    if not file_path and not data:
        t0 = _time_mod.perf_counter()
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="path和data参数必须传入其中一个", hint="请提供path或data参数")
        return build_error(data={}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    err_msg = validate_top_n(top_n)
    if err_msg:
        llm_data = _build_analyze_data_llm_data("error", 0, detail=err_msg, hint="top_n参数必须设置在1-1000之间", path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    if not _check_module("pandas"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="pandas库未安装", hint="请安装pandas库", path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)

    try:
        all_ops = ["mean", "sum", "count", "min", "max", "std"]
        if operations is None:
            operations = all_ops

        if file_path:
            loaded = load_data_to_df(file_path)
        else:
            parsed_data = coerce_json(data)
            if isinstance(parsed_data, list):
                loaded = load_data_to_df(parsed_data)
            else:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_analyze_data_llm_data("error", duration_ms, detail="data参数必须是JSON数组格式的字符串", hint="请提供JSON数组格式的数据", data=data)
                return build_error(data={}, llm_data=llm_data)
        if "error_detail" in loaded:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_analyze_data_llm_data("error", duration_ms, detail=loaded["error_detail"], hint="请检查数据加载路径", path=file_path)
            return build_error(data={}, llm_data=llm_data)
        df = loaded["df"]

        total_count = len(df)
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        if not numeric_cols:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_analyze_data_llm_data("success", duration_ms, total_count, 0, df.columns.tolist(),
                                                       path=file_path, data=data, operations=operations, group_by=group_by, sort_by=sort_by, top_n=top_n or 0)
            # ---- observation_formatter route -------------------------------------------
            # branch: #20 analyze_data(transposed) - 无数值列场景
            # trigger: "statistics" in data - statistics 为 {} 空 dict
            # handler: _format_analyze_data(data) - 首行 列名 | 总数 转置表
            # file:    observation_formatter.py:201-202
            # ------------------------------------------------------------------------------
            # =============================================================================
            # 数据设计：row_count 从 data 移除，通过 llm_data.metrics 传入 summary
            # summary 示例: "分析完成: X行, Y个数值列"
            # - 小欧 2026-07-06 18:46:13
            # =============================================================================
            return build_success(data={"columns": df.columns.tolist(), "statistics": {}}, llm_data=llm_data)

        result = {"columns": numeric_cols, "row_count": total_count}
        # 2026-07-31 小欧: Bug⑫关联 — sort_by列不存在同样抛明确错误, 防静默跳过排序误导LLM
        if sort_by:
            if sort_by not in df.columns:
                raise ValueError(f"sort_by列不存在: {sort_by}")
            df = df.sort_values(by=sort_by, ascending=True)

        # 先统计（在完整数据上）
        result.update(_compute_stats(df, numeric_cols, operations, all_ops, group_by=group_by))

        # 再截断输出
        if top_n and top_n > 0:
            df = df.head(top_n)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("success", duration_ms, total_count, len(numeric_cols), df.columns.tolist(),
                                                   path=file_path, data=data, operations=operations, group_by=group_by, sort_by=sort_by, top_n=top_n or 0)
        # ---- observation_formatter route -------------------------------------------
        # branch: #20 analyze_data(transposed) - 有数值列场景
        # trigger: "statistics" in data or "grouped_statistics" in data
        # handler: _format_analyze_data(data) - 每列名 均值/求和/计数 转置表
        # file:    observation_formatter.py:201-202
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_analyze_data_llm_data("error", duration_ms, detail=str(e), hint=hint_for_data_error(e), path=file_path, data=data)
        return build_error(data={}, llm_data=llm_data)


__all__ = ["analyze_data"]
