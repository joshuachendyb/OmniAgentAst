# -*- coding: utf-8 -*-
"""
D4: read_xlsx — 读取Excel/CSV/XLS文档

从document_tools.py拆分而来 — 小欧 2026-06-22
内聚: _read_xlsx / _read_xls / _read_csv_stdlib 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import csv
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.constants import ERR_DOC_READ_XLSX
from app.utils.logger import logger


def _build_read_xlsx_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", row_count: int = 0, sheet_count: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """read_xlsx的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取Excel失败: {detail}",
            "action": {"tool": "read_xlsx", "tool_zh": "读取Excel", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取Excel失败", "code": ERR_DOC_READ_XLSX, "detail": detail, "hint": "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取Excel成功: {row_count}行, {sheet_count}个工作表",
        "action": {"tool": "read_xlsx", "tool_zh": "读取Excel", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取Excel成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "row_count": {"value": row_count, "text": f"{row_count}行"},
            "sheet_count": {"value": sheet_count, "text": f"{sheet_count}个表"},
        },
    }


def _read_xlsx_inner(file_path: str, max_rows: int = 10000) -> Dict[str, Any]:
    """读取.xlsx文件(内部) — 小欧 2026-06-22
    辅助函数: 仅返回原始dict，不含build3/llm_data — 小欧 2026-06-22"""
    try:
        from openpyxl import load_workbook

        path = Path(file_path)
        if not path.exists():
            return {"error_detail": "文件不存在", "params": {"file_path": file_path}}

        wb = load_workbook(path, read_only=True, data_only=True)
        sheet_names = wb.sheetnames
        ws = wb.active

        rows = []
        headers = []
        row_count = 0

        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows + 1:
                break
            row_data = [None if val is None else val for val in row]
            if i == 0:
                headers = [str(h) if h is not None else f"column_{j}" for j, h in enumerate(row_data)]
            else:
                rows.append(row_data)
                row_count += 1

        wb.close()
        return {"headers": headers, "rows": rows, "row_count": row_count, "sheet_names": sheet_names}
    except Exception as e:
        return {"error_detail": str(e), "params": {"file_path": file_path}}


def _read_xls_inner(file_path: str, max_rows: int = 10000) -> Dict[str, Any]:
    """读取.xls文件(内部) — 小欧 2026-06-22
    辅助函数: 仅返回原始dict，不含build3/llm_data — 小欧 2026-06-22"""
    try:
        import xlrd

        path = Path(file_path)
        if not path.exists():
            return {"error_detail": "文件不存在", "params": {"file_path": file_path}}

        wb = xlrd.open_workbook_xls(str(path))
        sheet_names = wb.sheet_names()
        ws = wb.sheet_by_index(0)

        headers = []
        rows = []
        for i in range(min(ws.nrows, max_rows)):
            row_data = [ws.cell_value(i, j) for j in range(ws.ncols)]
            if i == 0:
                headers = [str(h) if h else f"column_{j}" for j, h in enumerate(row_data)]
            else:
                rows.append(row_data)

        return {"headers": headers, "rows": rows, "row_count": len(rows), "sheet_names": sheet_names}
    except Exception as e:
        return {"error_detail": str(e), "params": {"file_path": file_path}}


def _read_csv_stdlib_inner(
    file_path: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    has_header: bool = True,
    max_rows: int = 10000,
) -> Dict[str, Any]:
    """使用标准库csv读取CSV文件(内部) — 小欧 2026-06-22
    辅助函数: 仅返回原始dict，不含build3/llm_data — 小欧 2026-06-22"""
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error_detail": "文件不存在", "params": {"file_path": file_path}}

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
            return {"error_detail": "编码不匹配", "params": {"file_path": file_path, "encodings_tried": encodings_to_try}}

        return {"headers": headers, "rows": rows, "row_count": len(rows)}
    except Exception as e:
        return {"error_detail": str(e), "params": {"file_path": file_path}}


def read_xlsx(file_name: str) -> Dict[str, Any]:
    """读取Excel/CSV/XLS文件 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件
    主函数: 负责build3+llm_data调用 — 小欧 2026-06-22"""
    path = Path(file_name)
    suffix = path.suffix.lower()
    t0 = _time_mod.perf_counter()

    if suffix == ".csv":
        result = _read_csv_stdlib_inner(file_name, encoding="utf-8", delimiter=",", has_header=True, max_rows=10000)
    elif suffix == ".xls":
        result = _read_xls_inner(file_name, max_rows=10000)
    else:
        if not _check_module("openpyxl"):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_xlsx_llm_data("error", duration_ms, file_name, detail="openpyxl库未安装")
            return build_error(data={"error_detail": "openpyxl库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)
        result = _read_xlsx_inner(file_name, max_rows=10000)

    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if "error_detail" in result:
        detail = result["error_detail"]
        llm_data = _build_read_xlsx_llm_data("error", duration_ms, file_name, detail=detail)
        return build_error(data=result, llm_data=llm_data)
    else:
        row_count = result.get("row_count", 0)
        sheet_count = len(result.get("sheet_names", []))
        llm_data = _build_read_xlsx_llm_data("success", duration_ms, file_name, row_count, sheet_count)
        return build_success(data=result, llm_data=llm_data)