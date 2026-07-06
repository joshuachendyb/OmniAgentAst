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
    text_len: int = 0, table_count: int = 0, image_count: int = 0, detail: str = "", hint: str = "",
) -> Dict[str, Any]:
    """read_pdf的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    if exec_code == "error":
        return {
            "summary": f"读取PDF失败: {detail}",
            "action": {"tool": "read_pdf", "tool_zh": "读取PDF", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取PDF失败", "code": ERR_DOC_READ_PDF, "detail": detail, "hint": hint if hint else "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    # summary: 页数(已读/总数)、字符数、表格数、图片数 — 小欧 2026-07-06
    parts = [f"{pages_read}/{page_count}页, {text_len}字符"]
    if table_count:
        parts.append(f"{table_count}项表格")
    if image_count:
        parts.append(f"{image_count}张图片")
    summary_str = "读取PDF成功: " + ", ".join(parts)
    return {
        "summary": summary_str,
        "action": {"tool": "read_pdf", "tool_zh": "读取PDF", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取PDF成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "page_count": {"value": page_count, "text": f"{page_count}页"},
            "pages_read": {"value": pages_read, "text": f"读取{pages_read}页"},
            "text_len": {"value": text_len, "text": f"{text_len}字符"},
            "table_count": {"value": table_count, "text": f"{table_count}个表格"},
            "image_count": {"value": image_count, "text": f"{image_count}张图片"},
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
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=error_detail, hint="文件类型不匹配,请使用.pdf格式")
        return build_error(data={"error_detail": error_detail, "params": {"file_name": file_name}}, llm_data=llm_data)

    if not _check_module("pdfplumber"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail="pdfplumber库未安装", hint="请安装pdfplumber库")
        return build_error(data={"error_detail": "pdfplumber库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        import pdfplumber

        # 工具层校验：非空/保留字符/保留名/系统目录/文件存在+是文件 — 小欧 2026-07-04
        # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
        is_valid, err, _ = validate_path(OpCategory.READ_FILE, file_path)
        if not is_valid:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=err, hint="请检查文件路径是否正确")
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
        result = {"text": full_text}
        if tables_data:
            result["tables"] = tables_data
        if images_data:
            result["images"] = images_data

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        table_cnt = len(tables_data)
        image_cnt = len(images_data)
        llm_data = _build_read_pdf_llm_data(
            "success", duration_ms, file_path, page_count, len(pages_read),
            len(full_text), table_cnt, image_cnt,
        )
        # =============================================================================
        # 数据设计：page_count/pages_read/table_count/image_count 从 data 移除
        # 通过 llm_data.metrics + summary 传递给 LLM
        # summary 示例: "读取PDF成功: 3/5页, 5000字符, 2项表格, 3张图片"
        # data 只保留 text/tables/images 纯数据 (formatter 渲染用)
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #10 raw text
        # trigger: "text" in data and isinstance(data["text"], str)
        # handler: _format_text_content(data) — 正文+额外字段(key=value)
        # file:    observation_formatter.py:124-126
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=str(e), hint="读取PDF文档异常,请检查文件完整性")
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)