# -*- coding: utf-8 -*-
"""
D5: write_docx — 写入Word文档

从document_tools.py拆分而来 — 小欧 2026-06-22

"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import re
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.tools.file_type_checker import check_for_document_tool
from app.tools.tool_constants import ERR_WRITE_DOCX
from app.tools.validate.tools_file_path_checker import validate_path_for_write
from app.utils.logger import logger
from app.utils.table_helper import parse_markdown_table, calculate_column_widths, get_table_header_style_config


def _set_docx_table_style(table):
    """设置表格边框和表头样式 — 小健 2026-06-24"""
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    from docx.shared import RGBColor, Pt
    
    tbl = table._tbl
    tblPr = tbl.tblPr if tbl.tblPr is not None else OxmlElement('w:tblPr')
    tblBorders = OxmlElement('w:tblBorders')
    for border_name in ['top', 'left', 'bottom', 'right', 'insideH', 'insideV']:
        border = OxmlElement(f'w:{border_name}')
        border.set(qn('w:val'), 'single')
        border.set(qn('w:sz'), '4')
        border.set(qn('w:color'), '000000')
        tblBorders.append(border)
    tblPr.append(tblBorders)
    if tbl.tblPr is None:
        tbl.insert(0, tblPr)
    
    header_config = get_table_header_style_config()
    if len(table.rows) > 0:
        for cell in table.rows[0].cells:
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.bold = header_config["bold"]
                    run.font.size = Pt(header_config["font_size"])
            tcPr = cell._tc.get_or_add_tcPr()
            shd = OxmlElement('w:shd')
            shd.set(qn('w:fill'), header_config["bg_color"])
            tcPr.append(shd)
            for para in cell.paragraphs:
                for run in para.runs:
                    run.font.color.rgb = RGBColor(255, 255, 255)


def _set_docx_column_widths(table, table_data):
    """设置列宽自适应 — 小健 2026-06-24"""
    from docx.shared import Inches
    
    if not table_data or not table_data[0]:
        return
    
    col_widths = calculate_column_widths(table_data, total_width=6.0)
    for ci, width in enumerate(col_widths):
        if ci < len(table.columns):
            for cell in table.columns[ci].cells:
                cell.width = Inches(width)


def _build_write_docx_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", detail: str = "",
) -> Dict[str, Any]:
    """write_docx的llm_data构建函数 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"写入Word失败: {detail}",
            "action": {"tool": "write_docx", "tool_zh": "写入Word", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "写入Word失败", "code": ERR_WRITE_DOCX, "detail": detail, "hint": "请检查路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入Word成功: {file_path}",
        "action": {"tool": "write_docx", "tool_zh": "写入Word", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "写入Word成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }




def write_docx(
    file_name: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    table_data: Optional[List[List[str]]] = None,
) -> Dict[str, Any]:
    """写入Word文档 — 小健 2026-06-24 支持Markdown表格+table_data互斥 — 小欧 2026-06-24 增加文件类型前置检查"""
    t0 = _time_mod.perf_counter()

    # 路径业务级前置检查
    is_valid, err, warn = validate_path_for_write(file_name)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_docx_llm_data("error", duration_ms, file_name, detail=err)
        return build_error(data={"error_detail": err, "params": {"file_name": file_name}}, llm_data=llm_data)
    if warn:
        logger.warning(f"[write_docx] {warn}")

    # 文件类型前置检查（write操作允许创建新文件） — 小欧 2026-06-24
    is_valid, error_detail, suggested_tool = check_for_document_tool(file_name, allow_create=True)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_docx_llm_data("error", duration_ms, file_name, detail=error_detail)
        return build_error(data={"error_detail": error_detail, "params": {"file_name": file_name}}, llm_data=llm_data)

    if not _check_module("docx"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_docx_llm_data("error", duration_ms, file_name, detail="python-docx库未安装")
        return build_error(data={"error_detail": "python-docx库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        from docx import Document

        doc = Document()

        if title:
            doc.add_heading(title, 0)

        if content:
            lines = content.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].rstrip()
                if not line:
                    i += 1
                    continue
                
                if line.startswith('# '):
                    doc.add_heading(line[2:], 1)
                elif line.startswith('## '):
                    doc.add_heading(line[3:], 2)
                elif line.startswith('### '):
                    doc.add_heading(line[4:], 3)
                elif line.startswith('#### '):
                    doc.add_heading(line[5:], 4)
                elif line.startswith('##### '):
                    doc.add_heading(line[6:], 5)
                elif line.startswith('- ') or line.startswith('* '):
                    doc.add_paragraph(line[2:], style='List Bullet')
                elif re.match(r'^\d+\.\s', line):
                    doc.add_paragraph(re.sub(r'^\d+\.\s', '', line), style='List Number')
                elif line.startswith('|') and '|' in line[1:]:
                    table_rows, i = parse_markdown_table(lines, i)
                    if table_rows:
                        t = doc.add_table(rows=len(table_rows), cols=len(table_rows[0]))
                        for ri, row_data in enumerate(table_rows):
                            for ci, cell_text in enumerate(row_data):
                                t.rows[ri].cells[ci].text = str(cell_text)
                        _set_docx_table_style(t)
                        _set_docx_column_widths(t, table_rows)
                    continue
                else:
                    doc.add_paragraph(line)
                i += 1
        
        if table_data:
            if table_data and len(table_data) > 0 and len(table_data[0]) > 0:
                t = doc.add_table(rows=len(table_data), cols=len(table_data[0]))
                for ri, row_data in enumerate(table_data):
                    for ci, cell_text in enumerate(row_data):
                        t.rows[ri].cells[ci].text = str(cell_text)
                _set_docx_table_style(t)
                _set_docx_column_widths(t, table_data)

        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(path)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_docx_llm_data("success", duration_ms, str(path))
        return build_success(data={"file_path": str(path)}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_docx_llm_data("error", duration_ms, file_name, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)