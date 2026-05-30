# -*- coding: utf-8 -*-
"""
预编译正则模式集中定义

将跨文件重复的正则模式集中到一处，预编译复用：
- 消除DRY违反（相同pattern字符串分散在多文件）
- 预编译提升性能（re.compile一次，多次使用）

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
