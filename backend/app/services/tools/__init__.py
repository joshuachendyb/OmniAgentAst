# -*- coding: utf-8 -*-
"""
Tools 模块 - 按意图类型组织的工具集

【2026-05-10 小沈重构】注册机制改造：
- 原设计：模块级import 15个子模块触发注册 → 启动时全量注册118个工具+118条日志
- 新设计：按需注册，首次请求时调用 ensure_tools_registered() 触发
- 原因：tools/__init__.py 被 base_react.py 的 import tools.registry 间接触发，
         导致启动时就全量注册，而非请求时按需注册

调用链路（改造后）：
  启动时: app.main → routes → base_react → import tools.registry → 只加载registry，不触发注册
  请求时: Agent.__init__() → _init_tools_and_executor() → ensure_tools_registered() → 首次触发注册
"""

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


_tools_registered = False


def ensure_tools_registered() -> None:
    """确保所有工具已注册（按需，仅首次调用时执行）- 小沈 2026-05-10
    
    改造前：tools/__init__.py 模块级import 15个子模块，启动时全量注册
    改造后：首次请求时调用此函数触发注册，后续调用直接跳过
    
    调用位置：ReactAgentMixin._init_tools_and_executor()
    """
    global _tools_registered
    if _tools_registered:
        return

    from app.services.tools import file
    from app.services.tools import time
    from app.services.tools import shell
    from app.services.tools import network
    from app.services.tools import environment
    from app.services.tools import system
    from app.services.tools import database
    from app.services.tools import desktop
    from app.services.tools import data_format
    from app.services.tools import code_execution
    from app.services.tools import document
    from app.services.tools import support_tool

    _tools_registered = True
    from app.utils.logger import logger
    logger.info("[Tools] 所有工具已注册完成（按需触发）")


def is_tools_registered() -> bool:
    """检查工具是否已注册"""
    return _tools_registered


__all__ = [
    "ToolRegistry",
    "ToolCategory",
    "ToolMetadata",
    "tool_registry",
    "get_tools_dict",
    "get_tools_from_file_registry",
    "register_tool",
    "get_registered_tools",
    "get_tool",
    "ToolConfig",
    "tool_config",
    "get_tool_config",
    "ensure_tools_registered",
    "is_tools_registered",
]
