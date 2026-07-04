# -*- coding: utf-8 -*-
"""
D6: write_xlsx — 写入Excel文档

从document_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.tools.file_type_checker import check_for_document_tool
from app.tools.tool_constants import ERR_WRITE_XLSX, ERR_DOC_NO_OPENPYXL
from app.utils.json_utils import coerce_json
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger
from app.utils.table_helper import calculate_column_widths, get_table_header_style_config


def _set_xlsx_table_style(ws):
    """设置Excel表格样式（表头背景色、数据单元格对齐和边框） — 小健 2026-06-24"""
    from openpyxl.styles import PatternFill, Alignment, Border, Side, Font
    from openpyxl.utils import get_column_letter
    
    header_config = get_table_header_style_config()
    header_fill = PatternFill(
        start_color=header_config["bg_color"],
        end_color=header_config["bg_color"],
        fill_type="solid"
    )
    
    data_alignment = Alignment(horizontal="left", vertical="center")
    data_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    for col_idx in range(1, ws.max_column + 1):
        header_cell = ws.cell(row=1, column=col_idx)
        header_cell.fill = header_fill
        header_cell.font = Font(
            bold=header_config["bold"],
            color=header_config["text_color"]
        )
        
        for row_idx in range(2, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.alignment = data_alignment
            cell.border = data_border


def _adjust_xlsx_column_width(ws):
    """调整Excel列宽自适应 — 小健 2026-06-24 — 小欧 2026-06-24 修复中文字符宽度"""
    from openpyxl.utils import get_column_letter
    
    def _display_width(s):
        """计算字符串显示宽度，中文字符占2宽度 — 小欧 2026-06-24"""
        width = 0
        for ch in str(s):
            if '\u4e00' <= ch <= '\u9fff' or '\u3000' <= ch <= '\u303f' or '\uff00' <= ch <= '\uffef':
                width += 2
            else:
                width += 1
        return width
    
    for col_idx in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for row_idx in range(1, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value is not None:
                max_len = max(max_len, _display_width(cell.value))
        ws.column_dimensions[col_letter].width = max(max_len + 2, 8)


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
    data: Optional[List[Dict[str, Any]]] = None,
    sheet_name: str = "Sheet1",
) -> Dict[str, Any]:
    """写入Excel文件 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化 — 小欧 2026-06-24 增加文件类型前置检查"""
    t0 = _time_mod.perf_counter()

    # 工具层校验：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.WRITE, file_name)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("error", duration_ms, file_name, detail=err)
        return build_error(data={"error_detail": err, "params": {"file_name": file_name}}, llm_data=llm_data)
    if warn:
        logger.warning(f"[write_xlsx] {warn}")

    # 文件类型前置检查（write操作允许创建新文件） — 小欧 2026-06-24
    is_valid, error_detail, suggested_tool = check_for_document_tool(file_name, allow_create=True)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("error", duration_ms, file_name, detail=error_detail)
        return build_error(data={"error_detail": error_detail, "params": {"file_name": file_name}}, llm_data=llm_data)

    data = coerce_json(data)

    if not _check_module("openpyxl"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("error", duration_ms, file_name, detail="openpyxl库未安装")
        return build_error(data={"error_detail": "openpyxl库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment

        if data is None:
            data = []
        
        headers = []
        rows = []
        if len(data) > 0:
            # KISS-DIRECT: 一行收集所有key，避免列不一致数据丢失 — 小健 2026-06-24
            headers = list(dict.fromkeys(k for row in data for k in row.keys()))
            # 按表头顺序填充，缺失填None
            rows = [[row.get(key) for key in headers] for row in data]

        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name

        if headers:
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = Font(bold=True)
                cell.alignment = Alignment(horizontal="center")

        if rows:
            for row_idx, row_data in enumerate(rows, 2):
                for col_idx, cell_data in enumerate(row_data, 1):
                    ws.cell(row=row_idx, column=col_idx, value=cell_data)
        
        if headers or rows:
            _set_xlsx_table_style(ws)
            _adjust_xlsx_column_width(ws)

        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        wb.save(path)

        row_count = len(rows)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("success", duration_ms, str(path), row_count)
        return build_success(data={"file_path": str(path), "row_count": row_count}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_xlsx_llm_data("error", duration_ms, file_name, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)