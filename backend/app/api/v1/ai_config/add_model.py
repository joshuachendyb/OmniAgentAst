from . import router
from .models import ModelAddRequest
from ._write_yaml_with_order import _write_yaml_with_order
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.post("/config/provider/{provider_name}/model")
async def add_model(provider_name: str, data: ModelAddRequest):
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        model_name = ' '.join(data.model.split())
        models = config['ai'][provider_name].get('models', [])
        if model_name in models:
            raise HTTPException(status_code=400, detail=f"模型 {model_name} 已存在")
        models.append(model_name)
        config['ai'][provider_name]['models'] = models
        if not config['ai'].get('model'):
            config['ai']['model'] = model_name
        _write_yaml_with_order(str(config_path), config)
        config_obj = get_config_instance()
        config_obj._load_config()
        AIServiceFactory.reset()
        return {"success": True, "message": f"模型 {data.model} 已添加"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
