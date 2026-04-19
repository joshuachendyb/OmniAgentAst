# -*- coding: utf-8 -*-
"""
解析器工厂 - 6.2.2补充

根据文档6.2.2设计，支持策略模式
创建时间: 2026-04-19
"""

from typing import List, Optional

from .base_parser import BaseParser, ParseResult
from .json_parser import JsonParser
from .keyword_parser import KeywordParser
from .tool_name_parser import ToolNameParser
from .implicit_parser import ImplicitParser


class ParserFactory:
    """解析器工厂，支持策略模式"""
    
    def __init__(self, parsers: Optional[List[BaseParser]] = None):
        self.parsers = parsers or self._create_default_parsers()
    
    def _create_default_parsers(self) -> List[BaseParser]:
        """创建默认解析器链（按优先级）"""
        return [
            JsonParser(),       # 优先级1: JSON格式
            KeywordParser(),    # 优先级2: 关键词匹配
            ToolNameParser(),   # 优先级3: 工具名匹配
            ImplicitParser()    # 优先级4: 隐式回答
        ]
    
    def parse(self, output: str) -> ParseResult:
        """使用解析器链解析输出"""
        if not output or not isinstance(output, str):
            return ParseResult(
                success=False,
                type="parse_error",
                error="Empty or non-string response"
            )
        
        # 按优先级尝试解析
        for parser in self.parsers:
            if parser.can_parse(output):
                result = parser.parse(output)
                if result.success:
                    return result
        
        # 所有解析器都失败
        return ParseResult(
            success=False,
            type="parse_error",
            error="无法解析LLM响应"
        )


# 全局工厂实例
parser_factory = ParserFactory()