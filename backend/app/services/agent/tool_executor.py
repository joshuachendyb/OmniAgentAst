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
    """从tool_search结果自动注入整个工具类给LLM — 小欧 2026-06-23

    P0-4修复: 匹配到一个工具，就把该工具所在的整个类(如NETWORK)全部注入LLM。
    因为LLM知道类名后就能理解该类的所有工具，无需逐个注入。
    
    注意：注入(inject)是指将工具描述提供给LLM使用，工具函数已在启动时注册(register)
    """
    from app.services.agent.tool_cache_manager import invalidate_tool_cache, patch_search_desc
    data = result.get("data", {})
    llm_matches = data.get("matches", [])
    if not llm_matches:
        return

    # 收集匹配工具所属的tool类别
    new_categories: Set[ToolCategory] = set()
    for m in llm_matches:
        cat_str = m.get("category", "")
        if cat_str:
            try:
                new_categories.add(ToolCategory(cat_str))
            except ValueError:
                continue

    if not new_categories:
        return

    before = len(agent._loaded_categories)
    agent._loaded_categories.update(new_categories)
    after = len(agent._loaded_categories)
    if after <= before:
        return

    # 同时加载工具实现到_tools_dict，确保ToolRetryEngine可执行
    for cat in new_categories:
        if hasattr(agent, '_tool_loader'):
            agent._tool_loader.load_category(cat)

    invalidate_tool_cache(agent)
    patch_search_desc(agent)