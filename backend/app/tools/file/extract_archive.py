# -*- coding: utf-8 -*-
"""
F9: extract_archive — 解压文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

import time as _time_mod
from typing import Any, Dict, Optional

from app.tools.tool_response import build_success, build_error
from app.utils.logger import logger


def _build_extract_archive_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "",
) -> Dict[str, Any]:
    """extract_archive的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"解压文件失败: {detail}",
            "action": {"tool": "extract_archive", "tool_zh": "解压文件", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "解压失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"解压文件成功: {source}",
        "action": {"tool": "extract_archive", "tool_zh": "解压文件", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "解压成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


async def extract_archive(
    source: str,
    destination: Optional[str] = None,
    password: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """解压归档包 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()

    from app.tools.toolhelper.file_helper import extract_archive as _extract_archive_impl
    result = _extract_archive_impl(
        archive_path=source,
        output_dir=destination,
        overwrite=overwrite,
        password=password,
        preserve_permissions=True,
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if result.get("code") == "SUCCESS":
        llm_data = _build_extract_archive_llm_data("success", duration_ms, source)
        return build_success(data=result.get("data", {}), llm_data=llm_data)
    llm_data = _build_extract_archive_llm_data("error", duration_ms, source, detail=result.get("data", {}).get("error", "解压失败"))
    return build_error(data=result.get("data", {}), llm_data=llm_data)