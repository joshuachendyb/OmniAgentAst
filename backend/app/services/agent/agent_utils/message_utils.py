# -*- coding: utf-8 -*-
"""
Message工具函数 — 纯函数，无状态

从 message_builder.py 拆出，遵循 SRP：
- MessageBuilder：状态管理（conversation_history 写/裁剪）
- message_utils：无状态工具函数（消息构建/注入/Schema生成）

Author: 小沈 - 2026-05-28
"""

from typing import Any, Dict, List, Optional

from app.services.agent.tool_result_formatter import _format_llm_observation


def build_llm_messages(message: str, history: Optional[List[Dict]] = None) -> List[Dict]:
    """LLM层消息列表拼接 — DRY原则：统一入口

    【重构 2026-05-27 小健】替代llm_core._build_messages()，
    消除消息构建逻辑分散两处（DRY）。
    LLM层只应接收已构建好的messages，不应自行组装（SLAP）。
    """
    if not message and history:
        return list(history)
    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})
    return messages


def build_observation_text(execution_result: dict, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    """根据工具执行结果构建observation文本 — 统一委托_format_llm_observation

    小健 2026-05-22：原手写逻辑已合入 _format_llm_observation（含next_actions），
    此方法保留作为兼容入口。
    更新 2026-05-24 小健：增加 tool_name/tool_params 参数供 failure hint 使用
    """
    return _format_llm_observation(execution_result, tool_name, tool_params)


def inject_tools_info(
    history_dicts: List[Dict[str, Any]],
    tools_content: str
) -> List[Dict[str, Any]]:
    """注入工具信息到 history_dicts

    替代 react_agent_mixin.py L339-363
    在第一个非system消息前插入，LLM最先看到工具信息。
    """
    if not tools_content:
        return history_dicts
    tools_msg = {"role": "system", "content": tools_content}
    insert_pos = 0
    for i, msg in enumerate(history_dicts):
        if msg.get("role") != "system":
            insert_pos = i
            break
    else:
        insert_pos = len(history_dicts)
    return list(history_dicts[:insert_pos]) + [tools_msg] + list(history_dicts[insert_pos:])


def inject_schema_text(
    history_dicts: List[Dict[str, Any]],
    schema_text: str
) -> List[Dict[str, Any]]:
    """注入Schema文本（仅TextStrategy使用）— 替代 react_agent_mixin.py L381-390"""
    if not schema_text:
        return history_dicts
    return list(history_dicts) + [{"role": "system", "content": schema_text}]


def build_schema_text(openai_tools: List[Dict]) -> str:
    """将openai_tools转换为文本格式（方案C）— 迁入自 react_agent_mixin.py L252-292
    小沈 2026-05-21
    """
    if not openai_tools:
        return ""
    lines = ["【Tools Schema参考（仅作参考，实际调用仍以JSON格式返回）】:"]
    for tool in openai_tools:
        func = tool.get("function", {})
        name = func.get("name", "")
        params = func.get("parameters", {})
        properties = params.get("properties", {})
        required = params.get("required", [])
        if not properties:
            lines.append(f"{name}: 无参数")
            continue
        params_list = []
        for pname, pinfo in properties.items():
            ptype = pinfo.get("type", "any")
            pdefault = pinfo.get("default")
            is_required = pname in required
            if pdefault is not None:
                params_list.append(f"{pname}({ptype}, default={pdefault})")
            elif is_required:
                params_list.append(f"{pname}({ptype}, required)")
            else:
                params_list.append(f"{pname}({ptype}, optional)")
        lines.append(f"{name}: {', '.join(params_list)}")
    return "\n".join(lines)
