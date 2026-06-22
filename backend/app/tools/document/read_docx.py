# -*- coding: utf-8 -*-
"""
D2: read_docx — 读取Word文档

从document_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import os
import shutil
import subprocess
import tempfile
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _check_module
from app.tools.tool_constants import SUBPROCESS_TIMEOUT_LONG
from app.constants import ERR_DOC_READ_DOCX
from app.utils.logger import logger


def _build_read_docx_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", para_count: int = 0, text_len: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """read_docx的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取Word失败: {detail}",
            "action": {"tool": "read_docx", "tool_zh": "读取Word", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取Word失败", "code": ERR_DOC_READ_DOCX, "detail": detail, "hint": "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取Word成功: {para_count}段, {text_len}字符",
        "action": {"tool": "read_docx", "tool_zh": "读取Word", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取Word成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "para_count": {"value": para_count, "text": f"{para_count}段"},
            "text_len": {"value": text_len, "text": f"{text_len}字符"},
        },
    }


def read_docx(file_name: str) -> Dict[str, Any]:
    """读取Word文档 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    file_path = file_name
    path = Path(file_name)
    suffix = path.suffix.lower()

    if suffix == ".doc":
        pandoc = shutil.which("pandoc")
        if not pandoc:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_docx_llm_data("error", duration_ms, file_name, detail="读取.doc文件需要安装pandoc转换工具")
            return build_error(data={"error_detail": "读取.doc文件需要安装pandoc", "params": {"file_name": file_name}}, llm_data=llm_data)
        tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            subprocess.run([pandoc, file_name, "-o", tmp_path], capture_output=True, text=True,
                         timeout=SUBPROCESS_TIMEOUT_LONG, check=True)
            file_path = tmp_path
        except subprocess.CalledProcessError as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_docx_llm_data("error", duration_ms, file_name, detail=f"pandoc转换.doc失败: {e.stderr}")
            return build_error(data={"error_detail": f"pandoc转换失败", "params": {"file_name": file_name}}, llm_data=llm_data)
        finally:
            pass

    if not _check_module("docx"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_docx_llm_data("error", duration_ms, file_name, detail="python-docx库未安装")
        return build_error(data={"error_detail": "python-docx库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        import docx

        doc_path = Path(file_path)
        if not doc_path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_docx_llm_data("error", duration_ms, file_name, detail=f"文件不存在: {file_name}")
            return build_error(data={"error_detail": "文件不存在", "params": {"file_name": file_name}}, llm_data=llm_data)

        doc = docx.Document(doc_path)
        paragraphs = [para.text for para in doc.paragraphs]
        text = "\n".join(paragraphs)

        result_data = {"text": text, "paragraph_count": len(paragraphs)}

        tables_data = []
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_rows.append(row_data)
            tables_data.append(table_rows)
        if tables_data:
            result_data["tables"] = tables_data
            result_data["table_count"] = len(tables_data)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_docx_llm_data("success", duration_ms, file_name, len(paragraphs), len(text))
        return build_success(data=result_data, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_docx_llm_data("error", duration_ms, file_name, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)
    finally:
        if suffix == ".doc":
            try:
                os.unlink(tmp_path)
            except OSError:
                pass