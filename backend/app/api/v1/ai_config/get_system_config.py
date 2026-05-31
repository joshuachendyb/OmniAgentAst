from . import router
from .models import ConfigResponse, SecurityConfig
from fastapi import HTTPException
from app.config import get_config as get_config_instance
from app.utils.logger import logger
from app.services.ai_config_resolver import resolve_provider_model


@router.get("/config", response_model=ConfigResponse)
async def get_system_config():
    try:
        config = get_config_instance()
        from app.services.ai_config_resolver import resolve_provider_model
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
    except Exception as e:
        logger.error(f"获取配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")
