# -*- coding: utf-8 -*-
"""
common_patterns — 常用正则模式

小健 - 2026-06-08 从 network_helper.py 迁入，统一复用
替代已删除的 app.utils.common_patterns 模块
"""
import re

# HTML清洗正则
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
SCRIPT_TAG_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL)
STYLE_TAG_PATTERN = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL)
MULTI_WHITESPACE_PATTERN = re.compile(r'\s+')
UTC_OFFSET_PATTERN = re.compile(r'([+-]\d{2}):?(\d{2})')

__all__ = [
    "HTML_TAG_PATTERN",
    "SCRIPT_TAG_PATTERN",
    "STYLE_TAG_PATTERN",
    "MULTI_WHITESPACE_PATTERN",
    "UTC_OFFSET_PATTERN",
]
