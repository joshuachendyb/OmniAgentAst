# -*- coding: utf-8 -*-
"""
ConfigValidationResult — 从 factory.py 拷出

拷贝来源: factory.py 第78-86行
"""

from dataclasses import dataclass


@dataclass
class ConfigValidationResult:
    """拷贝自 factory.py 第78-86行"""
    success: bool
    provider: str
    model: str
    message: str
    errors: list
    warnings: list
