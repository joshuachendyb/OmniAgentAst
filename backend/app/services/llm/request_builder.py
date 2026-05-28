# -*- coding: utf-8 -*-
"""
LLM请求构建器 — SRP拆分自llm_core.py — 小健 2026-05-27

职责：请求体构建、消息列表构建。
从BaseAIService提取，遵循SRP原则。

Author: 小健 - 2026-05-27
"""

from typing import List, Dict, Optional

from app.services.agent.message_utils import build_llm_messages


def build_request_body(
    messages: List[Dict],
    model: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
    seed: Optional[int] = None,
    stream: bool = False
) -> Dict:
    """构建LLM请求体 — 小健 2026-05-27

    Args:
        messages: 消息列表
        model: 模型名称
        max_tokens: 最大token数
        temperature: 温度
        seed: 随机种子
        stream: 是否流式

    Returns:
        请求体字典
    """
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if seed is not None:
        body["seed"] = seed
    if stream:
        body["stream"] = True
    return body


def build_messages(message: str, history: Optional[List[Dict]] = None) -> List[Dict]:
    """构建消息列表 — 委托给MessageBuilder统一入口 — 小健 2026-05-27

    DRY原则：LLM层不自行组装消息列表，委托给MessageBuilder。

    Args:
        message: 用户消息
        history: 历史消息列表

    Returns:
        消息列表
    """
    return build_llm_messages(message, history)


__all__ = [
    "build_request_body",
    "build_messages",
]
