# -*- coding: utf-8 -*-
"""
detect_intent — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第235-246行
"""

from typing import Tuple, List

from app.api.v1.chat.route_with_fallback import route_with_fallback


async def detect_intent(user_input: str) -> Tuple[str, str, float, List[str]]:
    """拷贝自 chat_router.py 第235-246行"""
    intent_info = await route_with_fallback(user_input)
    intent_value = intent_info["intent"]
    source = intent_info.get("source", "unknown")
    conf = intent_info["confidence"]
    candidates = [c.value for c in intent_info.get("candidates", []) if c]
    if intent_value is not None:
        return intent_value.value, source, conf, candidates
    raw = str(intent_info.get("raw_intent", "")).lower()
    intent_type = "system" if raw in {"greeting", "chat", "conversation", "qa", "question"} else "network"
    return intent_type, f"{source}(fallback)", conf, candidates
