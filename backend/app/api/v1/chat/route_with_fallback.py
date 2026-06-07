# -*- coding: utf-8 -*-
"""
route_intent — 纯CRSS意图路由,无LLM兜底

Author: 小沈 - 2026-06-07
"""

from typing import Dict

from app.services.intents.crss_scorer import detect_intent_v2
from app.utils.logger import logger


async def route_with_fallback(user_input: str) -> Dict:
    """纯CRSS意图路由"""
    primary, candidates, confidence = detect_intent_v2(user_input)

    result = {
        "intent": primary,
        "candidates": candidates,
        "confidence": confidence,
        "original": user_input,
        "corrected": user_input,
        "all_intents": {},
        "source": "crss",
    }

    if primary is not None:
        logger.info(
            f"[RouteIntent] CRSS → intent={primary.value}, "
            f"conf={confidence}, candidates={[c.value for c in candidates]}"
        )
    else:
        logger.info(f"[RouteIntent] CRSS无匹配, primary=None, confidence={confidence}")

    return result
