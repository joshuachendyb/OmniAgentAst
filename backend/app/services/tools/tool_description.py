# -*- coding: utf-8 -*-
"""
工具格式转换 — 将注册表数据转换为各种展示格式

拆分自 registry.py — 小沈 2026-05-29
"""

from collections import defaultdict
from typing import Dict, List, Optional, Any
from app.services.tools.tool_types import ToolCategory, CATEGORY_ORDER, CATEGORY_NAMES
from app.utils.common import format_param_value


def _group_tools_by_category(
    registry,
    expose_to_llm_only: bool = True,
    exclude_categories: Optional[set] = None,
    category_filter: Optional[ToolCategory] = None,
    priority_category: Optional[ToolCategory] = None,
):
    """按分类分组工具，返回 (category_order, by_category) 元组"""
    by_category: Dict[ToolCategory, List[tuple]] = defaultdict(list)
    for name, metadata in registry._tools.items():
        if expose_to_llm_only and not metadata.expose_to_llm:
            continue
        if category_filter and metadata.category != category_filter:
            continue
        if exclude_categories and metadata.category.value in exclude_categories:
            continue
        by_category[metadata.category].append((name, metadata))

    category_order = list(CATEGORY_ORDER)
    if priority_category and priority_category in category_order:
        category_order.remove(priority_category)
        category_order.insert(0, priority_category)

    return category_order, by_category


def get_all_tools_summary(
    registry,
    priority_category: Optional[ToolCategory] = None,
    expose_to_llm_only: bool = True,
    exclude_categories: Optional[set] = None,
) -> str:
    """获取工具概要描述（分类标题+工具名+一句话描述） - 小健 2026-05-15 重构

    【重构 小健 2026-05-15】在工具名后追加一句话描述（取description首句，约50字），
    LLM可以判断是否需要加载该分类。

    Args:
        registry: ToolRegistry实例
        priority_category: 优先展示的分类
        expose_to_llm_only: 是否只展示暴露给LLM的工具
        exclude_categories: 排除的分类集合

    Returns:
        格式化的工具概要字符串
    """
    lines = []
    lines.append("=== 其他可用工具（概要）===")
    lines.append("")

    category_order, by_category = _group_tools_by_category(
        registry, expose_to_llm_only, exclude_categories,
        category_filter=None, priority_category=priority_category)

    for cat in category_order:
        if exclude_categories and cat.value in exclude_categories:
            continue
        items = by_category.get(cat, [])
        if not items:
            continue
        display_name = CATEGORY_NAMES.get(cat, cat.value)
        lines.append(f"【{display_name}】")
        for name, meta in sorted(items, key=lambda x: x[0]):
            # 取description首句（到第一个句号）作为一句话概要
            desc = meta.description.split("。")[0][:80]
            lines.append(f"  {name}: {desc}")
        lines.append("")

    return "\n".join(lines)


def get_all_tools_detail(
    registry,
    priority_category: Optional[ToolCategory] = None,
    category_filter: Optional[ToolCategory] = None,
    exclude_categories: Optional[set] = None,
    expose_to_llm_only: bool = True,
) -> str:
    """获取工具完整描述（使用场景+示例+返回格式） - 小健 2026-05-14
    
    【修复 小健 2026-05-15】category_filter指定时不再添加"=== 可用工具列表 ==="标题，
    避免_loaded_categories多分类遍历时重复标题。

    与 get_all_tools_summary（概要版）互补，此方法输出每个工具的完整description。

    Args:
        registry: ToolRegistry实例
        priority_category: 优先展示的分类（排在最前）
        category_filter: 只输出指定分类的工具（None=全部）
        exclude_categories: 排除的分类集合（避免与概要重复）
        expose_to_llm_only: 是否只展示暴露给LLM的工具

    Returns:
        格式化的工具完整描述字符串
    """
    lines = []
    # category_filter时用分类名作标题，不放"=== 可用工具列表 ==="避免重复
    if category_filter:
        display = CATEGORY_NAMES.get(category_filter, category_filter.value)
        lines.append(f"=== {display} ===")
    else:
        lines.append("=== 可用工具列表（完整）===")
    lines.append("")

    category_order, by_category = _group_tools_by_category(
        registry, expose_to_llm_only, exclude_categories,
        category_filter=category_filter, priority_category=priority_category)

    for cat in category_order:
        if cat not in by_category:
            continue
        items = by_category[cat]
        display_name = CATEGORY_NAMES.get(cat, cat.value)
        lines.append(f"【{display_name}】")
        for name, meta in sorted(items, key=lambda x: x[0]):
            lines.append(f"  {name}: {meta.description}")
        lines.append("")

    return "\n".join(lines)


