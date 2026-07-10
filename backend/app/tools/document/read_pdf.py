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
from app.tools.validate.file_type_checker import check_for_document_tool
from app.tools.tool_constants import ERR_DOC_READ_PDF

from app.logger import logger


def _is_garbled_text(text: str, threshold: float = 0.30) -> bool:
    """检测文本是否含大量 ? 字符（CJK编码丢失）— 小欧 2026-07-08"""
    if not text.strip():
        return False
    q_count = sum(1 for c in text if c == '\ufffd' or c == '?')
    return (q_count / len(text)) > threshold


def _extract_with_fitz(file_path: str, page_count: int) -> Tuple[str, list, list]:
    """PyMuPDF后备提取文本+表格+图片 — 小欧 2026-07-08"""
    import fitz
    all_text, tables_data, images_data = [], [], []
    doc = fitz.open(file_path)
    for pn in range(doc.page_count):
        page = doc[pn]
        text = page.get_text() or ""
        all_text.append(f"--- 第 {pn + 1} 页 ---\n{text}")
        tables_data.append({"page": pn + 1, "note": "PyMuPDF不提供表格提取"})
        for img in page.get_images():
            images_data.append({
                "page": pn + 1,
                "width": 0, "height": 0,
                "note": "图片引用索引, 实际尺寸需渲染后获取",
            })
    doc.close()
    full_text = "\n\n".join(all_text)
    return full_text, tables_data, images_data


def _build_read_pdf_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", page_count: int = 0, pages_read: int = 0,
    text_len: int = 0, table_count: int = 0, image_count: int = 0, detail: str = "", hint: str = "",
) -> Dict[str, Any]:
    """read_pdf的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    if exec_code == "error":
        return {
            "summary": f"读取PDF{file_path}，失败: {detail}",
            "action": {"tool": "read_pdf", "tool_zh": "读取PDF", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取PDF失败", "code": ERR_DOC_READ_PDF, "detail": detail, "hint": hint if hint else "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    # summary: 页数(已读/总数)、字符数、表格数、图片数 — 小欧 2026-07-06
    parts = [f"已读{pages_read}页/共{page_count}页，{text_len}字符"]
    if table_count:
        parts.append(f"{table_count}项表格")
    if image_count:
        parts.append(f"{image_count}张图片")
    summary_str = f"读取PDF{file_path}，成功: " + "，".join(parts)
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


def _process_page(page, page_num: int, extract_tables: bool = True, extract_images: bool = True) -> Tuple[str, List, List]:
    """提取单页PDF的文本、表格和图片 — 小欧 2026-07-07

    pdfplumber从document_tools.py拆分出来时遗漏了此函数
    """
    text = page.extract_text() or ""
    tables = []
    if extract_tables:
        for table in page.find_tables():
            tables.append(table.extract())
    images = []
    if extract_images:
        for img in page.images:
            images.append({
                "page": page_num,
                "width": img.get("width", 0),
                "height": img.get("height", 0),
                "x0": img.get("x0", 0),
                "top": img.get("top", 0),
            })
    return text, tables, images


def read_pdf(file_name: str) -> Dict[str, Any]:
    """读取PDF文件 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 增加文件类型前置检查"""
    t0 = _time_mod.perf_counter()
    file_path = file_name

    # 文件类型前置检查 — 小欧 2026-06-24
    is_valid, error_detail, suggested_tool = check_for_document_tool(file_name)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if suggested_tool:
            _hint = f"建议使用{suggested_tool}工具"
        elif suggested_tool == "":
            _hint = "请检查文件路径和文件名是否正确"
        else:
            _hint = "文件类型不匹配,请使用正确的文档格式"
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=error_detail, hint=_hint)
        return build_error(data={}, llm_data=llm_data)

    if not _check_module("pdfplumber"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail="pdfplumber库未安装", hint="请安装pdfplumber库")
        return build_error(data={}, llm_data=llm_data)

    try:
        import pdfplumber

        path = Path(file_path)
        # 校验PDF文件头（前5字节应为%PDF），提前拦截非PDF文件 — 小欧 2026-07-07
        with open(path, 'rb') as fh:
            header = fh.read(5)
        if header != b'%PDF-':
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail="文件不是有效的PDF格式（缺少%PDF头）", hint="请确认文件是PDF格式")
            return build_error(data={}, llm_data=llm_data)
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

        # CJK乱码检测: 当?/U+FFFD占比>30%时，尝试PyMuPDF后备提取 — 小欧 2026-07-08
        fitz_used = False
        if _is_garbled_text(full_text):
            try:
                if _check_module("fitz"):
                    fitz_text, fitz_tables, fitz_images = _extract_with_fitz(file_path, page_count)
                    if not _is_garbled_text(fitz_text):
                        full_text = fitz_text
                        tables_data = fitz_tables
                        images_data = fitz_images
                        fitz_used = True
            except Exception:
                pass

        result = {"text": full_text}
        if tables_data:
            result["tables"] = tables_data
        if images_data:
            result["images"] = images_data

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        table_cnt = len(tables_data)
        image_cnt = len(images_data)
        hint = ""
        if fitz_used:
            hint = "pdfplumber提取中文乱码,已使用PyMuPDF后备提取"
        elif _is_garbled_text(full_text):
            hint = "该PDF文档的中文文本在创建时已丢失编码信息,无法通过文本提取恢复,建议使用OCR工具"
        llm_data = _build_read_pdf_llm_data(
            "success", duration_ms, file_path, page_count, len(pages_read),
            len(full_text), table_cnt, image_cnt, hint=hint,
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
        return build_error(data={}, llm_data=llm_data)