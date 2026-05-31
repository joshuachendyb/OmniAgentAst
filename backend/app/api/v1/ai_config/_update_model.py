from ._invalidate_ai_service_cache import _invalidate_ai_service_cache
from app.utils.logger import logger


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
        _invalidate_ai_service_cache(provider)
