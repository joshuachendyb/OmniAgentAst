# -*- coding: utf-8 -*-
"""
get_config_path — 从 factory.py 拷出

拷贝来源: factory.py 第127-134行
"""

from typing import Optional


def get_config_path(config_path: Optional[str] = None) -> str:
    """拷贝自 factory.py 第127-134行"""
    if config_path is not None:
        return config_path
    from app.utils.paths import get_config_path as _get
    return _get()
