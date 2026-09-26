# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.6: 全链 ModelRef 归一——ConfigValidationResult.provider/model
#   两分离字段归一为 model_ref: Optional[ModelRef]; _resolve_provider_model 返回 (ModelRef|None, errors);
#   各 make_*_result 工厂与 validate_config 主流程形参同步改透传 model_ref(日志文本内取 .provider/.model
#   拼展示串属派生, 允许) — F8 无兼容 shim, 调用点随改
# 2026-09-26 - 小欧 - [72]第二章(2.4 配套·DRY) 落地: api_key 空判定改调公用函数 is_blank_secret()
#   修前此处为 `not isinstance(api_key, str) or api_key.strip() == ""`，与 model/resolver.py 的
#   `(_pv_cfg.get("api_key") or "").strip() or None` 是两处独立写法、语义却相同（空/纯空白=未配置）。
#   同一判定两处各写一遍，第三次出现不一致只是时间问题 —— 抽出全局层 app/utils/secret_utils.py
#   作唯一权威（DRY：相同逻辑只写一次）。行为等价，非字符串仍按未配置处理，验证语义零变化 — 小欧 2026-09-26
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
# 2026-09-26 小欧 - [72]第二章(2.4 配套·DRY): 密钥空白判定收口到公用函数
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
    if not api_key:
        errors.append(f"provider '{final_provider}' 缺少 api_key 配置")
    elif is_blank_secret(api_key):
        # [72]第二章(2.4 配套·DRY) - 小欧 - 2026-09-26: 原为 `not isinstance(api_key, str) or api_key.strip() == ""`，
        #   与 resolver 的"key 空白判定"是同一语义的两份独立写法；现统一收口到 app.utils.secret_utils.is_blank_secret，
        #   杜绝第三次出现不一致写法（DRY）。语义不变：空/纯空白 = 未配置。
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