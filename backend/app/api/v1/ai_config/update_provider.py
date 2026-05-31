from . import router
from .models import ProviderUpdate
from ._backup_config import _backup_config
from ._write_yaml_with_order import _write_yaml_with_order
from ._fix_config_common_issues import _fix_config_common_issues
from ._validate_config_integrity import _validate_config_integrity
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.put("/config/provider/{provider_name}")
async def update_provider(provider_name: str, data: ProviderUpdate):
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        backup_path = _backup_config(config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if provider_name not in config.get('ai', {}):
            raise HTTPException(status_code=404, detail=f"Provider {provider_name} 不存在")
        if data.api_base is not None:
            config['ai'][provider_name]['api_base'] = data.api_base
        if data.api_key is not None:
            config['ai'][provider_name]['api_key'] = data.api_key.strip()
        if data.model is not None:
            config['ai']['model'] = data.model.strip()
        if data.timeout is not None:
            config['ai'][provider_name]['timeout'] = data.timeout
        if data.max_retries is not None:
            config['ai'][provider_name]['max_retries'] = data.max_retries
        config = _fix_config_common_issues(config)
        is_valid, errors, warnings = _validate_config_integrity(config)
        if not is_valid:
            return {
                "success": False,
                "message": "配置验证失败",
                "errors": errors,
                "warnings": warnings,
                "backup_path": str(backup_path)
            }
        _write_yaml_with_order(str(config_path), config)
        config_obj = get_config_instance()
        config_obj._load_config()
        AIServiceFactory.reset()
        return {
            "success": True,
            "message": f"Provider {provider_name} 已更新",
            "warnings": warnings,
            "backup_path": str(backup_path)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新Provider失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
