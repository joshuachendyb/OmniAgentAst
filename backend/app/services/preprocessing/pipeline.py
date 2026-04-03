# -*- coding: utf-8 -*-
"""
预处理流水线模块

整合语句校对和意图检测（文本矫正已合并到 LLM 调用中）
Author: 小沈 - 2026-03-20
"""

from typing import Any, List

from app.utils.logger import logger

from .intent_classifier import IntentClassifier


class PreprocessingPipeline:
    """用户输入预处理流水线（异步版本）"""

    def __init__(self) -> None:
        self.classifier = IntentClassifier()

    async def process(
        self,
        user_input: str,
        intent_labels: List[str],
        session_id: str = ""
    ) -> dict[str, Any]:
        """
        处理用户输入（异步）

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

        # 步骤1: 意图检测（同时进行文本矫正）
        try:
            intent_result = await self.classifier.classify(user_input, intent_labels)
            corrected = intent_result.get("corrected", user_input)
            errors = []
            
            logger.info(
                f"[Preprocessing] {session_tag} Classifier - "
                f"input: '{user_input}', corrected: '{corrected}', labels: {intent_labels} -> "
                f"intent: '{intent_result.get('intent', 'unknown')}', "
                f"confidence: {intent_result.get('confidence', 0):.4f}"
            )
        except Exception as e:
            logger.warning(f"[Preprocessing] {session_tag} Classifier failed: {e}")
            intent_result = {"intent": "unknown", "confidence": 0.0, "all_intents": {}}
            corrected = user_input
            errors = []

        return {
            "original": user_input,
            "corrected": corrected,
            "errors": errors,
            "intent": intent_result.get("intent", "unknown"),
            "confidence": intent_result.get("confidence", 0.0),
            "all_intents": intent_result.get("all_intents", {}),
        }
