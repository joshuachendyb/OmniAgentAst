# -*- coding: utf-8 -*-
"""
D7: write_pdf — 写入PDF文档

从document_tools.py拆分而来 — 小欧 2026-06-22
内聚: _resolve_paragraphs / _add_pdf_content_item 辅助函数
"""

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.constants import ERR_WRITE_PDF, ERR_NO_REPORTLAB
from app.utils.json_utils import coerce_json
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


def _resolve_paragraphs(paragraphs):
    """解析paragraphs参数: 统一输出为 (title_from_dict, content_list) — 小欧 2026-06-19"""
    title = None
    items = []

    if isinstance(paragraphs, str):
        items = [paragraphs]
    elif isinstance(paragraphs, list):
        items = paragraphs
    elif isinstance(paragraphs, dict):
        title = paragraphs.get("title")
        content = paragraphs.get("content", [])
        items = content if isinstance(content, list) else [content]

    return title, items


def _add_pdf_content_item(elements, item, chinese_style, title_style):
    """处理单个PDF内容元素 — 小欧 2026-06-19"""
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Table, TableStyle, Spacer
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle

    if isinstance(item, str):
        if item.strip():
            elements.append(Paragraph(item, chinese_style))
            elements.append(Spacer(1, 3 * mm))
    elif isinstance(item, dict):
        item_type = item.get("type", "paragraph")
        item_text = item.get("text", "")
        if item_type in ("h1", "heading"):
            heading_style = ParagraphStyle('h1', parent=chinese_style,
                                           fontSize=18, spaceBefore=12, spaceAfter=6)
            elements.append(Paragraph(item_text, heading_style))
            elements.append(Spacer(1, 3 * mm))
        elif item_type in ("h2", "h3", "h4", "h5"):
            fs = max(18 - int(item_type[1]) * 2, 12)
            h_style = ParagraphStyle(f'h{item_type[1]}', parent=chinese_style,
                                     fontSize=fs, spaceBefore=8, spaceAfter=4)
            elements.append(Paragraph(item_text, h_style))
            elements.append(Spacer(1, 2 * mm))
        elif item_type == "paragraph":
            elements.append(Paragraph(item_text, chinese_style))
            elements.append(Spacer(1, 3 * mm))
        elif item_type == "table":
            rows_data = item.get("rows", [])
            if rows_data and len(rows_data) > 0:
                try:
                    t = Table(rows_data)
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ]))
                    elements.append(t)
                    elements.append(Spacer(1, 5 * mm))
                except Exception:
                    pass
    else:
        text = str(item)
        if text.strip():
            elements.append(Paragraph(text, chinese_style))
            elements.append(Spacer(1, 3 * mm))


def write_pdf(
    file_name: str,
    title: Optional[str] = None,
    paragraphs: Optional[Union[str, List, Dict]] = None,
) -> Dict[str, Any]:
    """写入PDF文件 — 小欧 2026-06-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    paragraphs = coerce_json(paragraphs)

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

        if paragraphs is not None:
            dict_title, items = _resolve_paragraphs(paragraphs)
            if dict_title and not title:
                elements.append(Paragraph(dict_title, title_style))
            for item in items:
                _add_pdf_content_item(elements, item, chinese_style, title_style)

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