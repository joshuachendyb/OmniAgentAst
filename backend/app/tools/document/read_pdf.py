# -*- coding: utf-8 -*-
"""
D1: read_pdf — 读取PDF文档

从document_tools.py拆分而来 — 小欧 2026-06-22
"""

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.constants import ERR_DOC_READ_PDF
from app.utils.logger import logger


def _parse_pages(pages_str: str) -> List[int]:
    """解析页码字符串为页码列表 — 小欧 2026-06-22"""
    result = []
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            try:
                result.extend(range(int(start), int(end) + 1))
            except ValueError:
                pass
        else:
            try:
                result.append(int(part))
            except ValueError:
                pass
    return sorted(set(result))


def _process_page(page, page_num: int,
                   extract_tables: bool, extract_images: bool,
) -> Tuple[str, List[Dict], List[Dict]]:
    """处理单页PDF:返回 (text, tables_data, images_data) — 小沈 2026-05-25 — 小欧 2026-06-22"""
    text = page.extract_text() or ""
    tables = []
    if extract_tables:
        for idx, t in enumerate(page.extract_tables() or []):
            tables.append({"page": page_num, "table_idx": idx, "data": t})
    images = []
    if extract_images:
        for idx, img in enumerate(page.images or []):
            images.append({
                "page": page_num, "image_idx": idx,
                "x0": float(img.get("x0", 0)), "y0": float(img.get("y0", 0)),
                "x1": float(img.get("x1", 0)), "y1": float(img.get("y1", 0)),
                "width": float(img.get("width", 0)), "height": float(img.get("height", 0)),
            })
    return text, tables, images


def _build_read_pdf_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", page_count: int = 0, pages_read: int = 0,
    text_len: int = 0, table_count: int = 0, image_count: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """read_pdf的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取PDF失败: {detail}",
            "action": {"tool": "read_pdf", "tool_zh": "读取PDF", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取PDF失败", "code": ERR_DOC_READ_PDF, "detail": detail, "hint": "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取PDF成功: {pages_read}/{page_count}页, {text_len}字符",
        "action": {"tool": "read_pdf", "tool_zh": "读取PDF", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取PDF成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "page_count": {"value": page_count, "text": f"{page_count}页"},
            "pages_read": {"value": pages_read, "text": f"读取{pages_read}页"},
            "text_len": {"value": text_len, "text": f"{text_len}字符"},
        },
    }


def read_pdf(file_name: str) -> Dict[str, Any]:
    """读取PDF文件 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    file_path = file_name

    if not _check_module("pdfplumber"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail="pdfplumber库未安装")
        return build_error(data={"error_detail": "pdfplumber库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        import pdfplumber

        path = Path(file_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=f"文件不存在: {file_path}")
            return build_error(data={"error_detail": "文件不存在", "params": {"file_name": file_name}}, llm_data=llm_data)

        all_text, pages_read, tables_data, images_data = [], [], [], []
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            target = list(range(1, page_count + 1))
            target = [p for p in target if 1 <= p <= page_count]

            for pn in target:
                page = pdf.pages[pn - 1]
                text, tables, images = _process_page(page, pn, extract_tables=True, extract_images=True)
                all_text.append(f"--- 第 {pn} 页 ---\n{text}")
                pages_read.append(pn)
                tables_data.extend(tables)
                images_data.extend(images)

        full_text = "\n\n".join(all_text)
        result = {"text": full_text, "page_count": page_count, "pages_read": pages_read}
        if tables_data:
            result["tables"] = tables_data
            result["table_count"] = len(tables_data)
        if images_data:
            result["images"] = images_data
            result["image_count"] = len(images_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data(
            "success", duration_ms, file_path, page_count, len(pages_read),
            len(full_text), len(tables_data), len(images_data),
        )
        return build_success(data=result, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)