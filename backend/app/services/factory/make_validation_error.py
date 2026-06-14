# -*- coding: utf-8 -*-
"""
make_validation_error — 从 factory.py 拷出

拷贝来源: factory.py 第136-145行
"""

from typing import Optional, List

from app.services.factory.models import ConfigValidationResult


def make_validation_error(message: str, field: str = "",
                          provider: str = "", model: str = "",
                          errors: Optional[list] = None,
                          warnings: Optional[list] = None) -> ConfigValidationResult:
    """拷贝自 factory.py 第136-145行"""
    return ConfigValidationResult(
        success=False, provider=provider, model=model, message=message,
        errors=errors or ([{"field": field, "message": message}] if field else []),
        warnings=warnings or [])
