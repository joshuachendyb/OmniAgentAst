# -*- coding: utf-8 -*-
"""
detect_intent — 纯CRSS意图检测,走直线

直接调crss_scorer.detect_intent_v2,无中间层

Author: 小沈 - 2026-06-08
"""

from typing import Tuple, List

from app.services.intents.crss_scorer import detect_intent_v2
from app.utils.logger import logger


# ToolCategory.value → intent_type name 映射 — 小沈 2026-06-10
# CRSS返回ToolCategory.value(如"doc_content"),但AGENT_REGISTRY用intent_type名(如"document")
_TOOLCATEGORY_TO_INTENT = {
    "file": "file",
    "fund_runtime": "system",
    "net_process": "network",
    "doc_content": "document",
    "screen": "desktop",
}


def detect_intent(user_input: str) -> Tuple[str, float, List[str]]:
    primary, candidates, confidence = detect_intent_v2(user_input)
    if primary is not None:
        intent = _TOOLCATEGORY_TO_INTENT.get(primary.value, primary.value)
        logger.info(f"[detect_intent] CRSS → intent={intent}, conf={confidence}")
        return intent, confidence, [c.value for c in candidates if c]
    logger.info(f"[detect_intent] CRSS无匹配, confidence={confidence}")
    return "system", confidence, []
