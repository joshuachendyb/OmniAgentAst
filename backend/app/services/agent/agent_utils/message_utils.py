# -*- coding: utf-8 -*-
"""
Message工具函数 — 纯函数,无状态

从 message_builder.py 拆出,遵循 SRP:
- MessageBuilder:状态管理(conversation_history 写/裁剪)
- message_utils:无状态工具函数(消息构建/注入/Schema生成)

Author: 小沈 - 2026-05-28
"""

from typing import Any, Dict, List, Optional



def build_observation_text(execution_result, tool_name: str = "", tool_params: Optional[dict] = None) -> str:
    """根据工具执行结果构建observation文本 — 小欧 2026-06-21 适配新3字段result

    从result中拆包data/llm_data，直接调format_llm_observation(data, llm_data)

    Args:
        execution_result: 工具执行结果（新格式dict或Exception）
        tool_name: 工具名称（仅异常时用）
        tool_params: 工具参数（仅异常时用）

    Returns:
        observation文本
    """
    from app.services.agent.observation_formatter import format_llm_observation

    if isinstance(execution_result, dict):
        data = execution_result.get("data")
        llm_data = execution_result.get("llm_data")
        if llm_data is not None:
            return format_llm_observation(data, llm_data)
        result_str = str(execution_result)
        return f"Observation: {result_str[:500]}" if len(result_str) > 500 else f"Observation: {result_str}"
    result_str = str(execution_result)
    return f"Observation: {result_str[:500]}" if len(result_str) > 500 else f"Observation: {result_str}"




