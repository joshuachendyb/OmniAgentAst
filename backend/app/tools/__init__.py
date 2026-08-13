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
"""

from app.tools.registry import tool_registry, register_tool, ToolRegistry, ensure_tools_registered


def cleanup_shell_pool_by_task(task_id: str):
    """清理指定任务的 shell 资源 — 供编排层调用 — 小沈 2026-08-13 P5a"""
    from app.tools.fundamental.shell_engine import shell_pool
    shell_pool.cleanup_by_task(task_id)


__all__ = [
    "tool_registry",
    "register_tool",
    "ToolRegistry",
    "ensure_tools_registered",
    "cleanup_shell_pool_by_task",
]
