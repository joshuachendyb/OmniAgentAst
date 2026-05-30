# -*- coding: utf-8 -*-
"""
公共预编译正则模式

集中跨文件重复使用的正则pattern，预编译复用：
- HTML清洗：SCRIPT_TAG / STYLE_TAG / HTML_TAG / MULTI_WHITESPACE
- 时间校验：UTC_OFFSET

仅集中跨文件重复的模式，文件私有的正则就地保留。

Author: 小健 - 2026-05-30
"""

import re


# === HTML清洗相关 ===
SCRIPT_TAG_PATTERN = re.compile(r'<script[^>]*>.*?</script>', re.DOTALL | re.IGNORECASE)
STYLE_TAG_PATTERN = re.compile(r'<style[^>]*>.*?</style>', re.DOTALL | re.IGNORECASE)
HTML_TAG_PATTERN = re.compile(r'<[^>]+>')
MULTI_WHITESPACE_PATTERN = re.compile(r'\s+')

# === 时间相关 ===
UTC_OFFSET_PATTERN = re.compile(r'^[+-]\d{2}:\d{2}$')


__all__ = [
    "SCRIPT_TAG_PATTERN",
    "STYLE_TAG_PATTERN",
    "HTML_TAG_PATTERN",
    "MULTI_WHITESPACE_PATTERN",
    "UTC_OFFSET_PATTERN",
]
