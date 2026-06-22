# -*- coding: utf-8 -*-
"""
F13: rename_file — 重命名文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。

from pathlib import Path
from typing import Any, Dict

from app.tools.file.move_file import _move_file_impl, _build_move_file_llm_data
from app.tools.tool_response import build_success


async def rename_file(
    source: str,
    destination: str,
) -> Dict[str, Any]:
    """重命名文件/目录 — 小沈 2026-06-16 — 小欧 2026-06-22 独立文件"""
    src = Path(source)
    new_name = Path(destination).name
    dst = src.parent / new_name
    if src.name == new_name:
        llm_data = _build_move_file_llm_data("success", 0, source, extra_metrics={"status": "no_change"})
        return build_success(data={"action": "rename", "source": source, "destination": str(dst)}, llm_data=llm_data)
    return await _move_file_impl(source_path=source, destination_path=str(dst), overwrite=False)