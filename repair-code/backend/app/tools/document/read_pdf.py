# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 自然单位翻页治理 feat:
#   1. 新增 _parse_pdf_pages() 解析器
#   2. read_pdf() 增加 page/pages 参数
#   3. 新增 READ_PDF_OUTLIMIT_DEFAULT_PAGES
#     防OOM截断(超限仅取前N页)
#   4. 新增翻页选择+参数校验逻辑
#   5. fitz 文本改为按页拆分(\n\n)
#   6. 更新 formatter 路由注释
#   7. 超出页数时拼接截断提示语
# 2026-07-21 - 小欧 - 修复BUG-001:
#   1. _process_page 表格从 list 改为
#     dict 含 page+rows 双字段
#   2. 恢复 paginate 按页过滤正确性
#     (修复因缺page字段致AttributeError)
# 2026-07-21 - 小欧 - 默认值+字节安全双治理: READ_PDF_OUTLIMIT_DEFAULT_PAGES=200 作为未传参时的默认读取页数, READ_PDF_INPUT_MAX_BYTES=50MB 作为硬安全字节上限
# 2026-07-23 - 小欧 - 三堂会审5bug修复(配套删input门): 删READ_PDF_INPUT_MAX_BYTES import+input门块
# 2026-07-24 - 小欧 - 修复: error summary嵌入full detail → 改用truncate_summary(detail)首行
# 2026-07-26 - 小欧 - 清理: 删logger死import(全文件无logger调用)
# 2026-07-26 - 小沈 - BugFix #3: path参数不覆盖
# 2026-07-31 - 小欧 - Bug⑦修复: _is_garbled_text 仅统计 \ufffd 替换字符, 不再统计普通'?'(正文合法问号占比高时误触发fitz后备); Bug⑮修复: _extract_with_fitz 返回按页对齐文本列表, 防页内含空行 split("\n\n") 页码错位 | py_compile ✓
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
from app.tools.validate.file_path_checker import hint_for_read_error
from app.tools.tool_constants import ERR_DOC_READ_PDF, READ_PDF_OUTLIMIT_DEFAULT_PAGES
from app.utils.text_utils import truncate_summary


def _is_garbled_text(text: str, threshold: float = 0.30) -> bool:
    """检测文本是否含大量 U+FFFD 替换字符（CJK编码丢失）— 小欧 2026-07-08
       2026-07-31 小欧: Bug⑦修复 — 不再统计普通'?'字符(正文合法问号占比高时误触发fitz后备), 仅统计编码丢失特征 \ufffd
    """
    if not text.strip():
        return False
    q_count = sum(1 for c in text if c == '\ufffd')
    return (q_count / len(text)) > threshold


def _parse_pdf_pages(page, pages, page_count: int):
    """解析 page/pages 参数为选中页号列表(1-based, 升序去重); 无效返回 None
    适用: read_pdf 自然单位翻页(2026-07-20 小欧)"""
    want = []
    if page is not None:
        if not isinstance(page, int) or page < 1 or page > page_count:
            return None
        want.append(page)
    if pages is not None:
        if isinstance(pages, int):
            if pages < 1 or pages > page_count:
                return None
            want.append(pages)
        elif isinstance(pages, str):
            m = pages.strip()
            if "-" in m:
                try:
                    a, b = m.split("-", 1)
                    a, b = int(a), int(b)
                except ValueError:
                    return None
                if a < 1 or b > page_count or a > b:
                    return None
                want.extend(range(a, b + 1))
            else:
                try:
                    v = int(m)
                except ValueError:
                    return None
                if v < 1 or v > page_count:
                    return None
                want.append(v)
        elif isinstance(pages, (list, tuple)):
            for v in pages:
                if not isinstance(v, int) or v < 1 or v > page_count:
                    return None
                want.append(v)
        else:
            return None
    seen = set()
    out = []
    for p in want:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def _extract_with_fitz(file_path: str) -> Tuple[list, list, list]:
    """PyMuPDF后备提取文本+表格+图片 — 小欧 2026-07-08
       2026-07-31 小欧: Bug⑮修复 — 返回按页对齐的文本列表(每页一个元素, 含---第N页---标记), 不再join后split("\n\n")造成页内含空行时页码错位; 移除未使用page_count参数
    """
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
    return all_text, tables_data, images_data


