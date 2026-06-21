# -*- coding: utf-8 -*-
"""
F11: copy_file — 复制文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

import os
import time as _time_mod
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.services.context_vars import _current_task_id
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _build_copy_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "", extra_metrics: Optional[Dict] = None,
) -> Dict[str, Any]:
    """copy_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    extra_metrics = extra_metrics or {}
    if exec_code == "error":
        return {
            "summary": f"复制失败: {detail}",
            "action": {"tool": "copy_file", "tool_zh": "复制", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "复制失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"复制成功: {source}",
        "action": {"tool": "copy_file", "tool_zh": "复制", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "复制成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics,
    }


async def copy_file(
    source: str,
    destination: str,
    recursive: bool = False,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """复制文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    preserve_metadata = True
    if os.path.abspath(source) == os.path.abspath(destination):
        llm_data = _build_copy_file_llm_data("success", 0, source, extra_metrics={"status": "no_change"})
        return build_success(data={"action": "copy", "source": source, "destination": destination}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    from app.tools.toolhelper.file_helper import copy_file_impl

    result = await copy_file_impl(
        source_path=source,
        destination_path=destination,
        recursive=recursive,
        overwrite=overwrite,
        preserve_metadata=preserve_metadata,
        validate_path_func=_validate_path,
        task_id=_current_task_id.get(),
        record_operation_func=record_operation,
        execute_with_safety_func=execute_with_safety,
        get_next_sequence_func=lambda: 0,
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if result.get("code") == "SUCCESS":
        llm_data = _build_copy_file_llm_data("success", duration_ms, source)
        return build_success(data=result.get("data", {}), llm_data=llm_data)
    llm_data = _build_copy_file_llm_data("error", duration_ms, source, detail=result.get("data", {}).get("error", "复制失败"))
    return build_error(data=result.get("data", {}), llm_data=llm_data)