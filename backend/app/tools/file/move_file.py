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
from app.tools.tool_constants import ERR_FILE_MOVE_FAILED
from app.utils.context_vars import _current_task_id
from app.db.models.operation_enums import OperationType
from app.tools.validate.file_path_checker import validate_path, OpCategory
from app.services.safety.file_safety import record_operation, execute_with_safety
from app.utils.logger import logger



def _build_move_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", destination: str = "", detail: str = "",
    extra_metrics: Optional[Dict[str, Any]] = None,
    hint: str = "",
    user_overwrite: Optional[bool] = None,
) -> Dict[str, Any]:
    """move_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint参数"""
    _act_params = {"source": source, "destination": destination}
    if user_overwrite is not None:
        _act_params["overwrite"] = user_overwrite
    if exec_code == "error":
        return {
            "summary": f"移动文件{source}，失败",
            "action": {"tool": "move", "tool_zh": "移动文件", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "移动失败", "code": ERR_FILE_MOVE_FAILED, "detail": detail, "hint": hint if hint else "请检查源路径和目标路径"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"移动成功: {source} -> {destination}",
        "action": {"tool": "move", "tool_zh": "移动文件", "target": source, "params": _act_params},
        "status": {"exec_code": "success", "message": "移动成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics or {},
    }


async def _move_file_impl(
    source_path: str, destination_path: str, overwrite: bool = False,
) -> Dict[str, Any]:
    """移动或重命名文件实现 — 小欧 2026-06-22 — 小健 2026-06-22 重构：只返回raw dict，不含build3/llm_data"""

    src = Path(source_path)
    dst = Path(destination_path)

    if src.resolve() == dst.resolve():
        return {"success": False, "error_detail": f"源路径和目标路径相同: {source_path}", "params": {"source": source_path, "destination": destination_path}}

    if src.is_dir() and dst.is_file():
        return {"success": False, "error_detail": "不能移动目录到文件路径", "params": {"source": source_path, "destination": destination_path}}

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
                if not os.access(str(dst), os.W_OK):
                    os.chmod(str(dst), os.stat(str(dst)).st_mode | 0o200)
                if dst.is_dir():
                    logger.warning(f"[move] overwrite模式: 目标目录已存在,将删除后移动: {dst}")
                    shutil.rmtree(str(dst))
                else:
                    dst.unlink()
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return True

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24
        if operation_id:
            success = await asyncio.to_thread(execute_with_safety, operation_id, operation_func=_move_sync)
        else:
            logger.info("Database unavailable, executing move operation without recording")
            success = await asyncio.to_thread(_move_sync)

        if success:
            return {"success": True, "operation_id": operation_id, "source": str(src), "destination": str(dst)}
        return {"success": False, "error_detail": "移动文件失败", "params": {"source": source_path, "destination": destination_path}}

    except Exception as e:
        logger.error(f"Failed to move {source_path} -> {destination_path}: {e}")
        return {"success": False, "error_detail": str(e), "params": {"source": source_path, "destination": destination_path}}


async def move(
    source: str,
    destination: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """移动文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：主函数负责计时+builder+build3"""
    t0 = _time_mod.perf_counter()
    if not source or not source.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail="source不能为空", hint="请提供有效的源文件路径", user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    if not destination or not destination.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail="destination不能为空", hint="请提供有效的目标路径", user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    # 工具层校验（源路径）：非空/保留字符/保留名/系统目录/源存在 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.EXISTS, source)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail=err, hint="请检查源文件路径是否正确", user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    if warn:
        logger.warning(warn)
    # 工具层校验（目标路径）：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.WRITE, destination, overwrite=overwrite, source=source)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail=err, hint="请检查目标路径是否正确", user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    if warn:
        logger.warning(warn)
    if os.path.abspath(source) == os.path.abspath(destination):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail=f"源路径和目标路径相同: {source}", hint="源路径和目标路径不能相同", user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)

    result = await _move_file_impl(source_path=source, destination_path=destination, overwrite=overwrite)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if result.get("success"):
        llm_data = _build_move_file_llm_data("success", duration_ms, source, destination=destination, user_overwrite=overwrite)
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — operation_id 不命中任何专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(
            data={},
            llm_data=llm_data,
        )
    else:
        error_detail = result.get("error_detail", "移动文件失败")
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail=error_detail, hint="请检查移动操作的参数和文件状态", user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)