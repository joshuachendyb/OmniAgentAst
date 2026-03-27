# -*- coding: utf-8 -*-
"""
Agent 模块 - 多意图处理架构 + 文件操作服务

【合并时间】2026-03-21 小沈
【合并依据】设计文档12.2节，第零步执行
【来源】
  - 新框架: _NEW_framework_20260321/__init__.py
  - 原file_operations: _OLD_file_operations_20260321/__init__.py

提供：
1. 通用 Agent 框架（BaseAgent, ToolParser, ToolExecutor）
2. 文件操作服务（FileTools, FileSafety等）

【重构 2026-03-22 小沈】
- preprocessing 和 intent 已移至 services/ 下独立目录
- 旧路径导入通过懒加载保持向后兼容
"""

from __future__ import annotations
from typing import TYPE_CHECKING

# ============================================================================
# 新框架导出（无循环依赖）
# ============================================================================
from app.services.preprocessing import PreprocessingPipeline, TextCorrector, IntentClassifier
from app.services.intent import Intent, IntentRegistry
from .base_react import BaseAgent
from .tool_parser import ToolParser
from .tool_executor import ToolExecutor
from .session_base import SessionServiceBase, SessionStatsMixin

# ============================================================================
# 原 file_operations 导出（通过懒加载避免循环依赖）
# ============================================================================

if TYPE_CHECKING:
    from app.services.safety.file.file_safety import (
        FileOperationSafety,
        FileSafetyConfig,
        get_file_safety_service,
    )
    from .session import (
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
        from .session import (
            FileOperationSessionService,
            get_session_service,
        )
        return locals()[name]
    if name in ("FileTools", "get_file_tools"):
        from app.services.tools.file.file_tools import FileTools, get_file_tools
        return locals()[name]
    if name == "IntentAgent":
        from .file_react import FileReactAgent
        return FileReactAgent
    if name == "IntentReactAgent":
        from .file_react import FileReactAgent
        return FileReactAgent
    if name == "FileReactAgent":
        from .file_react import FileReactAgent
        return FileReactAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    # 新框架
    "BaseAgent",
    "ToolParser",
    "ToolExecutor",
    "PreprocessingPipeline",
    "TextCorrector",
    "IntentClassifier",
    "Intent",
    "IntentRegistry",
    "SessionServiceBase",
    "SessionStatsMixin",
    # 原 file_operations（通过__getattr__懒加载）
    "FileOperationSafety",
    "FileSafetyConfig",
    "get_file_safety_service",
    "FileOperationSessionService",
    "get_session_service",
    "FileTools",
    "get_file_tools",
    "IntentAgent",
    "IntentReactAgent",
    "FileReactAgent",
]
