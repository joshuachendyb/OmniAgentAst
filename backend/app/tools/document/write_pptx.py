# -*- coding: utf-8 -*-
"""
D8: write_pptx — 写入PPT文档

从document_tools.py拆分而来 — 小欧 2026-06-22
内聚: _select_layout / _add_pptx_content / _add_pptx_table / _add_pptx_slide / _build_pptx_presentation 辅助函数
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.constants import ERR_DOC_WRITE_PPTX, ERR_DOC_NO_PPTX
from app.utils.json_utils import coerce_json
from app.utils.logger import logger


def _build_write_pptx_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", slide_count: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """write_pptx的llm_data构建函数 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"写入PPT失败: {detail}",
            "action": {"tool": "write_pptx", "tool_zh": "写入PPT", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "写入PPT失败", "code": ERR_DOC_WRITE_PPTX, "detail": detail, "hint": "请检查路径和权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"写入PPT成功: {file_path}, {slide_count}页",
        "action": {"tool": "write_pptx", "tool_zh": "写入PPT", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "写入PPT成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "slide_count": {"value": slide_count, "text": f"{slide_count}页"},
        },
    }


def _select_layout(prs, slide_type):
    """选布局 — 小欧 2026-06-19"""
    m = {0: 0, "cover": 0, 1: 1, "content": 1, 2: 2, "two": 2}
    return prs.slide_layouts[m.get(slide_type, 1)]


def _add_pptx_content(slide, content):
    """处理正文到 content placeholder — 小欧 2026-06-19"""
    body = None
    for sh in slide.placeholders:
        idx = sh.placeholder_format.idx
        if idx == 1:
            continue
        if idx >= 2:
            body = sh.text_frame
            break
    if body is None:
        return

    def _get_para(is_first: bool):
        return body.paragraphs[0] if is_first else body.add_paragraph()

    if isinstance(content, str):
        body.paragraphs[0].text = content
    elif isinstance(content, list):
        first_slot = True
        for item in content:
            if isinstance(item, str):
                p = _get_para(first_slot)
                first_slot = False
                p.text = item
            elif isinstance(item, dict):
                t = item.get("type", "paragraph")
                txt = item.get("text", "")
                if t == "paragraph":
                    p = _get_para(first_slot)
                    first_slot = False
                    p.text = txt
                elif t == "bullets":
                    for b in item.get("items", []):
                        p = _get_para(first_slot)
                        first_slot = False
                        p.text = str(b)
                        p.level = 1


def _add_pptx_table(slide, table_data):
    """添加表格到幻灯片(独立shape) — 小欧 2026-06-19"""
    if not table_data or not table_data[0] or len(table_data[0]) == 0:
        return
    rows, cols = len(table_data), len(table_data[0])
    from pptx.util import Inches
    left, top, width, height = Inches(1), Inches(2), Inches(6), Inches(0.4 * rows)
    tbl = slide.shapes.add_table(rows, cols, left, top, width, height).table
    for ri, row in enumerate(table_data):
        for ci, val in enumerate(row):
            tbl.cell(ri, ci).text = str(val)


def _add_pptx_slide(prs, slide_data):
    """添加一页幻灯片 — 小欧 2026-06-19"""
    slide_type = slide_data.get("type", 1)
    title = slide_data.get("title", "")
    subtitle = slide_data.get("subtitle", "")
    content = slide_data.get("content")
    tables = slide_data.get("tables")

    layout = _select_layout(prs, slide_type)
    slide = prs.slides.add_slide(layout)

    if title and slide.shapes.title:
        slide.shapes.title.text = title

    if subtitle and slide_type in (0, "cover"):
        for shape in slide.placeholders:
            if shape.placeholder_format.idx == 1:
                shape.text = subtitle
                break

    if content:
        _add_pptx_content(slide, content)

    if tables:
        for td in tables:
            _add_pptx_table(slide, td)


def _build_pptx_presentation(slides: list):
    """构建全部幻灯片 — 小欧 2026-06-19"""
    from pptx import Presentation
    prs = Presentation()

    if slides:
        for slide_data in slides:
            _add_pptx_slide(prs, slide_data)

    return prs


def write_pptx(
    file_name: str,
    slides: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """写入PPT文件 — 小欧 2026-06-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    slides = coerce_json(slides)

    if not _check_module("pptx"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pptx_llm_data("error", duration_ms, file_name, detail="python-pptx库未安装")
        return build_error(data={"error_detail": "python-pptx库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        prs = _build_pptx_presentation(slides)
        path = Path(file_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(path)

        slide_count = len(prs.slides)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pptx_llm_data("success", duration_ms, str(path), slide_count)
        return build_success(data={"file_path": str(path), "slide_count": slide_count}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_pptx_llm_data("error", duration_ms, file_name, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)