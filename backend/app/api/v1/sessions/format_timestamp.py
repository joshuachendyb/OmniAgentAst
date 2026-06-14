# -*- coding: utf-8 -*-
"""
format_timestamp — 从 sessions.py 拷出

拷贝来源: sessions.py 第52-64行
"""

from datetime import datetime, timezone
from typing import Any

from app.utils.time_utils import convert_to_utc


def format_timestamp(val: Any) -> str:
    """拷贝自 sessions.py 第52-64行"""
    if isinstance(val, (int, float)):
        return datetime.fromtimestamp(val / 1000, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.%f') + 'Z'
    if isinstance(val, str):
        return val.replace('+00:00', 'Z') if '+00:00' in val else (val + 'Z' if not val.endswith('Z') else val)
    return convert_to_utc(val)
