from . import router
from ._write_yaml_with_order import _write_yaml_with_order
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.delete("/config/provider/{provider_name}")
async def delete_provider(provider_name: str):
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        provider_keys = [k for k in config.get('ai', {}).keys() if k != 'provider']
        if len(provider_keys) <= 1:
            raise HTTPException(status_code=400, detail="至少保留一个Provider")
        del config['ai'][provider_name]
        if config['ai'].get('provider') == provider_name:
            remaining = [k for k in config['ai'].keys() if k != 'provider']
            if remaining:
                config['ai']['provider'] = remaining[0]
        _write_yaml_with_order(str(config_path), config)
        config_obj = get_config_instance()
        config_obj._load_config()
        AIServiceFactory.reset()
        return {"success": True, "message": f"Provider {provider_name} 已删除"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除Provider失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
