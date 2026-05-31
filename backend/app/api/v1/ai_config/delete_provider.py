from . import router
from ._helpers import get_config_path, read_yaml_config, write_yaml_config, reload_ai_config
from ._decorators import handle_config_errors
from ._validators import ensure_provider_exists
from fastapi import HTTPException
from app.utils.response_utils import api_success


@router.delete("/config/provider/{provider_name}")
@handle_config_errors("删除Provider")
async def delete_provider(provider_name: str):
    config_path = get_config_path()
    config = read_yaml_config(config_path)

    ensure_provider_exists(config, provider_name)
    provider_keys = [k for k in config.get('ai', {}).keys() if k != 'provider']
    if len(provider_keys) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个Provider")

    del config['ai'][provider_name]
    if config['ai'].get('provider') == provider_name:
        remaining = [k for k in config['ai'].keys() if k != 'provider']
        if remaining:
            config['ai']['provider'] = remaining[0]

    write_yaml_config(str(config_path), config)
    reload_ai_config()
    return api_success(f"Provider {provider_name} 已删除")
