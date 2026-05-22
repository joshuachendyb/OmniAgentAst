# -*- coding: utf-8 -*-
"""
@deprecated 2026-05-20 小健
此目录属于 parsers/ 策略模式模块（2026-04-19设计），当前未被使用。
请使用 react_output_parser.py 的解析器链（_HANDLERS）替代。
详情见：doc-5月优化/parse_react_response解析器链重构设计-小沈-2026-05-19.md

解析器模块 - 6.2.2策略模式拆分

根据文档6.2.2设计，将parse_react_response拆分为多个独立解析器
创建时间: 2026-04-19
"""

from .base_parser import BaseParser, ParseResult
from .json_parser import JsonParser
from .keyword_parser import KeywordParser
from .tool_name_parser import ToolNameParser
from .implicit_parser import ImplicitParser
from .parser_factory import ParserFactory, parser_factory

__all__ = [
    "BaseParser",
    "ParseResult", 
    "JsonParser",
    "KeywordParser",
    "ToolNameParser",
    "ImplicitParser",
    "ParserFactory",
    "parser_factory",
]