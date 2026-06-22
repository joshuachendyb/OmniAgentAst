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


def _build_rename_file_llm_data(
    exec_code: str, duration_ms: int,
    source: str = "", detail: str = "",
) -> Dict[str, Any]:
    """rename_file的llm_data构建函数 — 小健 2026-06-22"""
    if exec_code == "error":
        return {
            "summary": f"重命名失败: {detail}",
            "action": {"tool": "rename_file", "tool_zh": "重命名", "target": source, "params": {}},
            "status": {"exec_code": "error", "message": "重命名失败", "code": "", "detail": detail, "hint": ""},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    return {
        "summary": f"重命名成功: {source}",
        "action": {"tool": "rename_file", "tool_zh": "重命名", "target": source, "params": {}},
        "status": {"exec_code": "success", "message": "重命名成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {},
    }


async def rename_file(
    source: str,
    destination: str,
) -> Dict[str, Any]:
    """重命名文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件 — 小健 2026-06-22 重构：独立builder"""
    t0 = _time_mod.perf_counter()
    src = Path(source)
    new_name = Path(destination).name
    dst = src.parent / new_name

    if src.name == new_name:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_rename_file_llm_data("success", duration_ms, source)
        return build_success(data={}, llm_data=llm_data)

    result = await _move_file_impl(source_path=source, destination_path=str(dst), overwrite=False)
    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

    if result.get("success"):
        llm_data = _build_rename_file_llm_data("success", duration_ms, source)
        return build_success(
            data={"operation_id": result.get("operation_id")},
            llm_data=llm_data,
        )
    else:
        error_detail = result.get("error_detail", "重命名失败")
        llm_data = _build_rename_file_llm_data("error", duration_ms, source, detail=error_detail)
        return build_error(data={"error_detail": error_detail, "params": result.get("params", {})}, llm_data=llm_data)