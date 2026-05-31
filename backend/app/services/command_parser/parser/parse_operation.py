# -*- coding: utf-8 -*-
"""
parse_operation — 从 parser.py 拷出

拷贝来源: parser.py 第70-76行
"""

import re
from typing import Optional


def parse_operation(command: str, operation_patterns: dict) -> Optional[str]:
    """拷贝自 parser.py 第70-76行"""
    command_lower = command.lower()
    for op, patterns in operation_patterns.items():
        for pattern in patterns:
            if re.search(pattern, command_lower):
                return op
    return None
