# -*- coding: utf-8 -*-
"""
预处理流水线模块

整合语句校对和意图检测
Author: 小沈 - 2026-03-20
"""

from typing import Any

from .corrector import TextCorrector
from .intent_classifier import IntentClassifier


class PreprocessingPipeline:
    """用户输入预处理流水线"""

    def __init__(self) -> None:
        self.corrector = TextCorrector()
        self.classifier = IntentClassifier()

    def process(self, user_input: str, intent_labels: list[str]) -> dict[str, Any]:
        """
        处理用户输入

        Args:
            user_input: 用户原始输入
            intent_labels: 候选意图标签列表

        Returns:
            dict: {
                original: 原始输入,
                corrected: 修正后文本,
                errors: 修正记录列表,
                intent: 最佳意图,
                confidence: 置信度,
                all_intents: 所有意图及置信度
            }
        """
        corrected, errors = self.corrector.correct(user_input)

        intent_result = self.classifier.classify(corrected, intent_labels)

        return {
            "original": user_input,
            "corrected": corrected,
            "errors": errors,
            "intent": intent_result["intent"],
            "confidence": intent_result["confidence"],
            "all_intents": intent_result["all_intents"],
        }
