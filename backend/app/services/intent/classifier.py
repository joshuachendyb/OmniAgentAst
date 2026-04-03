# -*- coding: utf-8 -*-
"""
Intent Classifier - 意图分类器

基于预处理结果确认意图类型
Author: 小沈 - 2026-03-22
"""

from typing import List

from .registry import Intent, IntentRegistry


class IntentClassifier:
    """意图分类器"""

    def __init__(self, registry: IntentRegistry, confidence_threshold: float = 0.7):
        self.registry = registry
        self.confidence_threshold = confidence_threshold

    def classify(self, preprocessed: dict, context: dict) -> List[Intent]:
        """
        基于预处理结果，确认意图类型

        输入：preprocessed（来自预处理流水线）
            - preprocessed["corrected"]: 修正后文本
            - preprocessed["intent"]: GLiClass 初步检测的意图
            - preprocessed["confidence"]: GLiClass 置信度

        返回值：List[Intent]（支持多意图拆分）

        处理逻辑：
        1. 如果 GLiClass 置信度足够高，直接使用
        2. 如果置信度不足，尝试关键词匹配兜底
        3. 失败时 → 返回空列表（触发回退机制）
        """
        matched_intents: List[Intent] = []
        confidence = preprocessed.get("confidence", 0)

        # 1. GLiClass 高置信度，直接使用
        if confidence >= self.confidence_threshold:
            intent_name = preprocessed.get("intent", "")
            intent = self.registry.get(intent_name)
            if intent:
                matched_intents.append(intent)

        # 2. 置信度不足，尝试关键词匹配兜底
        if not matched_intents:
            corrected_text = preprocessed.get("corrected", "")
            matched_intents = self._keyword_match(corrected_text)

        # 3. 如果仍然失败，返回空列表（触发回退）
        return matched_intents

    def _keyword_match(self, text: str) -> List[Intent]:
        """关键词匹配兜底"""
        matched: List[Intent] = []
        for intent in self.registry.list_all():
            if any(kw in text.lower() for kw in intent.keywords):
                matched.append(intent)
        return matched