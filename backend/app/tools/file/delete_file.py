# -*- coding: utf-8 -*-
"""
F12: delete_file — 删除文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

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


def _remove_readonly(func, path, excinfo):
    """force删除时解除只读属性的回调 — 小健 2026-05-02 — 小欧 2026-06-22"""
    os.chmod(path, os.stat(path).st_mode | 0o200)
    func(path)


def _force_delete_sync(path: Path, recursive: bool = False) -> bool:
    """永久删除:目录(recursive→rmtree否则rmdir) / 文件→unlink — 小沈重构 2026-05-25 — 小欧 2026-06-22"""
    try:
        if path.is_dir():
            if recursive:
                shutil.rmtree(str(path), onerror=_remove_readonly)
            else:
                path.rmdir()
        else:
            if path.exists() and not os.access(str(path), os.W_OK):
                path.chmod(path.stat().st_mode | 0o200)
            path.unlink()
        return True
    except Exception as e:
        logger.error(f"[_force_delete_sync] 删除失败: {path}, 错误: {e}")
        return False


def _send2trash_sync(path: Path, recursive: bool = False) -> Tuple[bool, str]:
    """尝试放入回收站,失败则回退到永久删除 — 小沈重构 2026-05-25 — 小欧 2026-06-22"""
    try:
        import send2trash
        send2trash.send2trash(str(path))
        return True, "send2trash"
    except ImportError:
        logger.warning("send2trash未安装,回退到永久删除")
    except Exception as e:
        logger.warning(f"send2trash失败: {e},回退到永久删除")
    return _force_delete_sync(path, recursive), "permanent"


def _build_delete_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "", extra_metrics: Optional[Dict] = None,
) -> Dict[str, Any]:
    """delete_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22"""
    extra_metrics = extra_metrics or {}
    if exec_code == "error":
        return {
            "summary": f"删除失败: {detail}",
            "action": {"tool": "delete_file", "tool_zh": "删除", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "删除失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"删除成功: {source}",
        "action": {"tool": "delete_file", "tool_zh": "删除", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "删除成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics,
    }


async def _delete_file_impl(
    file_path: str, recursive: bool = False, force: bool = False,
) -> Dict[str, Any]:
    """删除文件或目录实现 — 小欧 2026-06-22"""
    t0 = _time_mod.perf_counter()
    is_valid, error_msg = _validate_path(file_path)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_file_llm_data("error", duration_ms, file_path, detail=error_msg)
        return build_error(data={"error_detail": error_msg, "params": {"source": file_path}}, llm_data=llm_data)

    path = Path(file_path)
    try:
        if not path.exists():
            llm_data = _build_delete_file_llm_data("success", 0, file_path)
            return build_success(data={"action": "delete", "source": file_path}, llm_data=llm_data)

        task_id = _current_task_id.get()
        if not task_id:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_delete_file_llm_data("error", duration_ms, file_path, detail="当前没有活跃任务ID")
            return build_error(data={"error_detail": "当前没有活跃任务ID", "params": {"source": file_path}}, llm_data=llm_data)

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.DELETE,
            source_path=path, sequence_number=0,
        )

        def _delete_sync():
            if force:
                return _force_delete_sync(path, recursive), "permanent"
            return _send2trash_sync(path, recursive)

        is_ok, method = await asyncio.to_thread(execute_with_safety, operation_id, operation_func=_delete_sync)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if is_ok:
            delete_mode = "永久删除" if force else "放入回收站"
            extra_m = {"mode": {"value": method, "text": delete_mode}}
            llm_data = _build_delete_file_llm_data("success", duration_ms, file_path, extra_metrics=extra_m)
            return build_success(
                data={"operation_id": operation_id, "deleted_path": str(path), "mode": method},
                llm_data=llm_data,
            )
        else:
            llm_data = _build_delete_file_llm_data("error", duration_ms, file_path, detail="删除文件失败,safety拦截")
            return build_error(data={"error_detail": "删除文件失败,safety拦截", "params": {"source": file_path}}, llm_data=llm_data)

    except Exception as e:
        logger.error(f"Failed to delete {file_path}: {e}")
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_file_llm_data("error", duration_ms, file_path, detail=str(e))
        return build_error(data={"error_detail": str(e), "params": {"source": file_path}}, llm_data=llm_data)


async def delete_file(
    source: str,
    recursive: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """删除文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    src_path = Path(source)
    if not src_path.exists():
        llm_data = _build_delete_file_llm_data("success", 0, source, extra_metrics={"status": "already_deleted"})
        return build_success(data={"action": "delete", "source": source}, llm_data=llm_data)
    return await _delete_file_impl(file_path=source, recursive=recursive, force=force)