def to_openai_tools(registry, category: Optional[ToolCategory] = None) -> list:
    """
    生成OpenAI API格式的tools定义 - 小沈 2026-05-09

    Args:
        registry: ToolRegistry实例
        category: 工具分类，None=全部

    Returns:
        [{"type": "function", "function": {...}}, ...]
    """
    tools = []
    for name, meta in sorted(registry._tools.items(), key=lambda x: x[0]):
        if not meta.expose_to_llm:
            continue
        if category and meta.category != category:
            continue
        tools.append({
            "type": "function",
            "function": {
                "name": meta.name,
                "description": meta.description,
                "parameters": meta.input_schema
            }
        })

    return tools


def generate_param_reminder(
    registry,
    category: Optional[ToolCategory] = None,
    style: str = "code",
) -> str:
    """
    从 input_schema 自动生成 Parameter Reminder 文本 - 小沈 2026-05-09

    参数信息完全来自 Pydantic 模型：
    - 参数名：properties 的 key
    - 参数类型：properties[field].type
    - 必填/可选：是否在 required 数组中
    - 默认值：properties[field].default（跳过 None）

    Args:
        registry: ToolRegistry实例
        category: 工具分类，None=全部
        style: "code"=函数签名风格(推荐), "text"=自然语言风格
    """
    TYPE_MAP = {"integer": "int", "number": "number", "string": "str", "boolean": "bool", "object": "dict", "array": "list"}
    header = "Parameter Reminder (auto-generated from Pydantic):" if style == "text" else "Available Functions (auto-generated):"
    lines = [header, ""]
    for name, meta in sorted(registry._tools.items(), key=lambda x: x[0]):
        if not meta.expose_to_llm:
            continue
        if category and meta.category != category:
            continue
        schema = meta.input_schema
        if not schema or "properties" not in schema:
            continue
        
        required_set = set(schema.get("required", []))
        param_parts = []
        for pname, pinfo in schema.get("properties", {}).items():
            ptype = pinfo.get("type")
            if ptype is None:
                if "anyOf" in pinfo:
                    type_set = set()
                    for item in pinfo["anyOf"]:
                        if isinstance(item, dict) and "type" in item and item["type"] != "null":
                            type_set.add(item["type"])
                    ptype = "/".join(sorted(type_set)) if type_set else "any"
                elif "oneOf" in pinfo:
                    type_set = set()
                    for item in pinfo["oneOf"]:
                        if isinstance(item, dict) and "type" in item and item["type"] != "null":
                            type_set.add(item["type"])
                    ptype = "/".join(sorted(type_set)) if type_set else "any"
                else:
                    ptype = "any"
            req_str = "required" if pname in required_set else "optional"
            default_formatted = format_param_value(pinfo.get("default"))
            default_str = f"default={default_formatted}" if default_formatted else ""

            if style == "code":
                short_type = "/".join(TYPE_MAP.get(t.strip(), t.strip()) for t in ptype.split("/"))
                optional_mark = "" if pname in required_set else "?"
                default_expr = ""
                if default_str:
                    default_expr = "=" + default_str.split("=", 1)[1]
                param_parts.append(f"{pname}{optional_mark}: {short_type}{default_expr}")
            else:
                if default_str:
                    param_parts.append("{}({}, {}, {})".format(pname, req_str, ptype, default_str))
                else:
                    param_parts.append("{}({}, {})".format(pname, req_str, ptype))
        
        if param_parts:
            if style == "code":
                lines.append(f"def {name}({', '.join(param_parts)})")
            else:
                lines.append("- " + name + ": " + ", ".join(param_parts))
    
    return "\n".join(lines)
