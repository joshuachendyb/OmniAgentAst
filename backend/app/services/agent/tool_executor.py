# -*- coding: utf-8 -*-
"""
tool_executor — 工具执行逻辑

从universal_agent拆出 — 小沈 2026-06-17
"""

from typing import Any, Dict, Set

from app.tools.tool_types import ToolCategory


async def execute_tool(agent, tool_name: str, tool_params: Dict[str, Any]) -> Dict[str, Any]:
    """执行工具并处理tool_search自动注入"""
    result = await agent._retry_engine.execute_tool_with_retry(tool_name, tool_params)
    if tool_name == "tool_search":
        auto_inject_from_search(agent, result)
    return result


def auto_inject_from_search(agent, result: Dict[str, Any]) -> None:
    """从tool_search结果自动注入分类给LLM
    注意：注入(inject)是指将工具描述提供给LLM使用，工具函数已在启动时注册(register)
    """
    from app.services.agent.tool_cache_manager import invalidate_tool_cache, patch_search_desc
    inner = result.get("data", {})
    llm_matches = inner.get("llm_data", {}).get("matches", [])
    new_cats: Set[ToolCategory] = set()
    for m in llm_matches:
        try:
            cat = ToolCategory(m["category"])
        except (ValueError, KeyError):
            continue
        if cat not in agent._loaded_categories:
            new_cats.add(cat)
    if not new_cats:
        return
    for cat in new_cats:
        agent._loaded_categories.add(cat)
        agent._tool_loader.load_category(cat)
    invalidate_tool_cache(agent)
    patch_search_desc(agent)