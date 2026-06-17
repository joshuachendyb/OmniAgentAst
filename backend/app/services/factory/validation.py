# -*- coding: utf-8 -*-
"""
validation — 配置验证

合并: validate_config + validate_credentials + make_validation_error
小沈 2026-06-17
"""

from typing import Optional, Tuple, List

import os

from app.services.factory.models import ConfigValidationResult
from app.utils.paths import get_config_path


def make_validation_error(message: str, field: str = "",
                          provider: str = "", model: str = "",
                          errors: Optional[list] = None,
                          warnings: Optional[list] = None) -> ConfigValidationResult:
    """构建验证错误结果 — 小沈 2026-06-08"""
    return ConfigValidationResult(
        success=False, provider=provider, model=model, message=message,
        errors=errors or ([{"field": field, "message": message}] if field else []),
        warnings=warnings or [])


def validate_credentials(ai_config: dict, final_provider: str) -> Tuple[list, list]:
    """验证凭证 — 小沈 2026-06-08"""
    errors = []
    warnings = []
    selected_provider_config = ai_config.get(final_provider, {})
    api_key = selected_provider_config.get("api_key")
    if not api_key:
        errors.append(f"provider '{final_provider}' 缺少 api_key 配置")
    elif not isinstance(api_key, str) or api_key.strip() == "":
        errors.append(f"provider '{final_provider}' 的 api_key 为空")
    api_base = selected_provider_config.get("api_base")
    if not api_base:
        warnings.append(f"provider '{final_provider}' 未配置 api_base,将使用默认值")
    return errors, warnings


def _check_config_exists(actual_path: str) -> Optional[ConfigValidationResult]:
    """检查配置文件存在 — 小沈 2026-06-08"""
    if not os.path.exists(actual_path):
        return make_validation_error("配置文件不存在", errors=[f"配置文件不存在: {actual_path}"])
    return None


def _resolve_provider_model(resolver=None) -> Tuple[Optional[str], Optional[str], list]:
    """解析provider和model — 小沈 2026-06-09 接受外部resolver"""
    if resolver is None:
        from app.services.ai_config_resolver import get_ai_config_resolver
        resolver = get_ai_config_resolver()
    try:
        provider, model = resolver.resolve_provider_model()
        return provider, model, []
    except ValueError as e:
        return None, None, [str(e)]


def _make_provider_model_error(errors: list, provider: Optional[str], model: Optional[str]) -> ConfigValidationResult:
    """构建provider/model错误 — 小沈 2026-06-08"""
    return make_validation_error(
        f"配置验证失败: {len(errors)} 个错误",
        provider=provider or "unknown",
        model=model or "",
        errors=errors, warnings=[])


def _validate_credentials_internal(provider: str, resolver=None) -> Tuple[list, list]:
    """验证凭证(内部) — 小沈 2026-06-09 接受外部resolver"""
    if resolver is None:
        from app.services.ai_config_resolver import get_ai_config_resolver
        resolver = get_ai_config_resolver()
    return validate_credentials(resolver.get_ai_config(), provider)


def _make_credentials_error(cred_errors: list, cred_warnings: list, provider: str, model: str) -> ConfigValidationResult:
    """构建凭证错误 — 小沈 2026-06-08"""
    return make_validation_error(
        f"配置验证失败: {len(cred_errors)} 个错误",
        provider=provider, model=model,
        errors=cred_errors, warnings=cred_warnings)


def _make_success_result(provider: str, model: str, cred_errors: list, cred_warnings: list) -> ConfigValidationResult:
    """构建成功结果 — 小沈 2026-06-08"""
    message = f"配置验证通过: provider={provider}, model={model}"
    if cred_warnings:
        message += f" ({len(cred_warnings)} 个警告)"
    return ConfigValidationResult(
        success=True, provider=provider, model=model,
        message=message, errors=cred_errors, warnings=cred_warnings)


def validate_config(config_path: Optional[str] = None) -> ConfigValidationResult:
    """验证配置 — 小沈 2026-06-08; 2026-06-09 resolver复用"""
    actual_path = get_config_path(config_path)
    
    error = _check_config_exists(actual_path)
    if error:
        return error
    
    from app.services.ai_config_resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()
    
    provider, model, errors = _resolve_provider_model(resolver)
    if errors:
        return _make_provider_model_error(errors, provider, model)
    
    cred_errors, cred_warnings = _validate_credentials_internal(provider, resolver)
    if cred_errors:
        return _make_credentials_error(cred_errors, cred_warnings, provider, model)
    
    return _make_success_result(provider, model, cred_errors, cred_warnings)