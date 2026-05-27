# -*- coding: utf-8 -*-
"""
懒加载兼容模块 — 原 file_operations 的向后兼容导入

【合并时间】2026-03-21 小沈
【重构 2026-05-27 小欧】从 __init__.py 抽出，保持向后兼容

当 `from app.services.agent import FileTools` 等旧路径导入时，
通过 __getattr__ 懒加载实际模块。
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.safety.file.file_safety import (
        FileOperationSafety,
        FileSafetyConfig,
        get_file_safety_service,
    )
    from app.services.agent.session import (
        FileOperationSessionService,
        get_session_service,
    )
    from app.services.tools.file.file_tools import (
        FileTools,
        get_file_tools,
    )


def __getattr__(name: str):
    if name in ("FileOperationSafety", "FileSafetyConfig", "get_file_safety_service"):
        from app.services.safety.file.file_safety import (
            FileOperationSafety,
            FileSafetyConfig,
            get_file_safety_service,
        )
        return locals()[name]
    if name in ("FileOperationSessionService", "get_session_service"):
        from app.services.agent.session import (
            FileOperationSessionService,
            get_session_service,
        )
        return locals()[name]
    if name in ("FileTools", "get_file_tools"):
        from app.services.tools.file.file_tools import FileTools, get_file_tools
        return locals()[name]
    raise AttributeError(f"module 'app.services.agent' has no attribute {name!r}")
