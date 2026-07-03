# -*- coding: utf-8 -*-
"""
tool_cache_manager — 工具缓存管理

从universal_agent拆出 — 小沈 2026-06-17
【2026-06-18 小健】删除 tool_categories.json，直接从 registry 获取工具信息（DRY原则）
"""

from app.tools.tool_types import ToolCategory
from app.utils.logger import logger



def get_openai_tools(agent) -> list:
    """获取已注入分类的OpenAI格式工具定义,含TTL缓存 — 小沈 2026-06-17 改用TTLCache
    注意：这里获取的是已注入(inject)给LLM的工具，不是所有已注册(register)的工具

    P0-4修复 2026-06-23 小欧: revert P0-3改为注入整个tool类,通过_loaded_categories承载
    Batch2e: 使用agent._searchtool_desc_override副本,不修改全局ts_meta — 小欧 2026-06-25
    """
    cached = agent._tool_cache.get()
    if cached is not None:
        return cached

    from app.tools.registry import tool_registry
    tools = tool_registry.to_openai_tools(categories=agent._loaded_categories)

    override = getattr(agent, '_searchtool_desc_override', None)
    if override:
        for t in tools:
            if t.get("function", {}).get("name") == "searchtool":
                t["function"]["description"] = override
                break

    agent._tool_cache.set(tools)
    return tools


def invalidate_tool_cache(agent):
    """P2-14修复: 清除工具缓存,工具注册/注销后调用"""
    agent._tool_cache.invalidate()


def _get_original_search_desc() -> str:
    """获取 searchtool 的原始描述（不带已注入的"当前未加载分类"后缀）— 小欧 2026-06-23
    P0-1修复: 严禁重复追加,每次重新拼装
    """
    from app.tools.registry import tool_registry
    ts_meta = tool_registry.get_tool("searchtool")
    if not ts_meta:
        return ""
    desc = ts_meta.description
    # 剥离之前可能注入的"当前未加载分类"部分,只取原始描述
    marker = "\n\n当前未加载分类:"
    if marker in desc:
        desc = desc.split(marker)[0]
    return desc


def patch_search_desc(agent):
    """动态更新 searchtool 描述: 列出未加载分类
    
    改为副本模式，不修改全局 ts_meta — 小欧 2026-06-25 Batch2e
    
    【设计原则】
    - DRY: 直接从 tool_registry 获取工具信息，无重复数据
    - KISS-DIRECT: 逻辑直线，无中间文件，每次从原始描述重新拼装
    - 动态生成: 每次根据 agent._loaded_categories 实时计算
    
    【P0-1修复 2026-06-23 小欧】每次从原始描述重新拼装，杜绝重复追加
    【2026-06-18 小健】删除 tool_categories.json，改为直接从 registry 获取
    【方案A修复 2026-06-23 小健】移除工具名列表，只列出分类名，避免LLM直接调用未注入工具
    【Bug15修复】chendyg 2026-06-26: override变更后统一失效缓存，消除4处重复invalidate调用
    """
    from app.tools.registry import tool_registry
    
    unloaded = [
        cat for cat in ToolCategory
        if cat not in {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL}
        and cat not in agent._loaded_categories
    ]
    
    if not unloaded:
        agent._searchtool_desc_override = None
        invalidate_tool_cache(agent)
        return
    
    ts_meta = tool_registry.get_tool("searchtool")
    if not ts_meta:
        agent._searchtool_desc_override = None
        invalidate_tool_cache(agent)
        return
    
    base_desc = _get_original_search_desc()
    if not base_desc:
        agent._searchtool_desc_override = None
        invalidate_tool_cache(agent)
        return
    
    lines = []
    
    for cat in sorted(unloaded, key=lambda c: c.order):
        lines.append(f"- {cat.name_cn}({cat.value})")
    
    if lines:
        agent._searchtool_desc_override = base_desc + "\n\n当前未加载分类:\n" + "\n".join(lines)
    else:
        agent._searchtool_desc_override = None
    invalidate_tool_cache(agent)