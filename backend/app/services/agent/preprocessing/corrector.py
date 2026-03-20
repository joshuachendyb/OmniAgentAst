# -*- coding: utf-8 -*-
"""
语句校对模块

使用 pycorrector 进行中文文本纠错
Author: 小沈 - 2026-03-20
"""

from pycorrector import Corrector


class TextCorrector:
    """中文文本校对修正"""

    def __init__(self) -> None:
        self.corrector = Corrector()

    def correct(self, text: str) -> tuple[str, list]:
        """
        校对修正

        Args:
            text: 用户原始输入文本

        Returns:
            tuple: (修正后文本, 修正记录列表)
        """
        corrected, errors = self.corrector.correct(text)
        return corrected, errors
