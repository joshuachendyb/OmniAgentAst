# -*- coding: utf-8 -*-
"""
工具执行器 — 统一工具执行接口

融合了原始ToolExecutor.execute()和execute_tool_with_unified_retry()的优点：
- 支持tools为None时从registry获取工具实现
- 支持finish短路
- 支持not-found判断
- 支持工具别名查找
- 调用ToolRetryEngine执行

Author: 小沈 - 2026-03-21
Updated: 小沈 - 2026-05-30 (融合execute_tool_with_unified_retry逻辑)
"""

from typing import Any, Callable, Dict, Optional

from app.services.agent.agent_utils.tool_result_factory import create_tool_result, create_error_tool_result
from app.services.agent.tool_retry_engine import _get_tool_retry_engine
from app.constants import ERR_TOOL_NOT_FOUND


async def execute_tool_with_unified_retry(
    action: str,
    action_input: Dict[str, Any],
    tools: Optional[Dict[str, Callable]] = None,
) -> Dict[str, Any]:
    """
    统一工具执行接口
    
    融合了原始ToolExecutor.execute()和execute_tool_with_unified_retry()的优点：
    - 支持tools为None时从registry获取工具实现
    - 支持finish短路
    - 支持not-found判断
    - 支持工具别名查找
    - 调用ToolRetryEngine执行
    
    Args:
        action: 工具名称
        action_input: 工具参数
        tools: 可选的工具字典，如果为None则从registry获取
    
    Returns:
        执行结果字典
    """
    # 1. 如果tools为None，从registry获取工具实现
    if tools is None:
        from app.services.tools.tool_queries import get_implementations_from_registry
        tools = get_implementations_from_registry()
    
    # 2. finish短路
    if action == "finish":
        return create_tool_result(
            data=action_input.get("result"),
            message=action_input.get("result", "Task completed"),
            retry_count=0
        )
    
    # 3. not-found判断 + 工具别名查找
    if action not in tools:
        from app.services.tools.registry import tool_registry
        impl = tool_registry.get_implementation(action)
        if impl is not None:
            tools[action] = impl
        else:
            return create_error_tool_result(
                code=ERR_TOOL_NOT_FOUND,
                data=None,
                message=f"Unknown tool: {action}. Available tools: {list(tools.keys())}",
                retry_count=0,
                error_message=f"工具 '{action}' 未找到",
                error_type="tool_not_found"
            )
    
    # 4. 调用ToolRetryEngine执行
    engine = _get_tool_retry_engine()
    return await engine.execute_tool_with_retry(action, action_input, tools.get(action))
