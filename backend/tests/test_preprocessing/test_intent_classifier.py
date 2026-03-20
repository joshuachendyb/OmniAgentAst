# -*- coding: utf-8 -*-
"""
预处理模块 - 意图分类器测试
Author: 小沈 - 2026-03-20
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.agent.preprocessing.intent_classifier import IntentClassifier


class TestIntentClassifier:
    """意图分类器测试"""

    @patch("app.services.agent.preprocessing.intent_classifier.GLiClassPipeline")
    def test_classify_with_labels(self, mock_gliclass_class):
        """测试带标签的分类"""
        mock_classifier_instance = MagicMock()
        mock_gliclass_class.return_value = mock_classifier_instance

        mock_classifier_instance.return_value = {
            "labels": ["文件操作", "搜索"],
            "scores": [0.9, 0.1],
        }

        classifier = IntentClassifier()
        result = classifier.classify("帮我打开文件", ["文件操作", "搜索"])

        assert result["intent"] == "文件操作"
        assert result["confidence"] == 0.9
        assert "文件操作" in result["all_intents"]
        assert "搜索" in result["all_intents"]

    def test_classify_empty_labels(self):
        """测试空标签列表"""
        classifier = IntentClassifier()
        result = classifier.classify("测试文本", [])

        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0
        assert result["all_intents"] == {}

    @patch("app.services.agent.preprocessing.intent_classifier.GLiClassPipeline")
    def test_classify_single_label(self, mock_gliclass_class):
        """测试单个标签的分类"""
        mock_classifier_instance = MagicMock()
        mock_gliclass_class.return_value = mock_classifier_instance

        mock_classifier_instance.return_value = {
            "labels": ["天气查询"],
            "scores": [0.95],
        }

        classifier = IntentClassifier()
        result = classifier.classify("今天天气怎么样", ["天气查询"])

        assert result["intent"] == "天气查询"
        assert result["confidence"] == 0.95
        assert len(result["all_intents"]) == 1