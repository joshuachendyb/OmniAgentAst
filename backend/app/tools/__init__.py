# -*- coding: utf-8 -*-
"""
Tools 模块 - 按功能域组织的工具集

拆分后 __init__.py 极简导出 — 小沈 2026-05-29
其余符号请从对应子模块直接导入:
  ToolCategory/ToolMetadata → app.tools.tool_types
  resolve_category → app.tools.tool_types
  get_* → app.tools.tool_queries
  to_openai_tools/generate_param_reminder → app.tools.tool_description

编辑历史:
  2026-08-13 - 小沈 - P5a: 新增 cleanup_shell_pool_by_task 门面函数,
    消除 services/agent/agent_runner→tools/fundamental/shell_engine 具体实现依赖
  2026-11-06 - 小欧 - 去池化: 删除 cleanup_shell_pool_by_task 门面(每命令独立子进程跑完即销毁, 无任务级常驻 shell 资源需清理)
"""

from app.tools.registry import ToolRegistry, ensure_tools_registered, register_tool, tool_registry

__all__ = [
    "tool_registry",
    "register_tool",
    "ToolRegistry",
    "ensure_tools_registered",
]
