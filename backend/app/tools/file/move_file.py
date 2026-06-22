# -*- coding: utf-8 -*-
"""
F10: move_file — 移动文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import asyncio
import os
import shutil
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.services.context_vars import _current_task_id
from app.db.models.operation_enums import OperationType
from app.services.safety.path_validator import ALLOWED_PATHS, validate_path as _validate_path_impl
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.utils.logger import logger


def _validate_path(file_path: str) -> Tuple[bool, Optional[str]]:
    """验证文件路径是否合法 — 小欧 2026-06-22"""
    return _validate_path_impl(file_path, ALLOWED_PATHS)


def _build_move_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "", extra_metrics: Optional[Dict] = None,
) -> Dict[str, Any]:
    """move_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    extra_metrics = extra_metrics or {}
    if exec_code == "error":
        return {
            "summary": f"移动失败: {detail}",
            "action": {"tool": "move_file", "tool_zh": "移动", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "移动失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"移动成功: {source}",
        "action": {"tool": "move_file", "tool_zh": "移动", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "移动成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics,
    }


async def _move_file_impl(
    source_path: str, destination_path: str, overwrite: bool = False,
) -> Dict[str, Any]:
    """移动或重命名文件实现 — 小欧 2026-06-22 — 小健 2026-06-22 重构：只返回raw dict，不含build3/llm_data"""
    is_valid_src, error_msg_src = _validate_path(source_path)
    if not is_valid_src:
        return {"success": False, "error_detail": f"源路径{error_msg_src}", "params": {"source": source_path}}

    is_valid_dst, error_msg_dst = _validate_path(destination_path)
    if not is_valid_dst:
        return {"success": False, "error_detail": f"目标路径{error_msg_dst}", "params": {"destination": destination_path}}

    src = Path(source_path)
    dst = Path(destination_path)

    try:
        if not src.exists():
            return {"success": False, "error_detail": "源文件不存在", "params": {"source": source_path}}

        task_id = _current_task_id.get()
        if not task_id:
            return {"success": False, "error_detail": "当前没有活跃任务ID", "params": {"source": source_path}}

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.MOVE,
            source_path=src, destination_path=dst, sequence_number=0,
        )

        def _move_sync():
            if dst.exists():
                if not overwrite:
                    raise FileExistsError(f"目标路径已存在: {dst},请设置overwrite=True")
                if dst.is_dir():
                    shutil.rmtree(str(dst))
                else:
                    dst.unlink()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return True

        success = await asyncio.to_thread(execute_with_safety, operation_id, operation_func=_move_sync)

        if success:
            return {"success": True, "operation_id": operation_id, "source": str(src), "destination": str(dst)}
        return {"success": False, "error_detail": "移动文件失败", "params": {"source": source_path, "destination": destination_path}}

    except Exception as e:
        logger.error(f"Failed to move {source_path} -> {destination_path}: {e}")
        return {"success": False, "error_detail": str(e), "params": {"source": source_path, "destination": destination_path}}


async def move_file(
    source: str,
    destination: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """移动文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：主函数负责计时+builder+build3"""
    t0 = _time_mod.perf_counter()
    if os.path.abspath(source) == os.path.abspath(destination):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("success", duration_ms, source, extra_metrics={"status": "no_change"})
        return build_success(data={}, llm_data=llm_data)

    result = await _move_file_impl(source_path=source, destination_path=destination, overwrite=overwrite)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if result.get("success"):
        llm_data = _build_move_file_llm_data("success", duration_ms, source)
        return build_success(
            data={"operation_id": result.get("operation_id")},
            llm_data=llm_data,
        )
    else:
        error_detail = result.get("error_detail", "移动文件失败")
        llm_data = _build_move_file_llm_data("error", duration_ms, source, detail=error_detail)
        return build_error(data={"error_detail": error_detail, "params": result.get("params", {})}, llm_data=llm_data)