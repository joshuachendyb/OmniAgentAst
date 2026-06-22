# -*- coding: utf-8 -*-
"""
F7: copy_file — 复制文件

从file_tools.py拆分而来 — 小欧 2026-06-22
内聚: _copy_file_impl (纯逻辑版，不含build3)
"""

import asyncio
import shutil
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.services.context_vars import _current_task_id
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _build_copy_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", extra_metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """copy_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    if exec_code == "error":
        detail = (extra_metrics or {}).get("detail", "复制失败")
        return {
            "summary": f"复制文件失败: {detail}",
            "action": {"tool": "copy_file", "tool_zh": "复制文件", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "复制失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"复制文件成功: {source}",
        "action": {"tool": "copy_file", "tool_zh": "复制文件", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "复制成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics or {},
    }


async def copy_file(
    source: str,
    destination: str,
    recursive: bool = False,
    overwrite: bool = False,
    preserve_metadata: bool = True,
) -> Dict[str, Any]:
    """复制文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    is_valid_src, err_src = _validate_path(source)
    if not is_valid_src:
        llm_data = _build_copy_file_llm_data("error", 0, source, extra_metrics={"detail": f"源路径验证失败: {err_src}"})
        return build_error(data={"error_detail": f"源路径验证失败: {err_src}", "params": {"source": source}}, llm_data=llm_data)

    is_valid_dst, err_dst = _validate_path(destination)
    if not is_valid_dst:
        llm_data = _build_copy_file_llm_data("error", 0, source, extra_metrics={"detail": f"目标路径验证失败: {err_dst}"})
        return build_error(data={"error_detail": f"目标路径验证失败: {err_dst}", "params": {"destination": destination}}, llm_data=llm_data)

    src = Path(source)
    dst = Path(destination)

    if not src.exists():
        llm_data = _build_copy_file_llm_data("error", 0, source, extra_metrics={"detail": f"源路径不存在: {source}"})
        return build_error(data={"error_detail": f"源路径不存在: {source}", "params": {"source": source}}, llm_data=llm_data)

    if dst.exists() and not overwrite:
        llm_data = _build_copy_file_llm_data("error", 0, source, extra_metrics={"status": "no_change"})
        return build_success(data={"action": "copy", "source": source, "destination": destination}, llm_data=llm_data)

    t0 = _time_mod.perf_counter()
    from app.services.safety.file_safety import record_operation, execute_with_safety
    from app.db.models.operation_enums import OperationType

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, extra_metrics={"detail": "No active task"})
        return build_error(data={"error_detail": "No active task", "params": {}}, llm_data=llm_data)

    try:
        operation_id = record_operation(
            task_id=task_id,
            operation_type=OperationType.COPY,
            source_path=src,
            destination_path=dst,
            sequence_number=0,
        )

        def _copy_sync():
            dst.parent.mkdir(parents=True, exist_ok=True)
            copy_func = shutil.copy2 if preserve_metadata else shutil.copy
            if src.is_file():
                copy_func(str(src), str(dst))
            elif src.is_dir():
                if recursive:
                    if dst.exists():
                        shutil.rmtree(str(dst))
                    if preserve_metadata:
                        shutil.copytree(str(src), str(dst))
                    else:
                        shutil.copytree(str(src), str(dst), copy_function=shutil.copy)
                else:
                    dst.mkdir(exist_ok=True)
            return True

        success = await asyncio.to_thread(
            execute_with_safety, operation_id=operation_id, operation_func=_copy_sync)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if success:
            llm_data = _build_copy_file_llm_data("success", duration_ms, source)
            return build_success(
                data={"operation_id": operation_id, "source": str(src), "destination": str(dst)},
                llm_data=llm_data)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, extra_metrics={"detail": "复制失败"})
        return build_error(data={"error_detail": "复制失败", "params": {"source": source}}, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, extra_metrics={"detail": str(e)})
        return build_error(data={"error_detail": str(e), "params": {"source": source}}, llm_data=llm_data)
