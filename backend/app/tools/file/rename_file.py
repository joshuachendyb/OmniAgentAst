# -*- coding: utf-8 -*-
"""
F13: rename_file — 重命名文件

从file_tools.py拆分而来 — 小欧 2026-06-22
"""

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