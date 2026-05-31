from . import router
from .models import ModelAddRequest
from ._helpers import get_config_path, read_yaml_config, write_yaml_config, reload_ai_config
from ._decorators import handle_config_errors
from ._validators import ensure_provider_exists
from app.utils.response_utils import api_success


@router.put("/config/provider/{provider_name}/model/{old_model_name}")
@handle_config_errors("更新模型")
async def update_model(provider_name: str, old_model_name: str, data: ModelAddRequest):
    config_path = get_config_path()
    config = read_yaml_config(config_path)

    ensure_provider_exists(config, provider_name)
    models = config['ai'][provider_name].get('models', [])
    new_model_name = ' '.join(data.model.split())

    if old_model_name not in models:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"模型 {old_model_name} 不存在")
    if new_model_name == old_model_name:
        return api_success("模型名称未改变")
    if new_model_name in models:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"模型 {new_model_name} 已存在")

    index = models.index(old_model_name)
    models[index] = new_model_name
    config['ai'][provider_name]['models'] = models

    write_yaml_config(str(config_path), config)
    reload_ai_config()
    return api_success(f"模型已从 {old_model_name} 更新为 {new_model_name}")
