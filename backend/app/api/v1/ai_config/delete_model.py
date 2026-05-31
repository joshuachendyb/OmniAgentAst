from . import router
from ._write_yaml_with_order import _write_yaml_with_order
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.delete("/config/provider/{provider_name}/model/{model_name}")
async def delete_model(provider_name: str, model_name: str):
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        provider_config = config.get('ai', {}).get(provider_name, {})
        if not provider_config:
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        models = provider_config.get('models', [])
        if model_name not in models:
            raise HTTPException(status_code=404, detail=f"模型 {model_name} 不存在")
        if len(models) <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个模型")
        models.remove(model_name)
        config['ai'][provider_name]['models'] = models
        ai_config = config.get('ai', {})
        current_model = ai_config.get('model', '')
        if current_model == model_name and models:
            config['ai']['model'] = models[0]
        _write_yaml_with_order(str(config_path), config)
        config_obj = get_config_instance()
        config_obj._load_config()
        AIServiceFactory.reset()
        return {"success": True, "message": f"模型 {model_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除模型失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
