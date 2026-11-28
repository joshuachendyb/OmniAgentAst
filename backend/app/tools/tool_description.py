
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
# 2026-10-19 小欧 缺库工具不暴露给 LLM: to_openai_tools 与 generate_param_reminder 两处改读
#   ToolMetadata.visible_to_llm(= expose_to_llm and 依赖齐备)。原先缺库工具照常进 LLM 工具列表,
#   LLM 试调一次才知不可用、白耗一轮; 两处必须同判据, 否则清单列了签名而实际调不通。
# 2026-11-27 小欧 增 exclude 形参(工具名黑名单, 子Agent只读拒绝清单的可见性同源过滤);
#   description 取值改走 ToolMetadata.resolved_description(), 支持 callable 动态描述(delegateagent 零改代码)
# 2026-11-28 小欧 exclude/tool_names fail-fast + 别名归一: 传 str 时 `name in str` 是子串判定而非集合判定,
#   exclude="write" 会把 write 及任何子串命中项一起藏掉, tool_names="read" 会放进任何子串命中项 ——
#   静默改变可见工具集, 与"安全类承诺不走静默降级"冲突; 名单统一过 normalize_tool_name,
#   拒绝名单写别名(write_file)与写注册名(write)等价
# 2026-11-28 - OmniAgent - 名单归一与 str fail-fast 改调 tools_alias_mapper.normalize_name_set():
#   与 tool_loader.init_tools 共用同一实现, 消除重复表达式(DRY), 行为等价
"""

from typing import Optional, Set

from app.tools.tool_types import ToolCategory
from app.tools.tools_alias_mapper import normalize_name_set
from app.utils.display_utils import format_param_value


def to_openai_tools(registry, categories: Optional[Set[ToolCategory]] = None,
                    tool_names: Optional[Set[str]] = None, strict: bool = False,
                    exclude: Optional[Set[str]] = None) -> list:
    """
    生成OpenAI API格式的tools定义 - 小沈 2026-05-09

    Args:
        registry: ToolRegistry实例
        categories: 工具分类集合,None=全部
        tool_names: 额外包含的指定工具名集合(即使其分类不在categories中) — 修复 2026-06-23 小欧
        strict: 是否启用strict模式(强制arguments符合Schema) - 小沈 2026-06-17;
               默认False(opencodeZen 会校验 strict 且本仓 schema 不合规) - 小欧 2026-10-02
        exclude: 工具名黑名单(None=不排除) — 子Agent只读拒绝清单的可见性同源过滤 - 小欧 2026-11-27

    Returns:
        [{"type": "function", "function": {...}}, ...]
    """
    tools = []
    # 2026-11-28 小欧 - fail-fast: 传 str 时 `name in str` 是子串判定, 会静默改变可见工具集;
    #   别名归一: 拒绝/白名单写别名(write_file)与写注册名(write)等价 — 收口 normalize_name_set(2026-11-28 OmniAgent)
    tool_names_set = normalize_name_set(tool_names, "tool_names")
    _exclude = normalize_name_set(exclude, "exclude")
    for name, meta in sorted(registry._tools.items(), key=lambda x: x[0]):
        # 2026-11-27 小欧 - 黑名单先过滤: 被拒工具不该出现在 LLM 眼里(看得见却调不通=白耗轮次)
        if name in _exclude:
            continue
        # 2026-10-19 小欧 - 可见性单一判据(visible_to_llm = expose_to_llm and 依赖齐备):
        #   缺库工具不进 LLM 工具列表, 免得 LLM 试调一次才知不可用、白耗一轮。
        if not meta.visible_to_llm:
            continue
        if categories is not None and meta.category not in categories:
            if name not in tool_names_set:
                continue
        func_def = {
            "name": meta.name,
            # 2026-11-27 小欧 - 走 resolved_description(): description 允许 callable(注册表快照动态生成)
            "description": meta.resolved_description(),
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
        # 2026-10-19 小欧 - 与 to_openai_tools 同读 visible_to_llm: 缺库工具不进函数签名清单,
        #   免得提示文本列了签名而实际调不通, 两处口径不一致会让 LLM 按清单硬调。
        if not meta.visible_to_llm:
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

