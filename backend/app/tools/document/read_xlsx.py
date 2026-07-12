# -*- coding: utf-8 -*-
"""
D4: read_xlsx — 读取Excel/CSV/XLS文档

从document_tools.py拆分而来 — 小欧 2026-06-22
内聚: _read_xlsx / _read_csv_stdlib 辅助函数 — 小欧 2026-06-24 移除._read_xls(不支持.xls)
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import csv
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.tools.validate.file_type_checker import check_for_document_tool
from app.tools.validate.file_path_checker import hint_for_read_error
from app.tools.tool_constants import ERR_DOC_READ_XLSX

from app.logger import logger


def _build_read_xlsx_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", row_count: int = 0, sheet_count: int = 0, detail: str = "",
    user_sheet_name: str = "", hint: str = "",
) -> Dict[str, Any]:
    """read_xlsx的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    if exec_code == "error":
        _act_params = {"file_path": file_path}
        if user_sheet_name:
            _act_params["sheet_name"] = user_sheet_name
        return {
            "summary": f"读取Excel{file_path}，失败: {detail}",
            "action": {"tool": "read_xlsx", "tool_zh": "读取Excel", "target": file_path, "params": _act_params},
            "status": {"exec_code": "error", "message": "读取Excel失败", "code": ERR_DOC_READ_XLSX, "detail": detail, "hint": hint if hint else "读取失败,详见错误明细"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _act_params = {"file_path": file_path}
    if user_sheet_name:
        _act_params["sheet_name"] = user_sheet_name
    return {
        "summary": f"读取Excel{file_path}，成功: {row_count}行，{sheet_count}个工作表",
        "action": {"tool": "read_xlsx", "tool_zh": "读取Excel", "target": file_path, "params": _act_params},
        "status": {"exec_code": "success", "message": "读取Excel成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "row_count": {"value": row_count, "text": f"{row_count}行"},
            "sheet_count": {"value": sheet_count, "text": f"{sheet_count}个表"},
        },
    }


def _read_xlsx_inner(file_path: str, max_rows: int = 10000, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """读取.xlsx文件(内部) — 小欧 2026-06-22
    辅助函数: 仅返回原始dict，不含build3/llm_data — 小欧 2026-06-22
    参数: sheet_name - 指定工作表名，None则读取所有工作表 — 小健 2026-06-24"""
    def _serialize_val(val):
        """单值序列化: None→None, datetime→isoformat, 其他原样 — 北京老陈 2026-07-03"""
        if val is None:
            return None
        if hasattr(val, 'isoformat'):
            return val.isoformat()
        return val

    from openpyxl import load_workbook

    path = Path(file_path)

    wb = load_workbook(path, read_only=True, data_only=True)
    try:
        sheet_names = wb.sheetnames

        if sheet_name:
            if sheet_name not in sheet_names:
                return {"error_detail": f"工作表不存在: {sheet_name}", "hint": f"工作表 {sheet_name} 不存在,请确认工作表名称是否正确", "params": {"file_path": file_path, "sheet_name": sheet_name}}
            target_sheets = [sheet_name]
        else:
            target_sheets = sheet_names

        all_sheets_data = []
        total_rows = 0

        for sheet in target_sheets:
            ws = wb[sheet]
            rows = []
            headers = []
            row_count = 0

            for i, row in enumerate(ws.iter_rows(values_only=True)):
                if i >= max_rows + 1:
                    break
                row_data = [_serialize_val(val) for val in row]
                if i == 0:
                    headers = [str(h) if h is not None else f"column_{j}" for j, h in enumerate(row_data)]
                else:
                    rows.append(row_data)
                    row_count += 1

            sheet_data = {
                "sheet_name": sheet,
                "headers": headers,
                "rows": rows,
                "row_count": row_count,
            }
            all_sheets_data.append(sheet_data)
            total_rows += row_count
    finally:
        wb.close()

    if len(all_sheets_data) == 1:
        result = all_sheets_data[0]
        result["sheet_names"] = sheet_names
        return result
    else:
        return {
            "sheets": all_sheets_data,
            "sheet_names": sheet_names,
            "row_count": total_rows,
        }


def _read_csv_stdlib_inner(
    file_path: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    has_header: bool = True,
    max_rows: int = 10000,
) -> Dict[str, Any]:
    """使用标准库csv读取CSV文件(内部) — 小欧 2026-06-22
    辅助函数: 仅返回原始dict，不含build3/llm_data — 小欧 2026-06-22"""
    path = Path(file_path)

    rows = []
    headers = []
    encodings_to_try = [encoding, "gbk", "gb2312", "latin-1"] if encoding == "utf-8" else [encoding, "utf-8", "latin-1"]
    read_ok = False
    for enc in encodings_to_try:
        try:
            with open(path, "r", encoding=enc, newline="") as f:
                reader = csv.reader(f, delimiter=delimiter)
                for i, row in enumerate(reader):
                    if i >= max_rows:
                        break
                    if i == 0:
                        if has_header:
                            headers = row
                        else:
                            headers = [f"col_{j}" for j in range(len(row))]
                            rows.append(row)
                    else:
                        rows.append(row)
            read_ok = True
            break
        except UnicodeDecodeError:
            continue
    if not read_ok:
        return {"error_detail": "编码不匹配", "hint": "无法以常见编码读取,请确认文件编码格式", "params": {"file_path": file_path, "encodings_tried": encodings_to_try}}

    return {"headers": headers, "rows": rows, "row_count": len(rows)}


def read_xlsx(path: str, sheet_name: Optional[str] = None) -> Dict[str, Any]:
    """读取Excel/CSV(.xlsx/.csv)文件 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件
    主函数: 负责build3+llm_data调用 — 小欧 2026-06-22
    参数: sheet_name - 指定工作表名（仅.xlsx），None则读取所有工作表 — 小健 2026-06-24
    小欧 2026-06-24 增加文件类型前置检查（.csv跳过检查） — 小欧 2026-06-24 移除.xls死代码"""
    path = Path(path)
    suffix = path.suffix.lower()
    t0 = _time_mod.perf_counter()

    # 文件类型前置检查（.csv由本工具处理，跳过检查） — 小欧 2026-06-24
    if suffix != ".csv":
        is_valid, error_detail, suggested_tool = check_for_document_tool(str(path))
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            _sn = sheet_name or ""
            if suggested_tool:
                _hint = f"建议使用{suggested_tool}工具"
            elif suggested_tool == "":
                _hint = "请检查文件路径和文件名是否正确"
            else:
                _hint = "文件类型不匹配,请使用.xlsx或.csv格式"
            # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
            # 避免action.target持有Path对象触发观察格式化len()崩溃
            llm_data = _build_read_xlsx_llm_data("error", duration_ms, str(path), detail=error_detail, user_sheet_name=_sn, hint=_hint)
            return build_error(data={}, llm_data=llm_data)

    if suffix == ".csv":
        try:
            result = _read_csv_stdlib_inner(path, encoding="utf-8", delimiter=",", has_header=True, max_rows=10000)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
            # 避免action.target持有Path对象触发观察格式化len()崩溃
            llm_data = _build_read_xlsx_llm_data("error", duration_ms, str(path), detail=str(e), user_sheet_name=sheet_name or "", hint=hint_for_read_error(e, str(path)))
            return build_error(data={}, llm_data=llm_data)
    else:
        if not _check_module("openpyxl"):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
            # 避免action.target持有Path对象触发观察格式化len()崩溃
            llm_data = _build_read_xlsx_llm_data("error", duration_ms, str(path), detail="openpyxl库未安装", user_sheet_name=sheet_name or "", hint="请安装openpyxl库")
            return build_error(data={}, llm_data=llm_data)
        try:
            result = _read_xlsx_inner(path, max_rows=10000, sheet_name=sheet_name)
        except Exception as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
            # 避免action.target持有Path对象触发观察格式化len()崩溃
            llm_data = _build_read_xlsx_llm_data("error", duration_ms, str(path), detail=str(e), user_sheet_name=sheet_name or "", hint=hint_for_read_error(e, str(path)))
            return build_error(data={}, llm_data=llm_data)

    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if "error_detail" in result:
        detail = result["error_detail"]
        # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
        # 避免action.target持有Path对象触发观察格式化len()崩溃
        llm_data = _build_read_xlsx_llm_data("error", duration_ms, str(path), detail=detail, user_sheet_name=sheet_name or "", hint=result.get("hint", ""))
        return build_error(data=result, llm_data=llm_data)
    else:
        row_count = result.get("row_count", 0)
        sheet_count = len(result.get("sheet_names", []))
        result.pop("row_count", None)
        # 小欧 2026-07-12: 此处path经Path()重赋值为WindowsPath,须str()化后传入builder,
        # 避免action.target持有Path对象触发观察格式化len()崩溃
        llm_data = _build_read_xlsx_llm_data("success", duration_ms, str(path), row_count, sheet_count, user_sheet_name=sheet_name or "")
        # =============================================================================
        # 数据设计：row_count/sheet_count 从 data 移除，通过 llm_data.metrics 传入 summary
        # summary 示例: "读取Excel成功: 100行, 3个工作表"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #2b flat table (单sheet/CSV) / #21 scalar fallback (多sheet)
        # trigger: "headers" in data and "rows" in data — 单sheet有headers+rows
        # handler: _format_table(data["headers"], data["rows"])
        # note:    多sheet返回 {"sheets": [...], "sheet_names": [...]}, 无headers/rows,
        #          走 scalar fallback → _format_scalar_data(data)
        # file:    observation_formatter.py:136-138
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)