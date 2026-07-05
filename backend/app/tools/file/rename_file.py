# -*- coding: utf-8 -*-
"""
F13: rename_file — 重命名文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

import time as _time_mod
from pathlib import Path
from typing import Any, Dict

from app.tools.file.move_file import _move_file_impl
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_FILE_RENAME_FAILED
from app.tools.validate.tools_file_path_checker import validate_path, OpCategory


def _build_rename_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", new_name: str = "", detail: str = "", hint: str = "",
    user_destination: str = "",
) -> Dict[str, Any]:
    """rename_file的llm_data构建函数 — 小健 2026-06-22 — 小沈 2026-07-05 新增hint参数"""
    _act_params = {"source": source, "new_name": new_name}
    if user_destination:
        _act_params["destination"] = user_destination
    if exec_code == "error":
        return {
            "summary": f"重命名失败: {source}",
            "action": {"tool": "rename", "tool_zh": "重命名", "target": source, "params": _act_params},
            "status": {"exec_code": "error", "message": "重命名失败", "code": ERR_FILE_RENAME_FAILED, "detail": detail, "hint": hint if hint else "请检查源路径和新名称"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _summary = f"重命名 {source} → {new_name}" if new_name else f"重命名 {source}"
    return {
        "summary": _summary,
        "action": {"tool": "rename", "tool_zh": "重命名", "target": source, "params": _act_params},
        "status": {"exec_code": "success", "message": "重命名成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


async def rename(
    source: str,
    destination: str,
) -> Dict[str, Any]:
    """重命名文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：独立builder — 小欧 2026-07-04 增加空串验证"""
    t0 = _time_mod.perf_counter()

    if not source or not source.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, detail="source不能为空", hint="请提供源文件路径", user_destination=destination)
        return build_error(data={"error_detail": "source不能为空", "params": {"source": source}}, llm_data=llm_data)
    if not destination or not destination.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, detail="destination不能为空", hint="请提供目标文件路径", user_destination=destination)
        return build_error(data={"error_detail": "destination不能为空", "params": {"destination": destination}}, llm_data=llm_data)

    # 工具层校验：非空/保留字符/保留名/系统目录/路径存在 — 小欧 2026-07-04
    # Safety层后续校验：路径黑名单/白名单/路径穿越/权限检查 — 小欧 2026-07-04
    is_valid, err, _ = validate_path(OpCategory.EXISTS, source)
    if not is_valid:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, detail=err, hint="请检查源路径是否正确", user_destination=destination)
        return build_error(data={"error_detail": err, "params": {"source": source}}, llm_data=llm_data)

    WINDOWS_RESERVED_CHARS = '<>:"/\\|?*'
    if any(c in destination for c in WINDOWS_RESERVED_CHARS):
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, detail=f"包含Windows保留字符: {destination}", hint="文件名包含Windows保留字符，请修改", user_destination=destination)
        return build_error(data={"error_detail": f"文件名包含Windows保留字符: {destination}", "params": {"destination": destination}}, llm_data=llm_data)

    src = Path(source)
    new_name = Path(destination).name
    dst = src.parent / new_name

    if src.name == new_name:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("success", duration_ms, source, new_name=new_name, user_destination=destination)
        llm_data["summary"] = f"重命名 {source} → {new_name}（名称相同，无操作）"
        llm_data["status"]["message"] = "名称相同，无需重命名"
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val) — skipped path
        # trigger: 无上述20条分支匹配 — skipped/reason 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data={"skipped": True, "reason": "名称相同，无需操作"}, llm_data=llm_data)

    result = await _move_file_impl(source_path=source, destination_path=str(dst), overwrite=False)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if result.get("success"):
        llm_data = _build_rename_file_llm_data("success", duration_ms, source, new_name=new_name, user_destination=destination)
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val)
        # trigger: 无上述20条分支匹配 — operation_id 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(
            data={"operation_id": result.get("operation_id")},
            llm_data=llm_data,
        )
    else:
        error_detail = result.get("error_detail", "重命名失败")
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, new_name=new_name, detail=error_detail, hint="重命名失败，请检查文件状态", user_destination=destination)
        return build_error(data={"error_detail": error_detail, "params": result.get("params", {})}, llm_data=llm_data)