# -*- coding: utf-8 -*-
"""
IntentClassifier — 从 intent_classifier.py 拷出

拷贝来源: intent_classifier.py 第206-231行
"""

from typing import Any, Dict, List

from app.services.preprocessing.intent_classifier.classify_intent import classify_intent


class IntentClassifier:
    """拷贝自 intent_classifier.py 第206-231行"""

    def __init__(self) -> None:
        pass

    async def classify(self, text: str, labels: List[str]) -> Dict[str, Any]:
        if not text or not labels:
            return {"corrected": text, "intent": "unknown", "confidence": 0.0, "all_intents": {}}
        return await classify_intent(text, labels)
