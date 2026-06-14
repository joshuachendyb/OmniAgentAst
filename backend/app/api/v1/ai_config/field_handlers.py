"""字段级更新处理函数 — 替代分散的 _update_*.py 文件

原分散文件: _update_provider.py, _update_model.py, _update_api_keys.py,
_update_max_steps.py, _update_security.py
F10合并: 小欧 - 2026-06-08
"""

from typing import Dict, Any
from fastapi import HTTPException

from app.utils.logger import logger
from app.services import reset
from ._helpers import _set_app_field
from .models import SecurityConfig


def _update_provider(config_data: dict, update) -> None:
    ai_config = config_data.get('ai', {})
    if update.ai_provider not in ai_config:
        raise HTTPException(status_code=400, detail=f"不支持的提供商: {update.ai_provider}")
    config_data['ai']['provider'] = update.ai_provider
    reset()
    logger.info(f"更新AI Provider: {update.ai_provider}")


def _update_model(config_data: dict, update) -> None:
    _ai_cfg = config_data.get('ai', {})
    provider = update.ai_provider or _ai_cfg.get('provider')
    if not provider:
        for _k, _v in _ai_cfg.items():
            if isinstance(_v, dict) and _v.get('models'):
                provider = _k
                break
    if provider in config_data.get('ai', {}):
        config_data['ai']['model'] = update.ai_model
        logger.info(f"更新AI Model: {update.ai_model} (provider={provider})")
        reset()


def _update_api_keys(config_data: dict, update) -> None:
    for provider_name, api_key in (update.provider_api_keys or {}).items():
        if provider_name in config_data.get('ai', {}):
            config_data['ai'][provider_name]['api_key'] = api_key.strip()
            logger.info(f"更新Provider API Key成功: {provider_name}")
        else:
            raise HTTPException(status_code=400, detail=f"不支持的Provider: {provider_name}")


def _update_max_steps(config_data: dict, update) -> None:
    if update.max_steps < 1:
        raise HTTPException(status_code=400, detail="max_steps 必须大于等于 1")
    if update.max_steps > 1000:
        raise HTTPException(status_code=400, detail="max_steps 不能超过 1000")
    config_data.setdefault('app', {})['max_steps'] = update.max_steps
    logger.info(f"更新max_steps: {update.max_steps}")


def _update_security(config_data: dict, update) -> None:
    if not update.security:
        return
    config_data['security'] = {
        "contentFilterEnabled": update.security.contentFilterEnabled,
        "contentFilterLevel": update.security.contentFilterLevel,
        "whitelistEnabled": update.security.whitelistEnabled,
        "commandWhitelist": update.security.commandWhitelist,
        "commandBlacklist": update.security.commandBlacklist,
        "confirmDangerousOps": update.security.confirmDangerousOps,
        "maxFileSize": update.security.maxFileSize,
    }
    logger.info("更新安全配置成功")


FIELD_HANDLERS: Dict[str, Any] = {
    "ai_provider": _update_provider,
    "ai_model": _update_model,
    "provider_api_keys": _update_api_keys,
    "theme": lambda config_data, update: _set_app_field(config_data, "theme", update.theme, "主题"),
    "language": lambda config_data, update: _set_app_field(config_data, "language", update.language, "语言"),
    "max_steps": _update_max_steps,
    "security": _update_security,
}
