# -*- coding: utf-8 -*-
"""Tools 模块 - 按意图类型组织的工具集"""

from app.services.tools.registry import (
    ToolRegistry,
    ToolCategory,
    ToolMetadata,
    tool_registry,
    get_tools_dict,
    get_tools_from_file_registry,
    register_tool,
    get_registered_tools,
    get_tool,
)

from app.services.tools.tool_config import (
    ToolConfig,
    tool_config,
    get_tool_config,
)

from app.services.tools import file  # 触发file工具注册
from app.services.tools import time  # 触发time工具注册
from app.services.tools import shell  # 触发shell工具注册
from app.services.tools import network  # 触发network工具注册
from app.services.tools import env  # 触发env工具注册
from app.services.tools import system  # 触发system工具注册
from app.services.tools import database  # 触发database工具注册
from app.services.tools import desktop  # 触发desktop工具注册
from app.services.tools import registry_tools  # 触发registry_tools工具注册（小沈-2026-05-02）
from app.services.tools import data_format  # 触发data_format工具注册（小沈-2026-05-02）
from app.services.tools import code_execution  # 触发code_execution工具注册（小沈-2026-05-02）
from app.services.tools import data_analysis  # 触发data_analysis工具注册（小沈-2026-05-02）

__all__ = [
    # registry
    "ToolRegistry",
    "ToolCategory", 
    "ToolMetadata",
    "tool_registry",
    "get_tools_dict",
    "get_tools_from_file_registry",
    "register_tool",
    "get_registered_tools",
    "get_tool",
    # config
    "ToolConfig",
    "tool_config",
    "get_tool_config",
    # categories
    "file",
    "network",
    "system",
    "database",
    "desktop",
    "time",
    "shell",
    "registry_tools",
    "data_format",
    "code_execution",
    "data_analysis",
]
