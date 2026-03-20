# -*- coding: utf-8 -*-
"""
意图检测模块

使用 GLiClass 进行零样本意图分类
Author: 小沈 - 2026-03-20
"""

from typing import Any

from gliclass import GLiClassPipeline


class IntentClassifier:
    """意图分类器"""

    def __init__(self) -> None:
        self.classifier = GLiClassPipeline(
            model="knowledgator/gliclass-instruct-base-v1.0"
        )

    def classify(self, text: str, labels: list[str]) -> dict[str, Any]:
        """
        意图分类

        Args:
            text: 修正后的文本
            labels: 候选意图标签列表

        Returns:
            dict: {
                intent: 最佳意图,
                confidence: 置信度,
                all_intents: 所有意图及置信度字典
            }
        """
        if not text or not labels:
            return {"intent": "unknown", "confidence": 0.0, "all_intents": {}}

        result = self.classifier(text, labels=labels)
        return {
            "intent": result["labels"][0],
            "confidence": result["scores"][0],
            "all_intents": dict(zip(result["labels"], result["scores"])),
        }
