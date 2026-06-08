# -*- coding: utf-8 -*-
"""
Message工具函数 — 纯函数,无状态

从 message_builder.py 拆出,遵循 SRP:
- MessageBuilder:状态管理(conversation_history 写/裁剪)
- message_utils:无状态工具函数(消息构建/注入/Schema生成)

Author: 小沈 - 2026-05-28
"""

from typing import Any, Dict, List, Optional

from app.services.agent.tool_result_formatter import format_llm_observation
from app.utils.common import format_param_value


def build_llm_messages(message: str, history: Optional[List[Dict]] = None) -> List[Dict]:
    """LLM层消息列表拼接 — DRY原则:统一入口

    【重构 2026-05-27 小健】替代llm_core._build_messages(),
    消除消息构建逻辑分散两处(DRY)。
    LLM层只应接收已构建好的messages,不应自行组装(SLAP)。
    """
    if not message and history:
        return list(history)
    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})
    return messages


def build_observation_text(execution_result: dict, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    """根据工具执行结果构建observation文本"""
    return format_llm_observation(execution_result, tool_name, tool_params)


def inject_tools_info(
    history_dicts: List[Dict[str, Any]],
    tools_content: str
) -> List[Dict[str, Any]]:
    """注入工具信息到 history_dicts

    替代 react_agent_mixin.py L339-363
    在第一个非system消息前插入,LLM最先看到工具信息。
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

