# -*- coding: utf-8 -*-
"""
D1: read_pdf — 读取PDF文档

从document_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.tools.file_type_checker import check_for_document_tool
from app.tools.tool_constants import ERR_DOC_READ_PDF
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger


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
    """读取PDF文件 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 增加文件类型前置检查"""
    t0 = _time_mod.perf_counter()
    file_path = file_name

    # 文件类型前置检查 — 小欧 2026-06-24
    is_valid, error_detail, suggested_tool = check_for_document_tool(file_name)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=error_detail)
        return build_error(data={"error_detail": error_detail, "params": {"file_name": file_name}}, llm_data=llm_data)

    if not _check_module("pdfplumber"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail="pdfplumber库未安装")
        return build_error(data={"error_detail": "pdfplumber库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        import pdfplumber

        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.READ_FILE, file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=err)
            return build_error(data={"error_detail": err, "params": {"file_name": file_name}}, llm_data=llm_data)

        path = Path(file_path)

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