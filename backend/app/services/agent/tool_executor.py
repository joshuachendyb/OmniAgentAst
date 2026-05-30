# -*- coding: utf-8 -*-
"""
工具执行器 — 薄壳委托层

仅保留ToolExecutor类壳(供mixin引用self.executor)，
所有逻辑已下沉到tool_retry_engine.py的execute_tool_with_unified_retry()。

Author: 小沈 - 2026-03-21
Updated: 小健 - 2026-05-30 (薄壳下沉：finish/not-found判断移入tool_retry_engine)
"""

from typing import Any, Callable, Dict, Optional

from app.services.agent.tool_retry_engine import execute_tool_with_unified_retry


class ToolExecutor:
    """工具执行器 — 委托给execute_tool_with_unified_retry统一入口"""

    def __init__(self, tools: Dict[str, Callable] = None):
        if tools is not None:
            self.available_tools = tools
        else:
            from app.services.tools.tool_queries import get_implementations_from_registry
            self.available_tools = get_implementations_from_registry()

    async def execute(
        self,
        action: str,
        action_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """执行工具调用 — 委托给execute_tool_with_unified_retry"""
        return await execute_tool_with_unified_retry(action, action_input, self.available_tools)
