# -*- coding: utf-8 -*-
"""
D5: write_docx — 写入Word文档

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
from app.constants import ERR_WRITE_DOCX
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



def write_docx(
    file_name: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> Dict[str, Any]:
    """写入Word文档 — 小欧 2026-06-19 — 小欧 2026-06-22 独立文件 — 小健 2026-06-24 参数简化（Markdown格式）"""
    t0 = _time_mod.perf_counter()

    if not _check_module("docx"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_write_docx_llm_data("error", duration_ms, file_name, detail="python-docx库未安装")
        return build_error(data={"error_detail": "python-docx库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        from docx import Document

        doc = Document()

        if title:
            doc.add_heading(title, 0)

        if content:
            lines = content.split('\n')
            for line in lines:
                line = line.rstrip()
                if not line:
                    continue
                if line.startswith('# '):
                    doc.add_heading(line[2:], 1)
                elif line.startswith('## '):
                    doc.add_heading(line[3:], 2)
                elif line.startswith('### '):
                    doc.add_heading(line[4:], 3)
                elif line.startswith('#### '):
                    doc.add_heading(line[5:], 4)
                elif line.startswith('##### '):
                    doc.add_heading(line[6:], 5)
                elif line.startswith('- ') or line.startswith('* '):
                    doc.add_paragraph(line[2:], style='List Bullet')
                elif re.match(r'^\d+\.\s', line):
                    doc.add_paragraph(re.sub(r'^\d+\.\s', '', line), style='List Number')
                else:
                    doc.add_paragraph(line)

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