# -*- coding: utf-8 -*-
"""
extract_json_balanced — 从 intent_classifier.py 拷出

拷贝来源: intent_classifier.py 第78-91行
"""

from typing import Optional


def extract_json_balanced(content: str) -> Optional[str]:
    """拷贝自 intent_classifier.py 第78-91行"""
    start = content.find("{")
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(content)):
        if content[i] == "{":
            depth += 1
        elif content[i] == "}":
            depth -= 1
            if depth == 0:
                return content[start:i + 1]
    return None
