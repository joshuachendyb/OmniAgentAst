# -*- coding: utf-8 -*-
"""
detect_intent — 纯CRSS意图检测

Author: 小沈 - 2026-06-07
"""

from typing import Tuple, List

from app.api.v1.chat.route_with_fallback import route_with_fallback


async def detect_intent(user_input: str) -> Tuple[str, str, float, List[str]]:
    """纯CRSS意图检测,无LLM兜底"""
    intent_info = await route_with_fallback(user_input)
    intent_value = intent_info["intent"]
    source = intent_info.get("source", "unknown")
    conf = intent_info["confidence"]
    candidates = [c.value for c in intent_info.get("candidates", []) if c]
    if intent_value is not None:
        return intent_value.value, source, conf, candidates
    return "system", source, conf, candidates
