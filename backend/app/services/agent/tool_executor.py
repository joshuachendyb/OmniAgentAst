# -*- coding: utf-8 -*-
"""
tool_executor — 工具执行逻辑

从universal_agent拆出 — 小沈 2026-06-17
"""

from typing import Any, Dict, Set


async def execute_tool(agent, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
    """执行工具并处理tool_search自动注入"""
    result = await agent._retry_engine.execute_tool_with_retry(tool_name, tool_params)
    if tool_name == "tool_search":
        auto_inject_from_search(agent, result)
    return result


def auto_inject_from_search(agent, result: Dict[str, Any]) -> None:
    """从tool_search结果自动注入工具给LLM — 小欧 2026-06-21 适配新3字段result

    P0-3修复 2026-06-23 小欧: 只注入匹配的具体工具名(不再加载整个分类),避免每轮66个工具
    
    注意：注入(inject)是指将工具描述提供给LLM使用，工具函数已在启动时注册(register)
    """
    from app.services.agent.tool_cache_manager import invalidate_tool_cache, patch_search_desc
    data = result.get("data", {})
    llm_matches = data.get("matches", [])
    if not llm_matches:
        return

    new_injected: Set[str] = set()
    for m in llm_matches:
        name = m.get("name", "")
        if name:
            new_injected.add(name)

    if not hasattr(agent, '_injected_tool_names'):
        agent._injected_tool_names = set()
    before = len(agent._injected_tool_names)
    agent._injected_tool_names.update(new_injected)
    after = len(agent._injected_tool_names)
    if after > before:
        invalidate_tool_cache(agent)
        patch_search_desc(agent)