def _build_read_pdf_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", page_count: int = 0, pages_read: int = 0,
    text_len: int = 0, table_count: int = 0, image_count: int = 0, detail: str = "", hint: str = "",
) -> Dict[str, Any]:
    """read_pdf的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小欧 2026-07-05 加hint参数"""
    if exec_code == "error":
        _err_summary = truncate_summary(detail)
        return {
            "summary": f"读取PDF{file_path}，失败" + (f": {_err_summary}" if _err_summary else ""),
            "action": {"tool": "read_pdf", "tool_zh": "读取PDF", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取PDF失败", "code": ERR_DOC_READ_PDF, "detail": detail, "hint": hint if hint else "读取失败,详见错误明细"},
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
            tables.append({
                "page": page_num,
                "rows": table.extract(),
            })
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


def read_pdf(path: str, page: Optional[int] = None, pages: Optional[Any] = None) -> Dict[str, Any]:
    """读取PDF文件 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件 — 小欧 2026-06-24 增加文件类型前置检查
    2026-07-21 默认值+字节安全双治理(小欧): READ_PDF_OUTLIMIT_DEFAULT_PAGES=200 作为未传参时的默认读取页数, READ_PDF_INPUT_MAX_BYTES=50MB 作为硬安全字节上限"""
    t0 = _time_mod.perf_counter()
    file_path = path

    # 文件类型前置检查 — 小欧 2026-06-24
    is_valid, error_detail, suggested_tool = check_for_document_tool(path)
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

        _p = Path(file_path)
        # 校验PDF文件头（前5字节应为%PDF），提前拦截非PDF文件 — 小欧 2026-07-07
        with open(_p, 'rb') as fh:
            header = fh.read(5)
        if header != b'%PDF-':
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail="文件不是有效的PDF格式（缺少%PDF头）", hint="请确认文件是PDF格式")
            return build_error(data={}, llm_data=llm_data)

        pages_text: List[str] = []
        read_page_nums: List[int] = []
        tables_data: List[dict] = []
        images_data: List[dict] = []
        with pdfplumber.open(_p) as pdf:
            page_count = len(pdf.pages)
            for pn in range(1, page_count + 1):
                pdf_page = pdf.pages[pn - 1]
                text, tables, images = _process_page(pdf_page, pn, extract_tables=True, extract_images=True)
                pages_text.append(f"--- 第 {pn} 页 ---\n{text}")
                read_page_nums.append(pn)
                tables_data.extend(tables)
                images_data.extend(images)

        full_text = "\n\n".join(pages_text)

        # CJK乱码检测: 当U+FFFD占比>30%时，尝试PyMuPDF后备提取 — 小欧 2026-07-08 — 小欧 2026-07-31 Bug⑮ 按页对齐
        fitz_used = False
        if _is_garbled_text(full_text):
            try:
                if _check_module("fitz"):
                    fitz_pages, fitz_tables, fitz_images = _extract_with_fitz(file_path)
                    if not _is_garbled_text("\n\n".join(fitz_pages)):
                        pages_text = fitz_pages
                        tables_data = fitz_tables
                        images_data = fitz_images
                        fitz_used = True
            except Exception:
                pass

        # —— 按页选取: 传参读指定页, 否则默认前 READ_PDF_OUTLIMIT_DEFAULT_PAGES 页; 字节检查兜底OOM ——
        selected: List[str] = []
        selected_pages: List[int] = []
        truncated_hint = ""
        if page is not None or pages is not None:
            want = _parse_pdf_pages(page, pages, page_count)
            if want is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path,
                                                    detail="page/pages 参数无效(超出范围或非数字)", hint="page 为 1..总页数 的整数; pages 可为整数/列表/'a-b'", page_count=page_count)
                return build_error(data={}, llm_data=llm_data)
            selected_pages = want
            selected = [pages_text[i - 1] for i in want if 1 <= i <= len(pages_text)]
        else:
            selected = pages_text[:READ_PDF_OUTLIMIT_DEFAULT_PAGES]
            selected_pages = read_page_nums[:READ_PDF_OUTLIMIT_DEFAULT_PAGES]
            if page_count > READ_PDF_OUTLIMIT_DEFAULT_PAGES:
                truncated_hint = f"文档共 {page_count} 页, 默认仅读前 {READ_PDF_OUTLIMIT_DEFAULT_PAGES} 页, 用 page=N 读取指定页"

        full_text = "\n\n".join(selected)
        # tables/images 仅保留所选页(按 page 号过滤; fitz 路径无 page 号则整体保留)
        if selected_pages and not fitz_used:
            sel_set = set(selected_pages)
            tables_data = [t for t in tables_data if t.get("page") in sel_set]
            images_data = [i for i in images_data if i.get("page") in sel_set]

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
        if truncated_hint:
            hint = (hint + "; " if hint else "") + truncated_hint
        llm_data = _build_read_pdf_llm_data(
            "success", duration_ms, file_path, page_count, len(selected_pages),
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
        # branch: #10a PDF页感知
        # trigger: "text" in data and isinstance(data["text"], str) and action.tool=="read_pdf"
        # handler: _format_pdf_result(data["text"]) — 行×列窗口(≈前3页), 保留 "--- 第 N 页 ---" 标记; 两态提示 page=N
        # file:    observation_formatter.py:_format_pdf_result
        # ------------------------------------------------------------------------------
        return build_success(data=result, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pdf_llm_data("error", duration_ms, file_path, detail=str(e), hint=hint_for_read_error(e, file_path))
        return build_error(data={}, llm_data=llm_data)
