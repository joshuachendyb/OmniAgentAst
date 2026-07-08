# -*- coding: utf-8 -*-
"""
F7: copy_file — 复制文件

从file_tools.py拆分而来 — 小欧 2026-06-22
内聚: _copy_file_impl (纯逻辑版，不含build3)
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
from app.tools.tool_constants import ERR_FILE_COPY_FAILED
from app.utils.context_vars import _current_task_id

from app.tools.validate.tools_file_path_checker import validate_path, OpCategory
from app.utils.logger import logger



def _build_copy_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", extra_metrics: Optional[Dict[str, Any]] = None,
    hint: str = "", destination: str = "",
    user_recursive: Optional[bool] = None, user_overwrite: Optional[bool] = None,
    user_preserve_metadata: Optional[bool] = None,
) -> Dict[str, Any]:
    """copy_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint/destination参数"""
    _act_params = {"source": source, "destination": destination}
    if user_recursive is not None:
        _act_params["recursive"] = user_recursive
    if user_overwrite is not None:
        _act_params["overwrite"] = user_overwrite
    if user_preserve_metadata is not None:
        _act_params["preserve_metadata"] = user_preserve_metadata
    if exec_code == "error":
        detail = (extra_metrics or {}).get("detail", "复制失败")
        return {
            "summary": f"复制文件{source}，失败",
            "action": {"tool": "copy", "tool_zh": "复制文件", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "复制失败", "code": ERR_FILE_COPY_FAILED, "detail": detail, "hint": hint if hint else "请检查源文件路径和目标路径及权限"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
            "summary": f"复制成功: {source} -> {destination}",
        "action": {"tool": "copy", "tool_zh": "复制文件", "target": source, "params": _act_params},
        "status": {"exec_code": "success", "message": "复制成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics or {},
    }


async def copy(
    source: str,
    destination: str,
    recursive: bool = False,
    overwrite: bool = False,
    preserve_metadata: bool = True,
) -> Dict[str, Any]:
    """复制文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 修复计时铁规"""
    t0 = _time_mod.perf_counter()
    if not source or not source.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": "source不能为空"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)
    if not destination or not destination.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": "destination不能为空"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)
    # 工具层校验（源路径）：非空/保留字符/保留名/系统目录/源存在 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.EXISTS, source)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": err}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)
    if warn:
        logger.warning(warn)
    # 工具层校验（目标路径）：非空/保留字符/保留名/系统目录（跳过存在性，允许新建） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.WRITE, destination, overwrite=overwrite, source=source)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": err}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)
    if warn:
        logger.warning(warn)

    src = Path(source)
    dst = Path(destination)

    if src.resolve() == dst.resolve():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": "源路径和目标路径相同"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)

    if dst.exists() and not overwrite:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": f"目标已存在且overwrite=False: {destination}"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)
    from app.services.safety.file_safety import record_operation, execute_with_safety
    from app.db.models.operation_enums import OperationType

    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": "No active task"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)

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
                        logger.warning(f"[copy] recursive模式: 目标目录已存在,将删除后重建: {dst}")
                        if not os.access(str(dst), os.W_OK):
                            os.chmod(str(dst), os.stat(str(dst)).st_mode | 0o200)
                        shutil.rmtree(str(dst))
                    if preserve_metadata:
                        shutil.copytree(str(src), str(dst))
                    else:
                        shutil.copytree(str(src), str(dst), copy_function=shutil.copy)
                else:
                    dst.mkdir(exist_ok=True)
            return True

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24
        if operation_id:
            success = await asyncio.to_thread(execute_with_safety, operation_id=operation_id, operation_func=_copy_sync)
        else:
            logger.info("Database unavailable, executing copy operation without recording")
            success = await asyncio.to_thread(_copy_sync)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if success:
            extra_m = {}
            src_size = None
            src_mtime = None
            if src.exists():
                try:
                    s = src.stat()
                    src_size = s.st_size
                    src_mtime = s.st_mtime
                except Exception:
                    pass
            if dst.exists():
                try:
                    extra_m["bytes"] = {"value": dst.stat().st_size, "text": f"{dst.stat().st_size}字节"}
                except Exception:
                    pass
            llm_data = _build_copy_file_llm_data("success", duration_ms, source, destination=destination, extra_metrics=extra_m, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
            # ---- observation_formatter route -------------------------------------------
            # branch: #21 fallback (key:val)
            # trigger: 无上述20条分支匹配 — operation_id/source/destination 不命中专用分支
            # handler: _format_scalar_data(data) — key | value 单行列表
            # file:    observation_formatter.py:214
            # ------------------------------------------------------------------------------
            return build_success(
                data={"source_size": src_size, "mtime": src_mtime},
                llm_data=llm_data)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": "复制失败"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": str(e)}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)
