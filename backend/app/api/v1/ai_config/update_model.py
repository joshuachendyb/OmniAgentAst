from . import router
from .models import ModelAddRequest
from ._write_yaml_with_order import _write_yaml_with_order
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.put("/config/provider/{provider_name}/model/{old_model_name}")
async def update_model(provider_name: str, old_model_name: str, data: ModelAddRequest):
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        models = config['ai'][provider_name].get('models', [])
        new_model_name = ' '.join(data.model.split())
        if old_model_name not in models:
            raise HTTPException(status_code=404, detail=f"模型 {old_model_name} 不存在")
        if new_model_name == old_model_name:
            return {"success": True, "message": "模型名称未改变"}
        if new_model_name in models:
            raise HTTPException(status_code=400, detail=f"模型 {new_model_name} 已存在")
        index = models.index(old_model_name)
        models[index] = new_model_name
        config['ai'][provider_name]['models'] = models
        _write_yaml_with_order(str(config_path), config)
        config_obj = get_config_instance()
        config_obj._load_config()
        AIServiceFactory.reset()
        return {"success": True, "message": f"模型已从 {old_model_name} 更新为 {new_model_name}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
