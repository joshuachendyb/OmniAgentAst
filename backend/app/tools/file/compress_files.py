# -*- coding: utf-8 -*-
"""
F8: compress_files — 压缩文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

import asyncio
import time as _time_mod
from typing import Any, Dict, List, Optional

from app.tools.tool_response import build_success, build_error
from app.services.context_vars import _current_task_id
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.json_utils import coerce_json
from app.utils.logger import logger


def _validate_path(file_path: str):
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _build_compress_files_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "",
) -> Dict[str, Any]:
    """compress_files的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"压缩文件失败: {detail}",
            "action": {"tool": "compress_files", "tool_zh": "压缩文件", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "压缩失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"压缩文件成功: {source}",
        "action": {"tool": "compress_files", "tool_zh": "压缩文件", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "压缩成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


async def compress_files(
    source: str,
    destination: str,
    format: str = "zip",
    password: Optional[str] = None,
    overwrite: bool = False,
    exclude_patterns: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """压缩文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    t0 = _time_mod.perf_counter()
    exclude_patterns = coerce_json(exclude_patterns)
    compression_level = 6

    from app.tools.toolhelper.file_helper import compress_files_impl
    from app.services.safety.file_safety import record_operation, execute_with_safety
    from app.db.models.operation_enums import OperationType

    result = await compress_files_impl(
        source_path=source,
        output_path=destination,
        format=format,
        exclude_patterns=exclude_patterns,
        compression_level=compression_level,
        overwrite=overwrite,
        password=password,
        validate_path_func=_validate_path,
        task_id=_current_task_id.get(),
        record_operation_func=record_operation,
        execute_with_safety_func=execute_with_safety,
        get_next_sequence_func=lambda: 0,
    )
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
    if result.get("code") == "SUCCESS":
        llm_data = _build_compress_files_llm_data("success", duration_ms, source)
        return build_success(data=result.get("data", {}), llm_data=llm_data)
    llm_data = _build_compress_files_llm_data("error", duration_ms, source, detail=result.get("data", {}).get("error", "压缩失败"))
    return build_error(data=result.get("data", {}), llm_data=llm_data)