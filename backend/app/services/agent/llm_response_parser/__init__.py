# -*- coding: utf-8 -*-
"""
llm_response_parser - ReAct输出统一解析器包

对外接口:parse_react_response(output) → Dict

【清理 2026-06-07 小欧】YAGNI:删除 80+ 内部 helper 死 import,只暴露 parse_react_response

Author: 小沈
Date: 2026-05-28
Version: 2.0(从 react_output_parser.py 按职责拆分为6个内部模块)
"""
from .parse_react_response import parse_react_response

__all__ = ["parse_react_response"]
