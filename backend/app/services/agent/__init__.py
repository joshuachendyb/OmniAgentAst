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
2. 用户输入预处理（PreprocessingPipeline, TextCorrector, IntentClassifier）
3. 意图管理（Intent, IntentRegistry）
4. 文件操作服务（FileTools, FileSafety等）
"""

# ============================================================================
# 新框架导出
# ============================================================================
from .preprocessing import PreprocessingPipeline, TextCorrector, IntentClassifier
from .base import BaseAgent
from .tool_parser import ToolParser
from .tool_executor import ToolExecutor
from .intent import Intent, IntentRegistry

# ============================================================================
# 原 file_operations 导出
# ============================================================================
from .safety import (
    FileOperationSafety,
    FileSafetyConfig,
    get_file_safety_service,
)
from .session import (
    FileOperationSessionService,
    get_session_service,
)
from .tools import (
    FileTools,
    get_file_tools,
)

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
    # FileOperationAgent
    "FileOperationAgent",
    # 原 file_operations
    "FileOperationSafety",
    "FileSafetyConfig",
    "get_file_safety_service",
    "FileOperationSessionService",
    "get_session_service",
    "FileTools",
    "get_file_tools",
]
