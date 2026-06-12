# -*- coding: utf-8 -*-
"""
Meta 工具实现 - tool_search

【2026-05-17 小沈】新建
【2026-06-12 小沈】删除tool_help/pipeline(YAGNI,FC Schema已覆盖),仅保留tool_search
"""

from typing import Dict, Any, List

from app.services.tools.registry import tool_registry
from app.utils.tool_result_formatter import (
    build_next_actions,
    truncate_data_for_frontend,
)
from app.services.tools._response import build_success, build_error


def tool_search(query: str) -> Dict[str, Any]:
    """
    按关键词搜索匹配的工具列表。

    Args:
        query: 自然语言描述需求

    Returns:
        匹配的工具列表
    """
    query_lower = query.lower()
    query_words = query_lower.split()

    if not query.strip():
        return build_error(
            ERR_DOC_QUERY_EMPTY,
            "搜索关键词不能为空,请提供描述性关键词",
        )

    all_tools = tool_registry._tools
    scored: List[Dict[str, Any]] = []

    for name, metadata in all_tools.items():
        score = 0
        name_lower = name.lower()
        desc_lower = metadata.description.lower()

        for word in query_words:
            if word in name_lower:
                score += 10
            if word in desc_lower:
                score += 5

        if name_lower in query_lower or query_lower in name_lower:
            score += 8

        if score > 0:
            scored.append({
                "name": metadata.name,
                "category": metadata.category.value,
                "description": metadata.description[:200],
                "score": score,
            })

    scored.sort(key=lambda x: x["score"], reverse=True)
    top_results = scored[:10]

    data = truncate_data_for_frontend({
        "query": query,
        "matches": top_results,
        "total_matched": len(scored),
        "total_tools": len(all_tools),
    })

    llm_data = {
        "query": query,
        "matches": [{"name": r["name"], "category": r["category"]} for r in top_results[:10]],
        "total_matched": len(scored),
    }

    return build_success(
        data,
        f"找到 {len(scored)} 个相关工具,返回前 {len(top_results)} 个",
        llm_data=llm_data,
    )


__all__ = ["tool_search"]

from app.constants import ERR_DOC_QUERY_EMPTY
