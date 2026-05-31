# -*- coding: utf-8 -*-
"""
parse_direction — 从 parser.py 拷出

拷贝来源: parser.py 第108-115行
"""

from typing import Optional


def parse_direction(operation: Optional[str]) -> Optional[str]:
    """拷贝自 parser.py 第108-115行"""
    if operation in ['copy', 'move', 'create', 'update']:
        return 'write'
    elif operation == 'delete':
        return 'delete'
    elif operation == 'read':
        return 'read'
    return None
