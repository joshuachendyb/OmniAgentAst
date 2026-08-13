
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 解包execute_with_safety返回的(success, detail), 用真实错误细节替代笼统"复制失败"提示(根因: execute_with_safety原吞掉细节只返bool), 修复LLM拿不到真因无法自我纠正的问题。
# 2026-07-20 - 小欧 - 去噪去重 refactor:
#   移除 source_size/mtime 噪声(data={}
#   data 改为空字典 {}，信息全部由 llm_data
#   承载，formatter 路由改走 #0 空data分支
# 2026-07-26 - 小欧 - recursive模式删除已存在目标目录时,shutil.rmtree缺onerror,子目录中只读文件导致WinError 5拒绝访问崩溃。
#   增_remove_readonly闭包函数+onerror参数,与delete_file.py/operation_cleanup.py保持一致。
# 2026-08-11 - 小欧 - 防自嵌套(北京老陈驱动): recursive复制目标在源内部→copytree无限递归自复制生成套娃垃圾
#   (shutil_demo/backup/shutil_demo/backup/... 历史事故源头), 并触发WinError206超长路径; 复制前拒绝目标在源内部
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1下沉: task_id ContextVar 迁至 app.tools.context, _current_task_id import 由 app.services.task.task_context 改 app.tools.context,
#   消除 tools 层对 app.services 越层依赖(守护测试 tools 禁 app.services 规则), 行为零变化(同一 ContextVar 对象)
# 2026-08-12 - 小欧 - A1后半面(4.1.7定案): 删除 from app.safety import record_operation/execute_with_safety,
#   改为 get_current_hooks() 取安全 hooks(record_operation/execute_with_safety 两方法签名与 operation_record 一致), 消除 tools→safety 越层
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
# 2026-08-13 - 小沈 - BUG-3修复(三堂会审): get_current_hooks() 改 get_current_hooks_or_noop() 兜底返回 NoOpHooks,
#   消除入口未注入时 _hooks.record_operation() NPE(如测试直接调工具函数), 行为零退化(生产路径已注入不变)
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
from app.tools.context import _current_task_id, get_current_hooks_or_noop  # A1: ContextVar hooks — 小欧 2026-08-12; BUG-3修复 — 小沈 2026-08-13

from app.tools.validate.file_path_checker import validate_path, OpCategory  # 统一错误提示 - 小欧 2026-07-12
from app.tools.toolhelper.error_hints import hint_for_write_error
from app.logger import logger
from app.db.models.operation_models import OperationType



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
    path: str,
    dest: str,
    recursive: bool = False,
    overwrite: bool = False,
    preserve_metadata: bool = True,
) -> Dict[str, Any]:
    """复制文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 修复计时铁规 — 小欧 2026-07-11 路径参数统一为path/dest"""
    t0 = _time_mod.perf_counter()
    # 路径参数统一为path/dest,桥接到内部变量source/destination — 小欧 2026-07-11
    source = path
    destination = dest
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

    # 2026-08-11 小欧 防自嵌套: 递归复制目标在源内部→copytree把dst当源子目录持续自我复制(套娃),
    #   历史事故源头(shutil_demo\backup\shutil_demo\... 无限嵌套→备份WinError206); 拒绝目标在源内部
    if recursive and src.is_dir():
        try:
            if dst.resolve().is_relative_to(src.resolve()):
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": f"目标路径位于源目录内部,禁止递归复制: {destination}"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
                return build_error(data={}, llm_data=llm_data)
        except ValueError:
            pass

    if dst.exists() and not overwrite:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": f"目标已存在且overwrite=False: {destination}"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)
    task_id = _current_task_id.get()
    if not task_id:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": "No active task"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)

    try:
        _hooks = get_current_hooks_or_noop()  # A1: ContextVar 取安全 hooks(BUG-3修复: _or_noop 兜底防 NPE) — 小沈 2026-08-13
        operation_id = _hooks.record_operation(
            task_id=task_id,
            operation_type=OperationType.COPY,
            source_path=src,
            destination_path=dst,
            sequence_number=0,
        )

        def _remove_readonly(func, path, excinfo):
            """解除只读属性后重试 — 小欧 2026-07-26"""
            os.chmod(path, os.stat(path).st_mode | 0o200)
            func(path)

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
                        shutil.rmtree(str(dst), onerror=_remove_readonly)
                    if preserve_metadata:
                        shutil.copytree(str(src), str(dst))
                    else:
                        shutil.copytree(str(src), str(dst), copy_function=shutil.copy)
                else:
                    dst.mkdir(exist_ok=True)
            return True

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24
        if operation_id:
            success, detail = await asyncio.to_thread(_hooks.execute_with_safety, operation_id=operation_id, operation_func=_copy_sync)
        else:
            logger.info("Database unavailable, executing copy operation without recording")
            success = await asyncio.to_thread(_copy_sync)

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        if success:
            extra_m = {}
            if dst.exists():
                try:
                    extra_m["bytes"] = {"value": dst.stat().st_size, "text": f"{dst.stat().st_size}字节"}
                except Exception:
                    pass
            llm_data = _build_copy_file_llm_data("success", duration_ms, source, destination=destination, extra_metrics=extra_m, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
            # ---- observation_formatter route -------------------------------------------
            # branch: #0 空data (L73)
            # trigger: data 为 {} → if not data: return ""
            # handler: 直接返回空字符串
            # file:    observation_formatter.py:73-74
            # ------------------------------------------------------------------------------
            return build_success(data={}, llm_data=llm_data)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": detail or "复制失败"}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata)
        return build_error(data={}, llm_data=llm_data)

    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_copy_file_llm_data("error", duration_ms, source, destination=destination, extra_metrics={"detail": str(e)}, user_recursive=recursive, user_overwrite=overwrite, user_preserve_metadata=preserve_metadata, hint=hint_for_write_error(e, Path(source).name))  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)

