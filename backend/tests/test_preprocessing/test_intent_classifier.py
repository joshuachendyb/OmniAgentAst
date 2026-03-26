# -*- coding: utf-8 -*-
"""
预处理模块 - 意图分类器测试
Author: 小沈 - 2026-03-20
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.preprocessing.intent_classifier import IntentClassifier


class TestIntentClassifier:
    """意图分类器测试"""

    def test_classify_with_labels_fallback(self):
        """测试带标签的分类 - 使用fallback分类器"""
        classifier = IntentClassifier()
        
        # fallback基于关键词匹配
        result = classifier._simple_fallback_classify("帮我打开文件", ["文件操作", "搜索"])
        
        # "打开文件"不匹配file关键词，回退到chat
        assert result["intent"] in ["文件操作", "搜索", "chat"]
        assert result["confidence"] >= 0.0
        assert "文件操作" in result["all_intents"]
        assert "搜索" in result["all_intents"]

    def test_classify_empty_labels(self):
        """测试空标签列表"""
        classifier = IntentClassifier()
        result = classifier.classify("测试文本", [])

        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0
        assert result["all_intents"] == {}

    def test_classify_single_label_fallback(self):
        """测试单个标签的分类 - 使用fallback分类器"""
        classifier = IntentClassifier()
        
        result = classifier._simple_fallback_classify("今天天气怎么样", ["天气查询"])
        
        assert result["intent"] in ["天气查询", "chat"]
        assert result["confidence"] >= 0.0
        assert len(result["all_intents"]) == 1

    def test_classify_none_text(self):
        """测试 None 文本输入"""
        classifier = IntentClassifier()
        result = classifier.classify(None, ["file", "network"])
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0.0

    def test_fallback_file_intent(self):
        """测试fallback识别文件操作意图"""
        classifier = IntentClassifier()
        
        # 测试文件相关关键词
        test_cases = [
            ("打开D盘的文件", "file", 0.9),
            ("读取这个文件", "file", 0.9),
            ("保存到桌面", "file", 0.9),
            ("删除这个文件", "file", 0.9),
        ]
        
        for text, expected_label, expected_score in test_cases:
            result = classifier._simple_fallback_classify(text, ["chat", "file", "network", "desktop"])
            assert result["intent"] == expected_label
            assert result["confidence"] == expected_score