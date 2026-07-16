# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 解包execute_with_safety返回的(success, detail), 用真实错误细节替代笼统"删除文件失败,safety拦截"提示(根因: execute_with_safety原吞掉细节只返bool), 修复LLM拿不到真因无法自我纠正的问题。
# 2026-07-15 - 小欧 - _force_delete_sync返(bool,str)透传真实失败原因, 替代原返bool(False)导致_delete_sync包装(False,"permanent")致error_detail=模式字串而非真因。
"""
F12: delete_file — 删除文件

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
from app.tools.tool_constants import ERR_FILE_DELETE_FAILED
from app.services.task.task_context import _current_task_id
from app.db.models.operation_models import OperationType

from app.tools.validate.file_path_checker import validate_path, OpCategory, hint_for_write_error  # 统一错误提示 - 小欧 2026-07-12
from app.services.safety import record_operation, execute_with_safety
from app.logger import logger



def remove_readonly(func, path, excinfo):
    """解除只读属性后重试（共用函数，operation_cleanup也使用）— 小沈 2026-07-07
    
    说明：Windows下shutil.rmtree遇到只读文件会[WinError 5]拒绝访问。
    因为备份用的是shutil.copy2，原文件的只读属性被完整保留。
    onerror回调先chmod加写权限再重新执行删除，解决此问题。
    """
    os.chmod(path, os.stat(path).st_mode | 0o200)
    func(path)


def _force_delete_sync(path: Path, recursive: bool = False) -> Tuple[bool, str]:
    """永久删除:目录(recursive→rmtree否则rmdir) / 文件→unlink — 小沈重构 2026-05-25 — 小欧 2026-06-22
    2026-07-15: 返回(bool,str)透传失败真正原因,替代原返bool导致真因丢失"""
    try:
        if path.is_dir():
            if recursive:
                shutil.rmtree(str(path), onerror=remove_readonly)
            else:
                path.rmdir()
        else:
            if path.exists() and not os.access(str(path), os.W_OK):
                path.chmod(path.stat().st_mode | 0o200)
            path.unlink()
        return True, "permanent"
    except Exception as e:
        err_msg = str(e) or f"永久删除失败: {path}"
        logger.error(f"[_force_delete_sync] 删除失败: {path}, 错误: {e}")
        return False, err_msg


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
    return _force_delete_sync(path, recursive)


def _build_delete_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "", extra_metrics: Optional[Dict] = None,
    hint: str = "",
    user_recursive: Optional[bool] = None, user_force: Optional[bool] = None,
) -> Dict[str, Any]:
    """delete_file的llm_data构建函数 — 小健 2026-06-21 — 小欧 2026-06-22 — 小沈 2026-07-05 新增hint参数"""
    _act_params = {"source": source}
    if user_recursive is not None:
        _act_params["recursive"] = user_recursive
    if user_force is not None:
        _act_params["force"] = user_force
    extra_metrics = extra_metrics or {}
    if exec_code == "error":
        return {
            "summary": f"删除{source}，失败",
            "action": {"tool": "delete", "tool_zh": "删除", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "删除失败", "code": ERR_FILE_DELETE_FAILED, "detail": detail, "hint": hint if hint else "请检查文件是否存在"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _suffix = extra_metrics.get("status", {}).get("text", "") or extra_metrics.get("deleted", {}).get("text", "")
    return {
        "summary": f"删除{source}，成功: {_suffix}" if _suffix else f"删除{source}，成功",
        "action": {"tool": "delete", "tool_zh": "删除", "target": source, "params": _act_params},
        "status": {"exec_code": "success", "message": "删除成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": extra_metrics,
    }


async def _delete_file_impl(
    file_path: str, recursive: bool = False, force: bool = False,
) -> Dict[str, Any]:
    """删除文件或目录实现 — 小欧 2026-06-22 — 小健 2026-06-22 重构：只返回raw dict，不含build3/llm_data"""

    path = Path(file_path)
    try:
        if path.is_dir() and not recursive:
            return {"success": False, "error_detail": "删除非空目录需要设置recursive=True", "params": {"source": file_path}}
        if not path.exists():
            return {"success": True, "action": "delete", "source": file_path, "already_deleted": True}

        task_id = _current_task_id.get()
        if not task_id:
            return {"success": False, "error_detail": "当前没有活跃任务ID", "params": {"source": file_path}}

        operation_id = record_operation(
            task_id=task_id, operation_type=OperationType.DELETE,
            source_path=path, sequence_number=0,
        )

        def _delete_sync():
            if force:
                return _force_delete_sync(path, recursive)
            return _send2trash_sync(path, recursive)

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24 — 小沈 2026-07-07 execute_with_safety返回(bool,str)
        if operation_id:
            is_ok, detail = await asyncio.to_thread(execute_with_safety, operation_id, operation_func=_delete_sync)
            method = "permanent" if force else "send2trash"
        else:
            logger.info("Database unavailable, executing delete operation without recording")
            is_ok, method = await asyncio.to_thread(_delete_sync)

        if is_ok:
            return {"success": True, "deleted_path": str(path), "mode": method}
        # 透传真实错误细节，避免退化为笼统提示 — 小欧 2026-07-15
        return {"success": False, "error_detail": detail or "删除文件失败,safety拦截", "params": {"source": file_path}}

    except Exception as e:
        logger.error(f"Failed to delete {file_path}: {e}")
        return {"success": False, "error_detail": str(e), "hint": hint_for_write_error(e, Path(file_path).name), "params": {"source": file_path}}  # 统一错误提示 - 小欧 2026-07-12


async def delete(
    path: str,
    recursive: bool = False,
    force: bool = False,
) -> Dict[str, Any]:
    """删除文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：主函数负责计时+builder+build3 — 小欧 2026-07-11 路径参数统一为path"""
    t0 = _time_mod.perf_counter()
    # 路径参数统一为path,桥接到内部变量source — 小欧 2026-07-11
    source = path
    if not source or not source.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_file_llm_data("error", duration_ms, source, detail="source不能为空", user_recursive=recursive, user_force=force)
        return build_error(data={}, llm_data=llm_data)
    # 工具层校验：非空/保留字符/保留名/系统目录/路径存在（含递归/强制警告） — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, warn = validate_path(OpCategory.EXISTS, source, recursive=recursive, force=force)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_delete_file_llm_data("error", duration_ms, source, detail=err, user_recursive=recursive, user_force=force)
        return build_error(data={}, llm_data=llm_data)
    if warn:
        logger.warning(warn)

    result = await _delete_file_impl(file_path=source, recursive=recursive, force=force)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if result.get("success"):
        if result.get("already_deleted"):
            llm_data = _build_delete_file_llm_data("success", duration_ms, source, extra_metrics={"status": {"value": "already_deleted", "text": "文件已删除"}}, user_recursive=recursive, user_force=force)
            # ---- observation_formatter route -------------------------------------------
            # branch: #0 空data (L73)
            # trigger: data 为 {} → if not data: return ""
            # handler: 直接返回空字符串
            # file:    observation_formatter.py:73-74
            # ------------------------------------------------------------------------------
            return build_success(data={}, llm_data=llm_data)
        delete_mode = "永久删除" if force else "放入回收站"
        extra_m = {"mode": {"value": result.get("mode", ""), "text": delete_mode}}
        llm_data = _build_delete_file_llm_data("success", duration_ms, source, extra_metrics=extra_m, user_recursive=recursive, user_force=force)
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — operation_id/deleted_path 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(
            data={},
            llm_data=llm_data,
        )
    else:
        error_detail = result.get("error_detail", "删除文件失败")
        if "recursive" in error_detail.lower():
            error_hint = "请设置recursive=True重新删除"
        elif "safety" in error_detail.lower():
            error_hint = "文件被安全策略拦截，请检查权限"
        elif "任务ID" in error_detail:
            error_hint = "请先创建任务再删除"
        else:
            error_hint = result.get("hint") or "请检查文件是否存在和权限"  # 统一错误提示 - 小欧 2026-07-12
        llm_data = _build_delete_file_llm_data("error", duration_ms, source, detail=error_detail, hint=error_hint, user_recursive=recursive, user_force=force)
        return build_error(data={}, llm_data=llm_data)