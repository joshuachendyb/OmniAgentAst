# -*- coding: utf-8 -*-
"""
预处理流水线模块

整合语句校对和意图检测
Author: 小沈 - 2026-03-20
"""

from typing import Any

from app.utils.logger import logger

from .corrector import TextCorrector
from .intent_classifier import IntentClassifier


class PreprocessingPipeline:
    """用户输入预处理流水线"""

    def __init__(self) -> None:
        self.corrector = TextCorrector()
        self.classifier = IntentClassifier()

    def process(
        self,
        user_input: str,
        intent_labels: list[str],
        session_id: str = ""
    ) -> dict[str, Any]:
        """
        处理用户输入

        Args:
            user_input: 用户原始输入
            intent_labels: 候选意图标签列表
            session_id: 会话ID，用于日志追踪

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
        session_tag = f"[session={session_id}]" if session_id else "[session=N/A]"

        # 步骤1: 语句校对
        try:
            corrected, errors = self.corrector.correct(user_input)
            logger.info(
                f"[Preprocessing] {session_tag} Corrector - "
                f"input: '{user_input}' -> "
                f"output: '{corrected}', errors: {errors}"
            )
        except Exception as e:
            logger.warning(f"[Preprocessing] {session_tag} Corrector failed: {e}")
            corrected, errors = user_input, []

        # 步骤2: 意图检测
        try:
            intent_result = self.classifier.classify(corrected, intent_labels)
            logger.info(
                f"[Preprocessing] {session_tag} Classifier - "
                f"input: '{corrected}', labels: {intent_labels} -> "
                f"intent: '{intent_result['intent']}', "
                f"confidence: {intent_result['confidence']:.4f}, "
                f"all_intents: {intent_result['all_intents']}"
            )
        except Exception as e:
            logger.warning(f"[Preprocessing] {session_tag} Classifier failed: {e}")
            intent_result = {"intent": "unknown", "confidence": 0.0, "all_intents": {}}

        return {
            "original": user_input,
            "corrected": corrected,
            "errors": errors,
            "intent": intent_result["intent"],
            "confidence": intent_result["confidence"],
            "all_intents": intent_result["all_intents"],
        }
