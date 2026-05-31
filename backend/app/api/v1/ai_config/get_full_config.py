from . import router
from .models import FullConfigResponse, ProviderInfo
from ._decorators import handle_config_errors
from app.services.ai_config_resolver import get_ai_config_resolver


@router.get("/config/full", response_model=FullConfigResponse)
@handle_config_errors("获取完整配置")
async def get_full_config():
    resolver = get_ai_config_resolver()
    ai_config = resolver.get_ai_config()
    final_provider, final_model = resolver.resolve_provider_model()
    providers = {}
    for provider_name in ai_config.keys():
        if provider_name == 'provider' or provider_name == 'model':
            continue
        provider_data = ai_config.get(provider_name, {})
        if not isinstance(provider_data, dict):
            continue
        api_key = provider_data.get('api_key', '')
        providers[provider_name] = ProviderInfo(
            name=provider_name,
            api_base=provider_data.get('api_base', ''),
            api_key=api_key,
            model='',
            models=provider_data.get('models', []),
            timeout=provider_data.get('timeout', 60),
            max_retries=provider_data.get('max_retries', 3)
        )
    return FullConfigResponse(
        providers=providers,
        current_provider=final_provider,
        current_model=final_model
    )
