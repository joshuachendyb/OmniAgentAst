# -*- coding: utf-8 -*-
"""
parse_quantity — 从 parser.py 拷出

拷贝来源: parser.py 第117-122行
"""

import re


def parse_quantity(command: str) -> str:
    """拷贝自 parser.py 第117-122行"""
    batch_keywords = [r'所有', r'全部', r'批量', r'\*', r'-r', r'-rf', r'/s']
    for keyword in batch_keywords:
        if re.search(keyword, command):
            return 'batch'
    return 'single'
