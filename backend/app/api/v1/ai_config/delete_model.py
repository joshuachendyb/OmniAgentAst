from . import router
from ._helpers import get_config_path, read_yaml_config, write_yaml_config, reload_ai_config
from ._decorators import handle_config_errors
from ._validators import ensure_provider_exists, ensure_model_exists
from fastapi import HTTPException
from app.utils.response_utils import api_success


@router.delete("/config/provider/{provider_name}/model/{model_name}")
@handle_config_errors("删除模型")
async def delete_model(provider_name: str, model_name: str):
    config_path = get_config_path()
    config = read_yaml_config(config_path)

    ensure_provider_exists(config, provider_name)
    ensure_model_exists(config, provider_name, model_name)
    models = config['ai'][provider_name].get('models', [])
    if len(models) <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个模型")

    models.remove(model_name)
    config['ai'][provider_name]['models'] = models

    write_yaml_config(str(config_path), config)
    reload_ai_config()
    return api_success(f"模型 {model_name} 已删除")
