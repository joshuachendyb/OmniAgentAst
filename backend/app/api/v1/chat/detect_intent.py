# -*- coding: utf-8 -*-
"""
detect_intent — 纯CRSS意图检测,走直线

直接调crss_scorer.detect_intent_v2,无中间层

Author: 小沈 - 2026-06-08
"""

from typing import Tuple, List

from app.services.intents.crss_scorer import detect_intent_v2
from app.utils.logger import logger


async def detect_intent(user_input: str) -> Tuple[str, str, float, List[str]]:
    primary, candidates, confidence = detect_intent_v2(user_input)
    if primary is not None:
        logger.info(f"[detect_intent] CRSS → intent={primary.value}, conf={confidence}")
        return primary.value, "crss", confidence, [c.value for c in candidates if c]
    logger.info(f"[detect_intent] CRSS无匹配, confidence={confidence}")
    return "system", "crss_no_match", confidence, []
