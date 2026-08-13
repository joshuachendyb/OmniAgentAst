
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 解包execute_with_safety返回的(success, detail), 用真实错误细节替代笼统"移动文件失败"提示(根因: execute_with_safety原吞掉细节只返bool), 修复LLM拿不到真因无法自我纠正的问题。
# 2026-07-26 - 小沈 - _move_sync预期失败改raise为return(False,msg)并对齐6工具范式; else分支解包tuple对齐executor返回格式
# 2026-07-26 - 小欧 - overwrite模式shutil.rmtree缺onerror,子目录只读文件导致WinError 5崩溃。增_remove_readonly闭包+onerror,对齐delete_file.py模式。
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1下沉: task_id ContextVar 迁至 app.tools.context, _current_task_id import 由 app.services.task.task_context 改 app.tools.context,
#   消除 tools 层对 app.services 越层依赖(守护测试 tools 禁 app.services 规则), 行为零变化(同一 ContextVar 对象)
# 2026-08-12 - 小欧 - A1后半面(4.1.7定案): 删除 from app.safety import record_operation/execute_with_safety,
#   改为 get_current_hooks() 取安全 hooks, 消除 tools→safety 越层; task_id 仍 _current_task_id.get()
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
# 2026-08-13 - 小沈 - BUG-3修复(三堂会审): get_current_hooks() 改 get_current_hooks_or_noop() 兜底返回 NoOpHooks,
#   消除入口未注入时 _hooks.record_operation() NPE(如测试直接调工具函数), 行为零退化(生产路径已注入不变)
# 2026-08-13 - 小欧 - 三堂会审修复#34/#4/#5: #34 同路径判定 abspath 统一 resolve()(解析盘符大小写/符号链接,
#   与 impl 口径一致); #4 自嵌套防护(目标在源目录子树内拒绝, 主函数+impl 双层, 防 shutil.move 递归复制进自身子树,
#   对齐 copy_file 防护); #5 目标存在探测/删除/移动/os 调用全链 to_win_long_path 长路径化(仅NT生效),
#   深嵌套路径不再触发 WinError 206
"""
F10: move_file — 移动文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
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
from app.tools.context import _current_task_id, get_current_hooks_or_noop  # A1: ContextVar hooks — 小欧 2026-08-12; BUG-3修复 — 小沈 2026-08-13
from app.db.models.operation_models import OperationType
from app.tools.validate.file_path_checker import validate_path, OpCategory  # 统一错误提示 - 小欧 2026-07-12
from app.tools.toolhelper.error_hints import hint_for_write_error
from app.utils.path_utils import to_win_long_path  # #5长路径包裹 — 小欧 2026-08-13
from app.logger import logger



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

    # 2026-08-13 - 小欧 - 三堂会审修复#4: 自嵌套防护(主函数 move() 同款, impl 层兜底防直调函数绕过)
    if src.is_dir() and dst.resolve() != src.resolve() and src.resolve() in dst.resolve().parents:
        return {"success": False, "error_detail": f"目标路径位于源目录内部,禁止移动造成递归: {source_path}", "params": {"source": source_path, "destination": destination_path}}

    if src.is_dir() and dst.is_file():
        return {"success": False, "error_detail": "不能移动目录到文件路径", "params": {"source": source_path, "destination": destination_path}}

    try:
        if not src.exists():
            return {"success": False, "error_detail": "源文件不存在", "params": {"source": source_path}}

        task_id = _current_task_id.get()
        if not task_id:
            return {"success": False, "error_detail": "当前没有活跃任务ID", "params": {"source": source_path}}

        _hooks = get_current_hooks_or_noop()  # A1: ContextVar 取安全 hooks(BUG-3修复: _or_noop 兜底防 NPE) — 小沈 2026-08-13
        operation_id = _hooks.record_operation(
            task_id=task_id, operation_type=OperationType.MOVE,
            source_path=src, destination_path=dst, sequence_number=0,
        )

        def _remove_readonly(func, path, excinfo):
            """解除只读属性后重试 — 小欧 2026-07-26"""
            _lp = to_win_long_path(Path(path))
            os.chmod(_lp, os.stat(_lp).st_mode | 0o200)
            func(path)

        def _move_sync():
            """返回(成功bool, 错误str) — 预期失败return而非raise,对齐6工具范式 — 小沈 2026-07-26"""
            # #5长路径: Windows下目标已存在探测/删除/移动统一走 \\?\ 前缀, 避免深嵌套路径WinError 206 — 小欧 2026-08-13
            _dst_lp = to_win_long_path(dst)
            if Path(_dst_lp).exists():
                if not overwrite:
                    return False, f"目标路径已存在: {dst},请设置overwrite=True"
                if not os.access(_dst_lp, os.W_OK):
                    os.chmod(_dst_lp, os.stat(_dst_lp).st_mode | 0o200)
                if Path(_dst_lp).is_dir():
                    logger.warning(f"[move] overwrite模式: 目标目录已存在,将删除后移动: {dst}")
                    shutil.rmtree(_dst_lp, onerror=_remove_readonly)
                else:
                    Path(_dst_lp).unlink()
            os.makedirs(to_win_long_path(dst.parent), exist_ok=True)
            shutil.move(to_win_long_path(src), _dst_lp)
            return True, None

        # 根据operation_id是否存在选择执行方式 — 小健 2026-06-24 — 小沈 2026-07-26 else分支解包tuple对齐executor
        if operation_id:
            success, detail = await asyncio.to_thread(_hooks.execute_with_safety, operation_id, operation_func=_move_sync)
        else:
            logger.info("Database unavailable, executing move operation without recording")
            raw = await asyncio.to_thread(_move_sync)
            success, detail = raw if isinstance(raw, tuple) else (raw, None)

        if success:
            # 小欧 2026-07-16 移除未消费的 operation_id 返回值(YAGNI, 调用方不读取)
            return {"success": True, "source": str(src), "destination": str(dst)}
        # 透传真实错误细节（如"目标路径已存在…请设置overwrite=True"），避免退化为笼统提示 — 小欧 2026-07-15
        return {"success": False, "error_detail": detail or "移动文件失败", "params": {"source": source_path, "destination": destination_path}}

    except Exception as e:
        logger.error(f"Failed to move {source_path} -> {destination_path}: {e}")
        return {"success": False, "error_detail": str(e), "hint": hint_for_write_error(e, Path(source_path).name), "params": {"source": source_path, "destination": destination_path}}  # 统一错误提示 - 小欧 2026-07-12


async def move(
    path: str,
    dest: str,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """移动文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：主函数负责计时+builder+build3 — 小欧 2026-07-11 路径参数统一为path/dest"""
    t0 = _time_mod.perf_counter()
    # 路径参数统一为path/dest,桥接到内部变量source/destination — 小欧 2026-07-11
    source = path
    destination = dest
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
    # 2026-08-13 - 小欧 - 三堂会审修复#34/#4: 同路径判定统一用 resolve()(原 abspath 不解析盘符
    #   大小写/符号链接, 与 _move_file_impl 口径不一); 并补自嵌套防护(目标在源子树内时
    #   shutil.move 会 copytree 进自身子树→递归/WinError206/数据丢失, 与 copy_file 防护对齐)
    _src_p = Path(source)
    _dst_p = Path(destination)
    if _src_p.resolve() == _dst_p.resolve():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail=f"源路径和目标路径相同: {source}", hint="源路径和目标路径不能相同", user_overwrite=overwrite)
        return build_error(data={}, llm_data=llm_data)
    if _src_p.is_dir() and _dst_p.resolve() != _src_p.resolve() and _src_p.resolve() in _dst_p.resolve().parents:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail=f"目标路径位于源目录内部,禁止移动造成递归: {source}", hint="目标路径不能是源目录的子目录", user_overwrite=overwrite)
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
        llm_data = _build_move_file_llm_data("error", duration_ms, source, destination=destination, detail=error_detail, hint=result.get("hint", "请检查移动操作的参数和文件状态"), user_overwrite=overwrite)  # 统一错误提示 - 小欧 2026-07-12
        return build_error(data={}, llm_data=llm_data)

