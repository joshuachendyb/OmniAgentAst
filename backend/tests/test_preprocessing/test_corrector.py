# -*- coding: utf-8 -*-
"""
预处理模块 - 文本校对器测试
Author: 小沈 - 2026-03-20
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.preprocessing.corrector import TextCorrector


class TestTextCorrector:
    """文本校对器测试"""

    @patch("pycorrector.Corrector")
    def test_correct_with_errors(self, mock_corrector_class):
        """测试有错误的文本修正"""
        mock_corrector_instance = MagicMock()
        mock_corrector_class.return_value = mock_corrector_instance

        mock_corrector_instance.correct.return_value = (
            "你好世界",
            [{"word": "世jie", "position": 2, "correct": "界"}],
        )

        corrector = TextCorrector()
        result, errors = corrector.correct("你好世jie")

        assert result == "你好世界"
        assert len(errors) == 1
        assert errors[0]["correct"] == "界"

    @patch("pycorrector.Corrector")
    def test_correct_empty_string(self, mock_corrector_class):
        """测试空字符串输入"""
        corrector = TextCorrector()
        result, errors = corrector.correct("")

        assert result == ""
        assert errors == []

    @patch("pycorrector.Corrector")
    def test_correct_whitespace_only(self, mock_corrector_class):
        """测试仅包含空格的输入"""
        corrector = TextCorrector()
        result, errors = corrector.correct("   ")

        assert result == "   "
        assert errors == []

    @patch("pycorrector.Corrector")
    def test_correct_normal_text(self, mock_corrector_class):
        """测试正常文本（无错误）"""
        mock_corrector_instance = MagicMock()
        mock_corrector_class.return_value = mock_corrector_instance

        mock_corrector_instance.correct.return_value = (
            "今天天气很好",
            [],
        )

        corrector = TextCorrector()
        result, errors = corrector.correct("今天天气很好")

        assert result == "今天天气很好"
        assert errors == []

    @patch("pycorrector.Corrector")
    def test_correct_none_input(self, mock_corrector_class):
        """测试 None 输入处理"""
        corrector = TextCorrector()
        result, errors = corrector.correct(None)
        assert result == ""
        assert errors == []