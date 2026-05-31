from . import router
from .models import ProviderAddRequest
from ._backup_config import _backup_config
from ._write_yaml_with_order import _write_yaml_with_order
from ._validate_config_integrity import _validate_config_integrity
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.post("/config/provider")
async def add_provider(data: ProviderAddRequest):
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        backup_path = _backup_config(config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if data.name in config.get('ai', {}):
            raise HTTPException(status_code=400, detail=f"Provider {data.name} 已存在")
        config['ai'][data.name] = {
            'api_base': data.api_base.strip(),
            'api_key': data.api_key.strip() if data.api_key else "",
            'models': [m.strip() for m in (data.models if data.models else ([data.model] if data.model else []))],
            'timeout': data.timeout,
            'max_retries': data.max_retries
        }
        is_valid, errors, warnings = _validate_config_integrity(config)
        if not is_valid:
            return {
                "success": False,
                "message": "配置验证失败",
                "errors": errors,
                "backup_path": str(backup_path)
            }
        _write_yaml_with_order(str(config_path), config)
        config_obj = get_config_instance()
        config_obj._load_config()
        AIServiceFactory.reset()
        return {
            "success": True,
            "message": f"Provider {data.name} 已添加",
            "warnings": warnings
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"添加Provider失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
