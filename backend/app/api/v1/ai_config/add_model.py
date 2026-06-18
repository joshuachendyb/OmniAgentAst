from . import router
from .models import ModelAddRequest
from ._helpers import load_config, save_config
from ._helpers import handle_config_errors
from ._validators import ensure_provider_exists, ensure_model_not_duplicate
from app.utils.response_utils import api_success


@router.post("/config/provider/{provider_name}/model")
@handle_config_errors("添加模型")
async def add_model(provider_name: str, data: ModelAddRequest):
    config_path, config = load_config()

    ensure_provider_exists(config, provider_name)
    model_name = ' '.join(data.model.split())
    ensure_model_not_duplicate(config, provider_name, model_name)

    models = config['ai'][provider_name].get('models', [])
    models.append(model_name)
    config['ai'][provider_name]['models'] = models
    if not config['ai'].get('model'):
        config['ai']['model'] = model_name

    save_config(str(config_path), config)
    return api_success(f"模型 {data.model} 已添加")
