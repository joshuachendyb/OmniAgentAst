# -*- coding: utf-8 -*-
"""
validate_config — 从 factory.py 拷出

拷贝来源: factory.py 第163-202行
"""

from typing import Optional, Tuple

import os

from app.services.factory.models import ConfigValidationResult
from app.utils.paths import get_config_path
from app.services.factory.make_validation_error import make_validation_error
from app.services.factory.validate_credentials import validate_credentials


def _check_config_exists(actual_path: str) -> Optional[ConfigValidationResult]:
    """检查配置文件存在 - 小沈 2026-06-08"""
    if not os.path.exists(actual_path):
        return make_validation_error("配置文件不存在", errors=[f"配置文件不存在: {actual_path}"])
    return None


def _resolve_provider_model() -> Tuple[Optional[str], Optional[str], list]:
    """解析provider和model - 小沈 2026-06-08"""
    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    try:
        provider, model = resolver.resolve_provider_model()
        return provider, model, []
    except ValueError as e:
        return None, None, [str(e)]


def _make_provider_model_error(errors: list, provider: Optional[str], model: Optional[str]) -> ConfigValidationResult:
    """构建provider/model错误 - 小沈 2026-06-08"""
    return make_validation_error(
        f"配置验证失败: {len(errors)} 个错误",
        provider=provider or "unknown",
        model=model or "",
        errors=errors, warnings=[]
    )


def _validate_credentials(provider: str) -> Tuple[list, list]:
    """验证凭证 - 小沈 2026-06-08"""
    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    return validate_credentials(resolver.get_ai_config(), provider)


def _make_credentials_error(cred_errors: list, cred_warnings: list, provider: str, model: str) -> ConfigValidationResult:
    """构建凭证错误 - 小沈 2026-06-08"""
    return make_validation_error(
        f"配置验证失败: {len(cred_errors)} 个错误",
        provider=provider, model=model,
        errors=cred_errors, warnings=cred_warnings
    )


def _make_success_result(provider: str, model: str, cred_errors: list, cred_warnings: list) -> ConfigValidationResult:
    """构建成功结果 - 小沈 2026-06-08"""
    message = f"配置验证通过: provider={provider}, model={model}"
    if cred_warnings:
        message += f" ({len(cred_warnings)} 个警告)"
    return ConfigValidationResult(
        success=True, provider=provider, model=model,
        message=message, errors=cred_errors, warnings=cred_warnings
    )


def validate_config(config_path: Optional[str] = None) -> ConfigValidationResult:
    """拷贝自 factory.py 第163-202行"""
    actual_path = get_config_path(config_path)
    
    error = _check_config_exists(actual_path)
    if error:
        return error
    
    provider, model, errors = _resolve_provider_model()
    if errors:
        return _make_provider_model_error(errors, provider, model)
    
    cred_errors, cred_warnings = _validate_credentials(provider)
    if cred_errors:
        return _make_credentials_error(cred_errors, cred_warnings, provider, model)
    
    return _make_success_result(provider, model, cred_errors, cred_warnings)
