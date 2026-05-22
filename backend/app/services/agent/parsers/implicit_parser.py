# -*- coding: utf-8 -*-
"""
@deprecated 2026-05-20 小健
此文件属于 parsers/ 策略模式模块（2026-04-19设计），当前未被使用。
请使用 react_output_parser.py 的解析器链（_HANDLERS）替代。
详情见：doc-5月优化/parse_react_response解析器链重构设计-小沈-2026-05-19.md

隐式回答解析器 - 6.2.2补充

根据文档6.2.2设计
创建时间: 2026-04-19
"""

import re
from typing import Dict, Any

from .base_parser import BaseParser, ParseResult


class ImplicitParser(BaseParser):
    """隐式回答解析器"""
    
    # 隐式回答关键词
    IMPLICIT_KEYWORDS = [
        "好的", "OK", "明白了", "了解", "我知道了",
        "yes", "okay", "sure", "got it", "understood",
    ]
    
    def can_parse(self, output: str) -> bool:
        """检查是否包含隐式回答关键词"""
        output = output.strip().lower()
        return any(kw in output for kw in self.IMPLICIT_KEYWORDS)
    
    def parse(self, output: str) -> ParseResult:
        """解析隐式回答"""
        try:
            output = output.strip()
            return ParseResult(
                success=True,
                type="implicit",
                thought=output,
                response=output
            )
        except Exception as e:
            return ParseResult(
                success=False,
                type="parse_error",
                error=f"隐式解析失败: {str(e)}"
            )