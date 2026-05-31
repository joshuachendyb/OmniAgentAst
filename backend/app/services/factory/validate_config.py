# -*- coding: utf-8 -*-
"""
validate_config — 从 factory.py 拷出

拷贝来源: factory.py 第163-202行
"""

from typing import Optional

import os

from app.services.factory.models import ConfigValidationResult
from app.services.factory.get_config_path import get_config_path
from app.services.factory.make_validation_error import make_validation_error
from app.services.factory.validate_credentials import validate_credentials


def validate_config(config_path: Optional[str] = None) -> ConfigValidationResult:
    """拷贝自 factory.py 第163-202行"""
    actual_path = get_config_path(config_path)
    if not os.path.exists(actual_path):
        return make_validation_error("配置文件不存在", errors=[f"配置文件不存在: {actual_path}"])

    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    is_valid, final_provider, final_model, error_messages = resolver.validate_config()

    if not is_valid:
        return make_validation_error(
            f"配置验证失败: {len(error_messages)} 个错误",
            provider=final_provider or "unknown",
            model=final_model or "",
            errors=error_messages, warnings=[]
        )

    cred_errors, cred_warnings = validate_credentials(resolver.get_ai_config(), final_provider)

    if cred_errors:
        return make_validation_error(f"配置验证失败: {len(cred_errors)} 个错误",
                                     provider=final_provider, model=final_model,
                                     errors=cred_errors, warnings=cred_warnings)

    message = f"配置验证通过: provider={final_provider}, model={final_model}"
    if cred_warnings:
        message += f" ({len(cred_warnings)} 个警告)"
    return ConfigValidationResult(success=True, provider=final_provider, model=final_model,
                                  message=message, errors=cred_errors, warnings=cred_warnings)
