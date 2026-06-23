# -*- coding: utf-8 -*-
"""
D7: write_pdf — 写入PDF文档

从document_tools.py拆分而来 — 小欧 2026-06-22

"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import re
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.constants import ERR_WRITE_PDF
from reportlab.lib.units import mm
from app.utils.logger import logger


def _build_write_pdf_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", detail: str = "",
) -> Dict[str, Any]:
    """write_pdf的llm_data构建函数 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"写入PDF失败: {detail}",
            "action": {"tool": "write_pdf", "tool_zh": "写入PDF", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "写入PDF失败", "code": ERR_WRITE_PDF, "detail": detail, "hint": "请检查路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入PDF成功: {file_path}",
        "action": {"tool": "write_pdf", "tool_zh": "写入PDF", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "写入PDF成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }



def write_pdf(
    file_name: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """写入PDF文件 — 小欧 2026-06-19 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化（Markdown格式）"""
    t0 = _time_mod.perf_counter()

    if not _check_module("reportlab"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("error", duration_ms, file_name, detail="reportlab库未安装")
        return build_error(data={"error_detail": "reportlab库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("error", duration_ms, file_name, detail="reportlab库导入失败")
        return build_error(data={"error_detail": "reportlab库导入失败", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)

        doc = SimpleDocTemplate(str(path), pagesize=A4)
        styles = getSampleStyleSheet()

        try:
            font_path = "C:/Windows/Fonts/simsun.ttc"
            pdfmetrics.registerFont(TTFont('SimSun', font_path, subfontIndex=0))
            chinese_style = ParagraphStyle(
                'Chinese', parent=styles['Normal'],
                fontName='SimSun', fontSize=10, leading=14,
                wordWrap='CJK',
            )
            title_style = ParagraphStyle(
                'ChineseTitle', parent=styles['Title'],
                fontName='SimSun', fontSize=18, leading=24,
                wordWrap='CJK',
            )
        except Exception:
            chinese_style = styles['Normal']
            title_style = styles['Title']

        elements = []

        if title:
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 10 * mm))

        if content:
            lines = content.split('\n')
            for line in lines:
                line = line.rstrip()
                if not line:
                    continue
                if line.startswith('# '):
                    h1_style = ParagraphStyle('h1', parent=chinese_style, fontSize=18, spaceBefore=12, spaceAfter=6)
                    elements.append(Paragraph(line[2:], h1_style))
                    elements.append(Spacer(1, 3 * mm))
                elif line.startswith('## '):
                    h2_style = ParagraphStyle('h2', parent=chinese_style, fontSize=16, spaceBefore=10, spaceAfter=5)
                    elements.append(Paragraph(line[3:], h2_style))
                    elements.append(Spacer(1, 3 * mm))
                elif line.startswith('### '):
                    h3_style = ParagraphStyle('h3', parent=chinese_style, fontSize=14, spaceBefore=8, spaceAfter=4)
                    elements.append(Paragraph(line[4:], h3_style))
                    elements.append(Spacer(1, 2 * mm))
                elif line.startswith('#### '):
                    h4_style = ParagraphStyle('h4', parent=chinese_style, fontSize=12, spaceBefore=6, spaceAfter=3)
                    elements.append(Paragraph(line[5:], h4_style))
                    elements.append(Spacer(1, 2 * mm))
                elif line.startswith('- ') or line.startswith('* '):
                    elements.append(Paragraph('• ' + line[2:], chinese_style))
                    elements.append(Spacer(1, 2 * mm))
                elif re.match(r'^\d+\.\s', line):
                    elements.append(Paragraph(re.sub(r'^\d+\.\s', '', line), chinese_style))
                    elements.append(Spacer(1, 2 * mm))
                else:
                    elements.append(Paragraph(line, chinese_style))
                    elements.append(Spacer(1, 3 * mm))

        if not elements:
            elements.append(Paragraph(" ", chinese_style))

        doc.build(elements)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("success", duration_ms, str(path))
        return build_success(data={"file_path": str(path)}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pdf_llm_data("error", duration_ms, file_name, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)