from . import router
from .models import ConfigFixResponse
from ._backup_config import _backup_config
from ._write_yaml_with_order import _write_yaml_with_order
from ._validate_config_integrity import _validate_config_integrity
from pathlib import Path
from fastapi import HTTPException
import yaml
from app.config import get_config as get_config_instance
from app.services import AIServiceFactory
from app.utils.logger import logger


@router.post("/config/fix", response_model=ConfigFixResponse)
async def fix_config():
    try:
        config_path = Path(AIServiceFactory.get_config_path())
        backup_path = _backup_config(config_path)
        with open(config_path, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f) or {}
        fixed_issues = []
        ai_config = config_data.get('ai', {})
        for provider_name in ai_config.keys():
            if provider_name == 'provider' or provider_name == 'model':
                continue
            provider_data = ai_config.get(provider_name, {})
            if isinstance(provider_data, dict) and 'model' in provider_data:
                del provider_data['model']
                fixed_issues.append(f"删除 provider '{provider_name}' 下废弃的 model 字段")
        is_valid, errors, warnings = _validate_config_integrity(config_data)
        if not is_valid:
            return ConfigFixResponse(
                success=False,
                fixed_issues=fixed_issues,
                warnings=warnings + errors,
                backup_path=str(backup_path)
            )
        with open(config_path, 'w', encoding='utf-8') as f:
            _write_yaml_with_order(str(config_path), config_data)
        config = get_config_instance()
        config.reload()
        logger.info(f"配置修复成功: 修复了 {len(fixed_issues)} 个问题")
        return ConfigFixResponse(
            success=True,
            fixed_issues=fixed_issues,
            warnings=warnings,
            backup_path=str(backup_path)
        )
    except Exception as e:
        logger.error(f"配置修复失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置修复失败: {str(e)}")
