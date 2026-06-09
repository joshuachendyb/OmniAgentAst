from . import router
from .models import ModelInfo, ModelListResponse
from app.services.ai_config_resolver import get_ai_config_resolver
from app.utils.logger import logger


@router.get("/config/models", response_model=ModelListResponse)
async def get_model_list():
    try:
        resolver = get_ai_config_resolver()
        ai_config = resolver.get_ai_config()
        final_provider, final_model = resolver.resolve_provider_model()
        models = []
        model_id = 1
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if not isinstance(provider_data, dict):
                continue
            provider_models = provider_data.get('models', [])
            if isinstance(provider_models, list) and provider_models:
                for model_name in provider_models:
                    display_name = f"{provider_name} ({model_name})"
                    is_current = (final_provider == provider_name and final_model == model_name)
                    models.append(ModelInfo(
                        id=model_id,
                        provider=provider_name,
                        model=model_name,
                        display_name=display_name,
                        current_model=is_current
                    ))
                    model_id += 1
        logger.info(f"获取模型列表成功: {len(models)}个模型")
        return ModelListResponse(
            models=models,
            default_provider=final_provider
        )
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return ModelListResponse(
            models=[],
            default_provider=''
        )
