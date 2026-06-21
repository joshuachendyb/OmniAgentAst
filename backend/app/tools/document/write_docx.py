# -*- coding: utf-8 -*-
"""
D5: write_docx — 写入Word文档

从document_tools.py拆分而来 — 小欧 2026-06-22
内聚: _resolve_paragraphs / _add_docx_content_item 辅助函数
"""

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.tools.tool_response import build_success, build_error
from app.tools.toolhelper.common_helper import _check_module
from app.constants import ERR_WRITE_DOCX, ERR_NO_DOCX
from app.utils.json_utils import coerce_json
from app.utils.logger import logger


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


def _add_docx_content_item(doc, item):
    """处理单个Word内容元素(list中的str或dict) — 小欧 2026-06-19"""
    if isinstance(item, str):
        if item.strip():
            doc.add_paragraph(item)
    elif isinstance(item, dict):
        item_type = item.get("type", "paragraph")
        item_text = item.get("text", "")
        if item_type in ("h1", "heading"):
            doc.add_heading(item_text, item.get("level", 1))
        elif item_type in ("h2", "h3", "h4", "h5"):
            doc.add_heading(item_text, level=int(item_type[1]))
        elif item_type == "paragraph":
            doc.add_paragraph(item_text)
        elif item_type == "table":
            rows_data = item.get("rows", [])
            if rows_data:
                t = doc.add_table(rows=len(rows_data), cols=len(rows_data[0]))
                for ri, rd in enumerate(rows_data):
                    for ci, cv in enumerate(rd):
                        t.rows[ri].cells[ci].text = str(cv)
    else:
        text = str(item)
        if text.strip():
            doc.add_paragraph(text)


def write_docx(
    file_name: str,
    title: Optional[str] = None,
    paragraphs: Optional[Union[str, List, Dict]] = None,
) -> Dict[str, Any]:
    """写入Word文档 — 小欧 2026-06-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    paragraphs = coerce_json(paragraphs)

    if not _check_module("docx"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_docx_llm_data("error", duration_ms, file_name, detail="python-docx库未安装")
        return build_error(data={"error_detail": "python-docx库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        from docx import Document

        doc = Document()

        if title:
            doc.add_heading(title, 0)

        if paragraphs is not None:
            dict_title, items = _resolve_paragraphs(paragraphs)
            if dict_title and not title:
                doc.add_heading(dict_title, 0)
            for item in items:
                _add_docx_content_item(doc, item)

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