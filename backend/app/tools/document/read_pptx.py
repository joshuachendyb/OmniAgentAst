# -*- coding: utf-8 -*-
"""
D3: read_pptx — 读取PPT文档

从document_tools.py拆分而来 — 小欧 2026-06-22
"""

import time as _time_mod
from pathlib import Path
from typing import Any, Dict

from app.tools.tool_response import build_success, build_error
from app.tools.toolhelper.common_helper import _check_module
from app.constants import ERR_DOC_READ_PPTX
from app.utils.logger import logger


def _build_read_pptx_llm_data(
    exec_code: str, duration_ms: int,
    file_path: str = "", slide_count: int = 0, text_len: int = 0, detail: str = "",
) -> Dict[str, Any]:
    """read_pptx的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"读取PPT失败: {detail}",
            "action": {"tool": "read_pptx", "tool_zh": "读取PPT", "target": file_path, "params": {"file_path": file_path}},
            "status": {"exec_code": "error", "message": "读取PPT失败", "code": ERR_DOC_READ_PPTX, "detail": detail, "hint": "请检查文件路径和格式"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"读取PPT成功: {slide_count}页, {text_len}字符",
        "action": {"tool": "read_pptx", "tool_zh": "读取PPT", "target": file_path, "params": {"file_path": file_path}},
        "status": {"exec_code": "success", "message": "读取PPT成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {
            "slide_count": {"value": slide_count, "text": f"{slide_count}页"},
            "text_len": {"value": text_len, "text": f"{text_len}字符"},
        },
    }


def read_pptx(file_name: str) -> Dict[str, Any]:
    """读取PPT文件 — 小沈 2026-06-19 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    file_path = file_name

    if not _check_module("pptx"):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pptx_llm_data("error", duration_ms, file_path, detail="python-pptx库未安装")
        return build_error(data={"error_detail": "python-pptx库未安装", "params": {"file_name": file_name}}, llm_data=llm_data)

    try:
        from pptx import Presentation

        path = Path(file_path)
        if not path.exists():
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_read_pptx_llm_data("error", duration_ms, file_path, detail=f"文件不存在: {file_path}")
            return build_error(data={"error_detail": "文件不存在", "params": {"file_name": file_name}}, llm_data=llm_data)

        prs = Presentation(path)
        slides_data = []
        notes_data = []

        for slide_num, slide in enumerate(prs.slides, 1):
            slide_text = []
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for para in shape.text_frame.paragraphs:
                        text = para.text.strip()
                        if text:
                            slide_text.append(text)

            slides_data.append({
                "slide_num": slide_num,
                "text": "\n".join(slide_text),
            })

            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text.strip()
                if notes:
                    notes_data.append({
                        "slide_num": slide_num,
                        "notes": notes,
                    })

        result_data = {
            "slide_count": len(prs.slides),
            "slides": slides_data,
        }
        if notes_data:
            result_data["notes"] = notes_data

        total_text = sum(len(s.get("text", "")) for s in slides_data)
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pptx_llm_data("success", duration_ms, file_path, len(prs.slides), total_text)
        return build_success(data=result_data, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_read_pptx_llm_data("error", duration_ms, file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"file_name": file_name}}, llm_data=llm_data)