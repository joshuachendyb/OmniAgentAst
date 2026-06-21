# -*- coding: utf-8 -*-
"""
D6: write_xlsx — 写入Excel文档

从document_tools.py拆分而来 — 小欧 2026-06-22
"""

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.tools.tool_response import build_success, build_error
from app.tools.toolhelper.common_helper import _check_module
from app.constants import ERR_WRITE_XLSX, ERR_DOC_NO_OPENPYXL
from app.utils.json_utils import coerce_json
from app.utils.logger import logger


def _build_write_xlsx_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", row_count: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """write_xlsx的llm_data构建函数 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"写入Excel失败: {detail}",
            "action": {"tool": "write_xlsx", "tool_zh": "写入Excel", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "写入Excel失败", "code": ERR_WRITE_XLSX, "detail": detail, "hint": "请检查路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入Excel成功: {file_path}, {row_count}行",
        "action": {"tool": "write_xlsx", "tool_zh": "写入Excel", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "写入Excel成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "row_count": {"value": row_count, "text": f"{row_count}行"},
        },
    }


def write_xlsx(
    file_name: str,
    data: Optional[Union[Dict[str, Any], List]] = None,
    sheet_name: str = "Sheet1",
) -> Dict[str, Any]:
    """写入Excel文件 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    data = coerce_json(data)

    if not _check_module("openpyxl"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("error", duration_ms, file_name, detail="openpyxl库未安装")
        return build_error(data={"error_detail": "openpyxl库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment

        if data is None:
            data = {"headers": [], "rows": []}
        elif isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], list):
                first_row = data[0]
                data = {"headers": first_row, "rows": data[1:]}
            elif len(data) > 0 and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [list(row.values()) for row in data]
                data = {"headers": headers, "rows": rows}
            else:
                data = {"headers": [], "rows": data}
        elif isinstance(data, dict) and "headers" not in data and "rows" not in data:
            headers = list(data.keys())
            rows = [list(data.values())]
            data = {"headers": headers, "rows": rows}

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        if "headers" in data and data["headers"]:
            headers = data["headers"]
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")

        if "rows" in data and data["rows"]:
            for row_idx, row_data in enumerate(data["rows"], 2):
                for col_idx, cell_data in enumerate(row_data, 1):
                    ws.cell(row=row_idx, column=col_idx, value=cell_data)

        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)

        row_count = len(data.get("rows", []))
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("success", duration_ms, str(path), row_count)
        return build_success(data={"file_path": str(path), "row_count": row_count}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("error", duration_ms, file_name, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)