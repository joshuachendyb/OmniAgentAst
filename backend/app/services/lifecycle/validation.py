# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.6: 全链 ModelRef 归一——ConfigValidationResult.provider/model
#   两分离字段归一为 model_ref: Optional[ModelRef]; _resolve_provider_model 返回 (ModelRef|None, errors);
#   各 make_*_result 工厂与 validate_config 主流程形参同步改透传 model_ref(日志文本内取 .provider/.model
#   拼展示串属派生, 允许) — F8 无兼容 shim, 调用点随改
# 2026-09-26 - 小欧 - api_key 空判定收口公用函数 is_blank_secret()，消除与 model/resolver.py 的重复写法 — 小欧 2026-09-26
# 2026-09-26 (三堂会审后修正·二) - 小欧 - 删残留的外层 `if not api_key:`：它是 is_blank_secret 的真子集，
#   同一判定写两遍（DRY），且两套文案同指"没有可用 api_key"。详见 validate_credentials 内注释。
# 2026-09-27 - 小欧 - 订正空 api_base 警示文案（原文"将使用默认值"撒谎：已删 client_sdk
#   兜底，空 URL 调用即 400）。改为如实告知"调用时会报错，请到设置页填写完整地址" — 小欧 2026-09-27
"""
validation — 配置验证

合并: validate_config + validate_credentials + make_validation_error
小沈 2026-06-17
"""

from typing import Optional, Tuple, List
from dataclasses import dataclass

import os

from app.config import get_config_path
from app.db.models.chat_models import ModelRef
# 2026-09-26 小欧 - 密钥空白判定收口到公用函数(DRY)
from app.utils.secret_utils import is_blank_secret


@dataclass
class ConfigValidationResult:
    """配置验证结果 — 小沈 2026-06-08; 2026-08-22 归一: provider/model → model_ref(ModelRef) — 小欧"""
    success: bool
    model_ref: Optional[ModelRef]
    message: str
    errors: list
    warnings: list


def make_validation_error(message: str, field: str = "",
                          model_ref: Optional[ModelRef] = None,
                          errors: Optional[list] = None,
                          warnings: Optional[list] = None) -> ConfigValidationResult:
    """构建验证错误结果 — 小沈 2026-06-08; 2026-08-22 归一 model_ref — 小欧"""
    return ConfigValidationResult(
        success=False, model_ref=model_ref, message=message,
        errors=errors or ([{"field": field, "message": message}] if field else []),
        warnings=warnings or [])


def validate_credentials(ai_config: dict, final_provider: str) -> Tuple[list, list]:
    """验证凭证 — 小沈 2026-06-08"""
    errors = []
    warnings = []
    selected_provider_config = ai_config.get(final_provider, {})
    api_key = selected_provider_config.get("api_key")
    # 2026-09-26 - 小欧 - 判空收口 is_blank_secret（缺失/空串/纯空白/类型非法统一为"未配置"），
    #   文案带出实际类型与值，便于定位 YAML 手误。详见文件头「三堂会审后修正·二」
    if is_blank_secret(api_key):
        errors.append(
            f"provider '{final_provider}' 未配置可用的 api_key"
            f"（缺失/空串/纯空白，或类型非法：{type(api_key).__name__}={api_key!r}）"
        )
    api_base = selected_provider_config.get("api_base")
    if not api_base:
        # 2026-09-27 - 小欧 - 订正文案撒谎：原文写"将使用默认值"，但已删
        #   client_sdk 的 _default_base_url/_DEFAULT_URLS 兜底，空 URL 构造即抛 400
        #   （见 client_sdk.py:298「provider X 的 URL 为空，请到设置页填写完整地址」）。
        #   继续写"用默认值"会让用户以为不填也能跑，真调用时才 400 且难归因。改为如实告知。
        warnings.append(
            f"provider '{final_provider}' 未配置 api_base，调用时会报错，请到设置页填写完整地址"
        )
    return errors, warnings


def _check_config_exists(actual_path: str) -> Optional[ConfigValidationResult]:
    """检查配置文件存在 — 小沈 2026-06-08"""
    if not os.path.exists(actual_path):
        return make_validation_error("配置文件不存在", errors=[f"配置文件不存在: {actual_path}"])
    return None


def _resolve_provider_model(resolver=None) -> Tuple[Optional[ModelRef], list]:
    """解析provider和model — 小沈 2026-06-09 接受外部resolver; 2026-08-22 归一返回 (ModelRef|None, errors) — 小欧"""
    if resolver is None:
        from app.services.model.resolver import get_ai_config_resolver
        resolver = get_ai_config_resolver()
    try:
        return resolver.resolve_model_ref(), []
    except ValueError as e:
        return None, [str(e)]


def _make_provider_model_error(errors: list, model_ref: Optional[ModelRef]) -> ConfigValidationResult:
    """构建provider/model错误 — 小沈 2026-06-08; 2026-08-22 归一 — 小欧"""
    return make_validation_error(
        f"配置验证失败: {len(errors)} 个错误",
        model_ref=model_ref,
        errors=errors, warnings=[])


def _validate_credentials_internal(model_ref: ModelRef, resolver=None) -> Tuple[list, list]:
    """验证凭证(内部) — 小沈 2026-06-09 接受外部resolver; 2026-08-22 归一入参 — 小欧"""
    if resolver is None:
        from app.services.model.resolver import get_ai_config_resolver
        resolver = get_ai_config_resolver()
    return validate_credentials(resolver.get_ai_config(), model_ref.provider)


def _make_credentials_error(cred_errors: list, cred_warnings: list, model_ref: ModelRef) -> ConfigValidationResult:
    """构建凭证错误 — 小沈 2026-06-08; 2026-08-22 归一 — 小欧"""
    return make_validation_error(
        f"配置验证失败: {len(cred_errors)} 个错误",
        model_ref=model_ref,
        errors=cred_errors, warnings=cred_warnings)


def _make_success_result(model_ref: ModelRef, cred_errors: list, cred_warnings: list) -> ConfigValidationResult:
    """构建成功结果 — 小沈 2026-06-08; 2026-08-22 归一(message 拼展示串属派生) — 小欧"""
    message = f"配置验证通过: provider={model_ref.provider}, model={model_ref.model}"
    if cred_warnings:
        message += f" ({len(cred_warnings)} 个警告)"
    return ConfigValidationResult(
        success=True, model_ref=model_ref,
        message=message, errors=cred_errors, warnings=cred_warnings)


def validate_config(config_path: Optional[str] = None) -> ConfigValidationResult:
    """验证配置 — 小沈 2026-06-08; 2026-06-09 resolver复用; 2026-08-22 归一全链透传 model_ref — 小欧"""
    actual_path = get_config_path(config_path)

    error = _check_config_exists(actual_path)
    if error:
        return error

    from app.services.model.resolver import get_ai_config_resolver
    resolver = get_ai_config_resolver()

    model_ref, errors = _resolve_provider_model(resolver)
    if errors:
        return _make_provider_model_error(errors, model_ref)

    cred_errors, cred_warnings = _validate_credentials_internal(model_ref, resolver)
    if cred_errors:
        return _make_credentials_error(cred_errors, cred_warnings, model_ref)

    return _make_success_result(model_ref, cred_errors, cred_warnings)