# -*- coding: utf-8 -*-
"""
语句校对模块

使用 pycorrector 进行中文文本纠错
Author: 小沈 - 2026-03-20
"""

from typing import Any


class TextCorrector:
    """中文文本校对修正"""

    def __init__(self) -> None:
        pass  # 延迟初始化

    def correct(self, text: str) -> tuple[str, list[Any]]:
        """
        校对修正

        Args:
            text: 用户原始输入文本

        Returns:
            tuple: (修正后文本, 修正记录列表)
        """
        if text is None or not text.strip():
            return str(text) if text else "", []

        from pycorrector import Corrector
        corrector = Corrector()
        corrected, errors = corrector.correct(text)
        return corrected, errors
