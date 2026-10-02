
# -*- coding: utf-8 -*-
"""
工具格式转换 — 将注册表数据转换为各种展示格式

拆分自 registry.py — 小沈 2026-05-29

# 编辑历史:
# 2026-10-02 小欧 strict 默认值 True→False: 验证 opencodeZen 是否接受 strict=false。
#   起因: opencodeZen 必报 400(Object schemas must have 'additionalProperties: false' in strict mode),
#         该要求由 strict 校验提出; 关掉 strict 校验即不执行, 报错应自动消失。
#   为何先试这个而非补 additionalProperties: 本仓库无任何模型需要 strict(gpt-5/o 系 0 个),
#         且该校验从未生效过(65/65 工具全缺 additionalProperties), 关掉不丢已有保护。
#   影响: 其余 6 provider 本就收原样 schema, 行为不变; 仅 opencodeZen 由全挂变为可用。
#   状态: 临时验证用, 结论落地后按结果决定保留或改走 strict 归一化。
"""

from typing import Dict, Any
from app.tools.tool_types import ToolCategory
from typing import Set, Optional
from app.utils.display_utils import format_param_value


def to_openai_tools(registry, categories: Optional[Set[ToolCategory]] = None,
                    tool_names: Optional[Set[str]] = None, strict: bool = False) -> list:
    """
    生成OpenAI API格式的tools定义 - 小沈 2026-05-09

    Args:
        registry: ToolRegistry实例
        categories: 工具分类集合,None=全部
        tool_names: 额外包含的指定工具名集合(即使其分类不在categories中) — 修复 2026-06-23 小欧
        strict: 是否启用strict模式(强制arguments符合Schema) - 小沈 2026-06-17;
               默认False(opencodeZen 会校验 strict 且本仓 schema 不合规) - 小欧 2026-10-02

    Returns:
        [{"type": "function", "function": {...}}, ...]
    """
    tools = []
    tool_names_set = tool_names or set()
    for name, meta in sorted(registry._tools.items(), key=lambda x: x[0]):
        if not meta.expose_to_llm:
            continue
        if categories is not None and meta.category not in categories:
            if name not in tool_names_set:
                continue
        func_def = {
            "name": meta.name,
            "description": meta.description,
            "parameters": meta.input_schema,
            "strict": strict,
        }
        if meta.examples:
            func_def["examples"] = meta.examples
        tools.append({
            "type": "function",
            "function": func_def
        })

    return tools


def _resolve_union_type(pinfo: dict) -> str:
    """从 anyOf/oneOf 中解析联合类型 — 消除重复 — 小沈 2026-05-29"""
    for key in ("anyOf", "oneOf"):
        if key in pinfo:
            type_set = set()
            for item in pinfo[key]:
                if isinstance(item, dict) and "type" in item and item["type"] != "null":
                    type_set.add(item["type"])
            return "/".join(sorted(type_set)) if type_set else "any"
    return "any"


def generate_param_reminder(
    registry,
    category: Optional[ToolCategory] = None,
    style: str = "code",
) -> str:
    """
    从 input_schema 自动生成 Parameter Reminder 文本 - 小沈 2026-05-09

    参数信息完全来自 Pydantic 模型:
    - 参数名:properties 的 key
    - 参数类型:properties[field].type
    - 必填/可选:是否在 required 数组中
    - 默认值:properties[field].default(跳过 None)

    Args:
        registry: ToolRegistry实例
        category: 工具分类,None=全部
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
                ptype = _resolve_union_type(pinfo)
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

