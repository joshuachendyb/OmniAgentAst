# -*- coding: utf-8 -*-
"""
llm_response_parser - LLM响应统一解析器包

对外接口:parse_llm_response(output) → Dict

【清理 2026-06-07 小欧】YAGNI:删除 80+ 内部 helper 死 import,只暴露 parse_llm_response

Author: 小沈
Date: 2026-05-28
Version: 2.1(从 parse_react_response 改名为 parse_llm_response)
"""
from .parse_llm_response import parse_llm_response

__all__ = ["parse_llm_response"]
