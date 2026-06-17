# -*- coding: utf-8 -*-
"""
tool_cache_manager — 工具缓存管理

从universal_agent拆出 — 小沈 2026-06-17
"""

from app.utils.json_utils import read_json_file
from pathlib import Path
from typing import Dict

from app.services.tools.tool_types import ToolCategory
from app.utils.logger import logger


_CATEGORIES_CONFIG_PATH = Path(__file__).resolve().parent.parent / "tools" / "fundamental" / "tool_categories.json"

_CATEGORY_SUMMARIES: Dict[ToolCategory, str] = {
    ToolCategory.FILE: "文件读写、目录浏览、文件搜索和内容分析",
    ToolCategory.NETWORK: "HTTP请求、文件下载、网络搜索和连通性测试",
    ToolCategory.DESKTOP: "窗口管理、鼠标/键盘控制、屏幕截图和剪贴板交互",
    ToolCategory.DOCUMENT: "PDF/Word/Excel/PPT文档的读写和转换",
    ToolCategory.DATAANALYSIS: "数据统计分析、图表可视化、SQL数据库查询",
    ToolCategory.SYSTEM: "系统查询、进程管理、服务控制和环境配置",
}


def get_openai_tools(agent) -> list:
    """获取已加载分类的OpenAI格式工具定义,含TTL缓存 — 小沈 2026-06-17 改用TTLCache"""
    cached = agent._tool_cache.get()
    if cached is not None:
        return cached

    from app.services.tools.registry import tool_registry
    tools = tool_registry.to_openai_tools(categories=agent._loaded_categories)
    agent._tool_cache.set(tools)
    return tools


def invalidate_tool_cache(agent):
    """P2-14修复: 清除工具缓存,工具注册/注销后调用"""
    agent._tool_cache.invalidate()


def patch_search_desc(agent):
    """动态更新 tool_search 描述: 列出未加载分类的概要+工具名 — 小沈 2026-06-17 改用TTLCache"""
    if not _CATEGORIES_CONFIG_PATH.exists():
        return

    categories_config = agent._categories_config_cache.get()
    if categories_config is None:
        categories_config = read_json_file(_CATEGORIES_CONFIG_PATH)
        if categories_config is None:
            return
        agent._categories_config_cache.set(categories_config)

    unloaded = [cat for cat in ToolCategory
                if cat not in {ToolCategory.FUNDAMENTAL, ToolCategory.SHELL} and cat not in agent._loaded_categories]

    from app.services.tools.registry import tool_registry

    ts_meta = tool_registry.get_tool("tool_search")
    if not ts_meta:
        return
    base_desc = ts_meta.description

    if not unloaded:
        return

    lines = []
    for cat in sorted(unloaded, key=lambda c: c.order):
        cfg = categories_config.get(cat.value, {})
        summary = cfg.get("summary", cat.name_cn)
        tools = cfg.get("tools", {})
        tool_items = list(tools.items())
        name_str = ", ".join(f"{k}:{v}" for k, v in tool_items[:5])
        if len(tool_items) > 5:
            name_str += "..."
        lines.append(f"- {cat.name_cn}({cat.value}): {summary} [{name_str}]")

    ts_meta.description = base_desc + "\n\n当前未加载分类:\n" + "\n".join(lines)