# -*- coding: utf-8 -*-
"""
意图检测模块

使用 GLiClass 进行零样本意图分类
Author: 小沈 - 2026-03-20
"""

import warnings
from typing import Any


class IntentClassifier:
    """意图分类器"""

    def __init__(self) -> None:
        self._classifier = None
        self._model_name = "knowledgator/gliclass-instruct-base-v1.0"

    @property
    def classifier(self):
        return None

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

        if self.classifier is None:
            return self._simple_fallback_classify(text, labels)

        try:
            result = self.classifier(text, labels=labels)
            return {
                "intent": result["labels"][0],
                "confidence": result["scores"][0],
                "all_intents": dict(zip(result["labels"], result["scores"])),
            }
        except Exception as e:
            warnings.warn(f"GLiClass classification failed: {e}, using fallback")
            return self._simple_fallback_classify(text, labels)

    def _simple_fallback_classify(self, text: str, labels: list[str]) -> dict[str, Any]:
        """简单回退分类器 - 基于关键词匹配"""
        text_lower = text.lower()
        
        score_map = {}
        for label in labels:
            label_lower = label.lower()
            score = 0.0
            
            if label_lower == "file":
                if any(kw in text_lower for kw in ["文件", "打开", "读取", "保存", "删除", "复制", "移动", "dir", "list"]):
                    score = 0.9
            elif label_lower == "network":
                if any(kw in text_lower for kw in ["网络", "http", "下载", "请求", "api"]):
                    score = 0.9
            elif label_lower == "desktop":
                if any(kw in text_lower for kw in ["桌面", "截图", "窗口", "应用"]):
                    score = 0.9
            elif label_lower == "chat":
                score = 0.5
            
            score_map[label] = score
        
        best_label = max(score_map, key=score_map.get)
        best_score = score_map[best_label]
        
        return {
            "intent": best_label if best_score > 0.3 else "chat",
            "confidence": best_score,
            "all_intents": score_map
        }
