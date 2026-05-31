from . import router
from .models import ConfigValidateRequest, ConfigValidateResponse
from app.services.ai_config_resolver import get_ai_config_resolver
from app.utils.logger import logger


@router.put("/config/validate", response_model=ConfigValidateResponse)
async def validate_config(request: ConfigValidateRequest):
    try:
        resolver = get_ai_config_resolver()
        try:
            provider_config = resolver.get_service_config(request.provider, request.model)
        except ValueError as e:
            return ConfigValidateResponse(
                valid=False,
                message=str(e),
                model=None
            )
        final_provider, final_model = resolver.resolve_provider_model()
        logger.info(f"配置已保存: provider={final_provider}, model={final_model}")
        return ConfigValidateResponse(
            valid=True,
            message=f"配置已保存，将在首次使用时验证 {final_provider} ({final_model})",
            model=final_model
        )
    except Exception as e:
        logger.error(f"配置验证异常: {e}")
        return ConfigValidateResponse(
            valid=False,
            message=f"验证过程出错: {str(e)}",
            model=None
        )
