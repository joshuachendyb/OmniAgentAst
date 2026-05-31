# -*- coding: utf-8 -*-
"""
route_with_fallback — 从 chat_router.py 拷出

拷贝来源: chat_router.py 第65-144行
"""

from typing import Dict, List

from app.services.tools.tool_types import ToolCategory
from app.services.intents.crss_scorer import detect_intent_v2
from app.constants import CRSS_CONFIDENCE_THRESHOLD
from app.utils.logger import logger
from app.services.preprocessing.intent_classifier import classify_intent
from app.services.intents.intent_mapper import resolve_category


async def route_with_fallback(user_input: str) -> Dict:
    """拷贝自 chat_router.py 第65-144行"""
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

    if primary is not None and confidence >= CRSS_CONFIDENCE_THRESHOLD:
        logger.info(
            f"[RouteFallback] CRSS阶段1 → intent={primary.value}, "
            f"conf={confidence}, candidates={[c.value for c in candidates]}"
        )
        return result

    logger.info(
        f"[RouteFallback] CRSS无匹配或模糊，进入LLM兜底阶段2. "
        f"primary={primary}, candidates={candidates}"
    )

    try:
        intent_labels = [c.value for c in ToolCategory]
        llm_result = await classify_intent(user_input, intent_labels)
        intent_str = llm_result.get("intent", "")
        llm_confidence = float(llm_result.get("confidence", 0.5))
        intent_enum = resolve_category(intent_str)

        result.update({
            "intent": intent_enum,
            "candidates": [intent_enum] if intent_enum else [],
            "confidence": llm_confidence,
            "corrected": llm_result.get("corrected", user_input),
            "all_intents": llm_result.get("all_intents", {}),
            "source": "llm",
            "raw_intent": intent_str,
        })

        logger.info(
            f"[RouteFallback] LLM阶段2 → intent={intent_str}({intent_enum}), "
            f"conf={llm_confidence}, corrected='{result['corrected']}'"
        )
    except Exception as e:
        logger.warning(f"[RouteFallback] LLM兜底失败: {e}，使用CRSS结果")

    return result
