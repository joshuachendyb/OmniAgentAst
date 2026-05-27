# -*- coding: utf-8 -*-
"""
Reasoning内容处理适配器

处理模型reasoning_content字段的探测、消息修复和内容提取。
从 llm_core.py 拆分出来，遵循SRP原则。
Author: 小沈 - 2026-05-27
"""

import httpx
from typing import Dict, List, Optional

from app.utils.logger import logger
from app.constants import DEFAULT_PROBE_TIMEOUT


async def detect_reasoning_support(
    api_base: str, api_key: str, model: str, cached: Optional[bool] = None
) -> bool:
    """
    通过API探测模型是否支持reasoning_content

    发一个简单请求，检查响应message中是否包含reasoning_content字段。

    Args:
        api_base: API基础URL
        api_key: API密钥
        model: 模型名称
        cached: 已缓存的探测结果（非None时直接返回）

    Returns:
        True如果模型支持reasoning_content
    """
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_PROBE_TIMEOUT) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "1+1=?"}], "stream": False}
            )
            if response.status_code == 200:
                message = response.json().get("choices", [{}])[0].get("message", {})
                return "reasoning_content" in message
            return False
    except Exception as e:
        logger.warning(f"[reasoning探测] 探测失败，默认不支持: {e}")
        return False


def fix_thinking_messages(messages: List[Dict], is_thinking: bool) -> List[Dict]:
    """
    修复thinking模型消息兼容性

    thinking模型(如deepseek-v3/r1)要求assistant消息必须包含
    reasoning_content或tool_calls字段，否则API返回400。

    修复策略：对缺少reasoning_content且无tool_calls的assistant消息，
    将content移入reasoning_content字段，content置空字符串。

    Args:
        messages: 消息列表
        is_thinking: 是否为thinking模型

    Returns:
        修复后的消息列表
    """
    if not is_thinking:
        return messages
    for msg in messages:
        if msg.get("role") == "assistant" and not msg.get("tool_calls"):
            if "reasoning_content" not in msg:
                content = msg.get("content") or ""
                msg["reasoning_content"] = content
                msg["content"] = ""
    return messages


def extract_reasoning_from_chunk(delta: Dict) -> Optional[str]:
    """
    从流式chunk的delta中提取reasoning_content

    Args:
        delta: SSE chunk的delta对象

    Returns:
        reasoning内容字符串，如果不存在返回None
    """
    return getattr(delta, 'reasoning_content', None) or delta.get('reasoning_content')


def extract_reasoning_from_message(message: Dict) -> str:
    """
    从非流式响应message中提取reasoning内容

    Args:
        message: API响应的message字典

    Returns:
        reasoning内容字符串
    """
    return message.get("reasoning_content", "") or message.get("reasoning", "")


__all__ = [
    "detect_reasoning_support",
    "fix_thinking_messages",
    "extract_reasoning_from_chunk",
    "extract_reasoning_from_message",
]
