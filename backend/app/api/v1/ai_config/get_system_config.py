from . import router
from .models import ConfigResponse, SecurityConfig
from ._decorators import handle_config_errors
from app.config import get_config as get_config_instance
from app.utils.logger import logger
from app.services.ai_config_resolver import resolve_provider_model


@router.get("/config", response_model=ConfigResponse)
@handle_config_errors("获取配置")
async def get_system_config():
    config = get_config_instance()
    final_provider, final_model = resolve_provider_model()
    ai_config = config.get('ai', {})
    provider_config = ai_config.get(final_provider, {})
    api_key = provider_config.get('api_key', '')
    api_key_configured = bool(api_key and api_key.strip() != '')
    theme = config.get('app.theme', 'light')
    language = config.get('app.language', 'zh-CN')
    security_config = config.get('security', {})
    if not security_config:
        security_config = SecurityConfig(
            contentFilterEnabled=True,
            contentFilterLevel="medium",
            whitelistEnabled=False,
            commandWhitelist="",
            commandBlacklist="",
            confirmDangerousOps=True,
            maxFileSize=100
        )
    else:
        security_config = SecurityConfig(**security_config)
    logger.info(f"获取配置成功: provider={final_provider}, model={final_model}")
    return ConfigResponse(
        ai_provider=final_provider,
        ai_model=final_model,
        api_key_configured=api_key_configured,
        theme=theme,
        language=language,
        security=security_config,
        max_steps=config.get_max_steps(100)
    )
